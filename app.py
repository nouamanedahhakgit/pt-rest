import os
import shutil
import subprocess
import threading
import queue
import json
import re
import copy
import fnmatch
import importlib.util
from flask import (
    Flask,
    Response,
    request,
    jsonify,
    stream_with_context,
    render_template,
    redirect,
    url_for,
    flash,
)
import openpyxl
import openai
import sys
import time
import random
import logging
from typing import Callable, Any, Optional, Dict, List


app = Flask(__name__)
app.secret_key = "dev"

# ------------------------------------------------------------
# !!! WARNING: This is not recommended for production usage !!!
# ------------------------------------------------------------
# من الأفضل تستعمل ENV بدل ما تكتب المفتاح مباشرة
openai.api_key = os.getenv("OPENAI_API_KEY",
                           "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")  # <--- Your key here

import openai_chat_compat

openai_chat_compat.install()

# ===== Retry: إعداد اللوجينغ
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ===== Retry: OpenAI exceptions (SDK 1.x; legacy openai.error was removed)
try:
    from openai import (
        APIConnectionError,
        APITimeoutError,
        RateLimitError,
        InternalServerError,
        APIError as OpenAIAPIError,
    )

    DEFAULT_RETRY_EXCEPTIONS = (
        RateLimitError,
        APIConnectionError,
        APITimeoutError,
        InternalServerError,
    )
except ImportError:  # openai < 1 (unlikely if install() ran)
    from openai import error as openai_error  # type: ignore

    OpenAIAPIError = openai_error.APIError  # type: ignore
    DEFAULT_RETRY_EXCEPTIONS = (
        openai_error.RateLimitError,
        openai_error.ServiceUnavailableError,
        openai_error.APIError,
        openai_error.Timeout,
        openai_error.TryAgain,
    )


def _subprocess_env(env_extra=None):
    """Windows: child Python often uses cp1252 for stdout; emoji in logs then crash unless UTF-8 mode is on."""
    env = os.environ.copy()
    if sys.platform == "win32":
        env.setdefault("PYTHONUTF8", "1")
    if env_extra:
        env.update(env_extra)
    return env


# Child scripts log UTF-8 (emoji, etc.); Windows defaults to cp1252 → UnicodeDecodeError on the pipe.
_SUBPROCESS_STDOUT_KWARGS = {
    "stdout": subprocess.PIPE,
    "stderr": subprocess.STDOUT,
    "text": True,
    "encoding": "utf-8",
    "errors": "replace",
    "bufsize": 1,
}

# A.4-ARTICLES: install compat + retry on ChatCompletion before runpy (used by all runners, not only parallel).
# Top level must be column 0 in -c string.
_A4_ARTICLES_BOOTSTRAP = r"""import os, sys, time, random, socket, runpy
import openai
_root = os.path.abspath(os.path.join(os.getcwd(), ".."))
if _root not in sys.path:
    sys.path.insert(0, _root)
import openai_chat_compat
openai_chat_compat.install()

from openai import (
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
    InternalServerError,
    APIError,
)

_orig = openai.ChatCompletion.create
MAX_TRIES = int(os.getenv("OPENAI_RETRY_MAX_TRIES", "6"))
TIMEOUT = int(os.getenv("OPENAI_REQUEST_TIMEOUT", "180"))

def _retryable(e):
    if isinstance(e, (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError, socket.timeout)):
        return True
    if isinstance(e, APIError):
        code = getattr(e, "status_code", None) or getattr(e, "http_status", None)
        return code in (500, 502, 503, 504)
    return False

def _create_with_retry(*args, **kwargs):
    if "request_timeout" not in kwargs:
        kwargs["request_timeout"] = TIMEOUT

    for attempt in range(1, MAX_TRIES + 1):
        try:
            return _orig(*args, **kwargs)
        except Exception as e:
            if not _retryable(e):
                raise
            wait = min(60, (2 ** (attempt - 1)) + random.random())
            print(f"[OpenAI Retry {attempt}/{MAX_TRIES}] {type(e).__name__}: {e} | waiting {wait:.1f}s...", flush=True)
            time.sleep(wait)

    raise RuntimeError("OpenAI request failed after multiple retries.")

openai.ChatCompletion.create = _create_with_retry
runpy.run_path("A.4-ARTICLES.py", run_name="__main__")
"""


def _popen_pipeline_script(folder_abs: str, script: str, base_env: dict) -> subprocess.Popen:
    """Start a pipeline .py; A.4-ARTICLES uses bootstrap -c for OpenAI retry wrapper."""
    if script == "A.4-ARTICLES.py":
        cmd = [sys.executable, "-u", "-c", _A4_ARTICLES_BOOTSTRAP]
    else:
        cmd = [sys.executable, "-u", script]
    return subprocess.Popen(
        cmd,
        cwd=folder_abs,
        env=base_env,
        **_SUBPROCESS_STDOUT_KWARGS,
    )


def call_with_retries(
        func: Callable,
        *args,
        max_attempts: Optional[int] = None,  # None => إلى أن ينجح
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        jitter: float = 0.3,
        retry_on_exceptions: tuple = DEFAULT_RETRY_EXCEPTIONS,
        retry_for_statuses: tuple = (500, 502, 503, 504),
        **kwargs,
) -> Any:
    attempt = 0
    delay = initial_delay
    while True:
        attempt += 1
        try:
            logging.info(f"Attempt {attempt} calling {getattr(func, '__name__', str(func))} ...")
            return func(*args, **kwargs)
        except Exception as e:
            status = getattr(e, "status_code", None) or getattr(e, "http_status", None)
            is_retry_exc = isinstance(e, retry_on_exceptions) or (
                isinstance(e, OpenAIAPIError)
                and status is not None
                and status in retry_for_statuses
            )
            is_retry_status = (status in retry_for_statuses) if status is not None else False
            logging.warning(f"Attempt {attempt} failed: {type(e).__name__}: {e}")
            if not (is_retry_exc or is_retry_status):
                logging.error("Not configured to retry this error. Raising.")
                raise
            if (max_attempts is not None) and (attempt >= max_attempts):
                logging.error(f"Exceeded max_attempts={max_attempts}. Raising.")
                raise
            # backoff + jitter
            jitter_amt = delay * jitter
            sleep_s = max(0.1, min(delay + random.uniform(-jitter_amt, jitter_amt), max_delay))
            logging.info(f"Sleeping {sleep_s:.2f}s before next attempt.")
            time.sleep(sleep_s)
            delay = min(delay * backoff_factor, max_delay)


def chat_completion_with_retry(messages, model="gpt-4o-mini", **kwargs):
    return call_with_retries(
        openai.ChatCompletion.create,
        model=model,
        messages=messages,
        temperature=kwargs.pop("temperature", 0.7),
        max_attempts=None,  # عاود حتى ينجح
        **kwargs,
    )


# -------------------- Repo project discovery (unlimited) --------------------
_APP_ROOT = os.path.dirname(os.path.abspath(__file__))
_APP_CONFIG = os.path.join(_APP_ROOT, "config")
_SKIP_PROJECT_PARENTS = {".git", "ALL", "node_modules", "Save CSV", "__pycache__"}


def _natural_sort_key(name: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def _is_pipeline_project(name: str) -> bool:
    return os.path.isfile(os.path.join(_APP_ROOT, name, "A.1-START.py"))


def _load_app_projects_file() -> dict:
    path = os.path.join(_APP_CONFIG, "projects.json")
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _load_sites_file_app() -> dict:
    path = os.path.join(_APP_CONFIG, "sites.json")
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _use_json_sites() -> bool:
    s = _load_sites_file_app().get("sites")
    return isinstance(s, list) and len(s) > 0


def _pipeline_code_folder() -> str:
    return (str(_load_sites_file_app().get("pipeline_code_folder") or "A1-Pinterest_01").strip() or "A1-Pinterest_01")


def _safe_log_dom_id(s: str) -> str:
    x = re.sub(r"[^a-zA-Z0-9_-]+", "_", (s or "").strip().strip("_"))
    return x or "log"


def _site_row_public_title(s: dict) -> str:
    """Name shown in dashboard: A1-Pinterest_01, B1-Pinterest_51, …"""
    t = s.get("display_name") or s.get("name") or s.get("id") or "site"
    return str(t).strip()


def flat_run_units() -> list:
    """
    One entry per 'project' the UI runs: either one row per real folder, or
    (when config/sites.json has sites) one row per site using the same code folder.

    - label: title for headers + ?project= (e.g. A1-Pinterest_01)
    - log_id: safe id for #log_{log_id} and SSE routing (getElementById)
    - env: PINTEREST_SITE_ID stays the internal `id` from JSON
    """
    if not _use_json_sites():
        out = []
        for f in PROJECT_FOLDERS:
            out.append(
                {
                    "folder": f,
                    "label": f,
                    "log_id": _safe_log_dom_id(f),
                    "env": {},
                }
            )
        return out
    root = _pipeline_code_folder()
    root_path = os.path.join(_APP_ROOT, root)
    if not os.path.isdir(root_path):
        return [
            {
                "folder": f,
                "label": f,
                "log_id": _safe_log_dom_id(f),
                "env": {},
            }
            for f in PROJECT_FOLDERS
        ]
    out = []
    for s in _load_sites_file_app().get("sites", []):
        if not isinstance(s, dict):
            continue
        sid = str(s.get("id", "")).strip()
        if not sid:
            continue
        title = _site_row_public_title(s)
        log_id = (str(s.get("log_id", "")).strip() or _safe_log_dom_id(title) or _safe_log_dom_id(sid))
        out.append(
            {
                "folder": root,
                "label": title,
                "log_id": log_id,
                "env": {"PINTEREST_SITE_ID": sid},
            }
        )
    return out


def all_out_name_for_label(label: str) -> str:
    """ALL/<out_dir>/... — label can be display_name or id from sites.json."""
    if _use_json_sites():
        for s in _load_sites_file_app().get("sites", []):
            if not isinstance(s, dict):
                continue
            sid = str(s.get("id", "")).strip()
            stitle = _site_row_public_title(s) if s else ""
            if sid == label or stitle == label:
                return (s.get("out_dir") or f"{s.get('id')}-out").strip()  # type: ignore[union-attr]
    return f"{label}-out"


def _project_excel_path_by_out_dir(out_dir: str) -> str:
    """
    Unified pipeline workbook:
    - Prefer Recipes.xlsx (new single-file flow)
    - Fallback to images.xlsx for backward compatibility
    """
    base = os.path.join(os.getcwd(), "ALL", out_dir)
    recipes_path = os.path.join(base, "Recipes.xlsx")
    if os.path.exists(recipes_path):
        return recipes_path
    return os.path.join(base, "images.xlsx")


def _is_filled_excel_value(v) -> bool:
    if v is None:
        return False
    s = str(v).strip()
    if not s:
        return False
    return s.lower() != "nan"


def _json_for_inline_script(obj) -> str:
    """
    JSON safe to paste inside HTML <script>...</script>.
    Escapes '<' so '</script>' in data cannot terminate the script tag.
    """
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


_STARTS_TOTAL_CACHE = {"at": 0.0, "value": 0}
_PROJECT_STATS_CACHE: dict = {}
_GLOBAL_START_ROTATION = {"cursor": 0}


def _total_titles_in_starts_cached(ttl_seconds: float = 10.0) -> int:
    now = time.time()
    at = float(_STARTS_TOTAL_CACHE.get("at", 0.0) or 0.0)
    if now - at <= ttl_seconds:
        return int(_STARTS_TOTAL_CACHE.get("value", 0) or 0)

    starts_dir = os.path.join(_APP_ROOT, "STARTS")
    if not os.path.isdir(starts_dir):
        _STARTS_TOTAL_CACHE["at"] = now
        _STARTS_TOTAL_CACHE["value"] = 0
        return 0

    total = 0
    xlsx_files = [
        f
        for f in os.listdir(starts_dir)
        if f.lower().endswith(".xlsx")
        and not f.startswith("~$")
        and not f.startswith("._")
        and os.path.isfile(os.path.join(starts_dir, f))
    ]
    for fn in xlsx_files:
        fp = os.path.join(starts_dir, fn)
        try:
            for rec in _read_titles_from_start_workbook(fp):
                if str(rec.get("title", "")).strip():
                    total += 1
        except Exception:
            continue

    _STARTS_TOTAL_CACHE["at"] = now
    _STARTS_TOTAL_CACHE["value"] = int(total)
    return int(total)


def _project_column_stats(project_label: str) -> dict:
    out_dir = all_out_name_for_label(project_label)
    file_path = _project_excel_path_by_out_dir(out_dir)
    if not os.path.exists(file_path):
        return {"ok": False, "error": "excel_not_found", "file_path": file_path}
    try:
        mtime = float(os.path.getmtime(file_path))
    except OSError:
        mtime = 0.0
    global_total = _total_titles_in_starts_cached()
    ck = str(project_label)
    cached = _PROJECT_STATS_CACHE.get(ck)
    if (
        isinstance(cached, dict)
        and float(cached.get("mtime", -1.0)) == mtime
        and (time.time() - float(cached.get("at", 0.0))) <= 8.0
    ):
        return dict(cached.get("data") or {})
    try:
        wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
    except Exception as e:
        return {"ok": False, "error": f"open_failed: {e}", "file_path": file_path}
    try:
        sh = wb.active
        max_col = int(sh.max_column or 0)
        max_row = int(sh.max_row or 0)
        if max_col <= 0:
            return {"ok": True, "total_titles": 0, "columns": []}
        # Fast path: read headers + rows with values_only to avoid per-cell access cost.
        header_values = next(
            sh.iter_rows(min_row=1, max_row=1, min_col=1, max_col=max_col, values_only=True),
            tuple(),
        )
        headers = []
        for i in range(max_col):
            hv = header_values[i] if i < len(header_values) else None
            h = str(hv).strip() if hv is not None else f"Column_{i+1}"
            headers.append(h or f"Column_{i+1}")

        total_rows = max(0, max_row - 1)
        filled_counts = [0 for _ in range(max_col)]
        title_filled_rows = 0
        title_col_idx = -1
        for i, h in enumerate(headers):
            if str(h).strip().lower() == "title":
                title_col_idx = i
                break
        if total_rows > 0:
            for row_vals in sh.iter_rows(
                min_row=2,
                max_row=max_row,
                min_col=1,
                max_col=max_col,
                values_only=True,
            ):
                ln = len(row_vals)
                for i in range(max_col):
                    v = row_vals[i] if i < ln else None
                    if _is_filled_excel_value(v):
                        filled_counts[i] += 1
                if title_col_idx >= 0:
                    tv = row_vals[title_col_idx] if title_col_idx < ln else None
                    if _is_filled_excel_value(tv):
                        title_filled_rows += 1
        # Denominator is number of rows with a non-empty Title.
        total_for_stats = int(title_filled_rows if title_filled_rows > 0 else total_rows)
        # Show full pipeline coverage: expected columns first, then any extra columns from the sheet.
        expected_columns = [
            "Title",
            "Recipe",
            "Generated At",
            "Json Recipe",
            "Prompt",
            "Prompt Image Ingredients",
            "main_image",
            "image_1",
            "image_2",
            "image_3",
            "image_4",
            "statu",
            "error",
            "main_image_ingredients",
            "image_ing_1",
            "image_ing_2",
            "image_ing_3",
            "image_ing_4",
            "statu_ing",
            "article",
            "recipe_title_pin",
            "pinterest_title",
            "pinterest_description",
            "pinterest_keywords",
            "_yoast_wpseo_focuskw",
            "_yoast_wpseo_metadesc",
            "_yoast_wpseo_keywordsynonyms",
            "categories",
            "pinterest_image",
            "output_name",
        ]

        by_lower = {str(h).strip().lower(): i for i, h in enumerate(headers)}
        cols = []
        seen_lowers = set()

        for name in expected_columns:
            lk = name.strip().lower()
            seen_lowers.add(lk)
            if lk in by_lower:
                idx = by_lower[lk]
                cols.append({"name": headers[idx], "filled": int(filled_counts[idx]), "total": int(total_for_stats)})
            else:
                cols.append({"name": name, "filled": 0, "total": int(total_for_stats)})

        for i, name in enumerate(headers):
            lk = str(name).strip().lower()
            if lk in seen_lowers:
                continue
            cols.append({"name": name, "filled": int(filled_counts[i]), "total": int(total_for_stats)})
        data = {
            "ok": True,
            "file_path": file_path,
            "total_titles": int(total_rows),
            "global_total_titles": int(global_total),
            "columns": cols,
        }
        _PROJECT_STATS_CACHE[ck] = {
            "at": time.time(),
            "mtime": mtime,
            "global_total_titles": int(global_total),
            "data": data,
        }
        return data
    finally:
        wb.close()


def _project_column_details(project_label: str, column_name: str) -> dict:
    out_dir = all_out_name_for_label(project_label)
    file_path = _project_excel_path_by_out_dir(out_dir)
    if not os.path.exists(file_path):
        return {"ok": False, "error": "excel_not_found", "file_path": file_path}
    try:
        wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
    except Exception as e:
        return {"ok": False, "error": f"open_failed: {e}", "file_path": file_path}
    try:
        sh = wb.active
        max_col = int(sh.max_column or 0)
        max_row = int(sh.max_row or 0)
        if max_col <= 0:
            return {"ok": True, "column": column_name, "rows": [], "total_titles": 0}

        headers = []
        for c in range(1, max_col + 1):
            hv = sh.cell(row=1, column=c).value
            h = str(hv).strip() if hv is not None else f"Column_{c}"
            headers.append(h or f"Column_{c}")

        hmap = {str(h).strip().lower(): i + 1 for i, h in enumerate(headers)}
        req_col = hmap.get(str(column_name or "").strip().lower())
        title_col = hmap.get("title", 1)
        total_rows = max(0, max_row - 1)

        rows = []
        for r in range(2, max_row + 1):
            title_v = sh.cell(row=r, column=title_col).value if title_col else None
            title_s = str(title_v).strip() if title_v is not None else ""
            if req_col:
                val = sh.cell(row=r, column=req_col).value
                val_s = str(val).strip() if val is not None else ""
                filled = _is_filled_excel_value(val)
            else:
                val_s = ""
                filled = False
            rows.append(
                {
                    "row": r - 1,
                    "title": title_s,
                    "value": val_s,
                    "filled": bool(filled),
                }
            )

        return {
            "ok": True,
            "column": column_name,
            "column_exists": bool(req_col),
            "rows": rows,
            "total_titles": int(total_rows),
            "file_path": file_path,
        }
    finally:
        wb.close()


def _starts_dir_path() -> str:
    return os.path.join(_APP_ROOT, "STARTS")


def _safe_start_file_path(file_name: str) -> str:
    base = os.path.basename(str(file_name or "").strip())
    if not base:
        raise ValueError("Missing file name")
    if base != str(file_name or "").strip():
        raise ValueError("Invalid file name")
    if not base.lower().endswith(".xlsx"):
        raise ValueError("File must end with .xlsx")
    if base.startswith("~$"):
        raise ValueError("Temporary Excel files are not allowed")
    starts_dir = _starts_dir_path()
    os.makedirs(starts_dir, exist_ok=True)
    fp = os.path.abspath(os.path.join(starts_dir, base))
    if os.path.dirname(fp) != os.path.abspath(starts_dir):
        raise ValueError("Invalid file path")
    return fp


def _unique_headers(header_values: list) -> list:
    """
    Make duplicate Excel headers unique for JSON/table rendering.
    Example: used, used, used -> used, used.1, used.2
    """
    out = []
    counts = {}
    for raw in header_values:
        base = str(raw).strip() if raw is not None else ""
        if not base:
            base = "Column"
        n = int(counts.get(base, 0))
        if n <= 0:
            name = base
        else:
            name = f"{base}.{n}"
        counts[base] = n + 1
        out.append(name)
    return out


@app.route("/api/starts-files")
def api_starts_files():
    pattern = (request.args.get("pattern") or "START*.xlsx").strip() or "START*.xlsx"
    starts_dir = _starts_dir_path()
    if not os.path.isdir(starts_dir):
        return jsonify({"ok": True, "items": [], "starts_dir": starts_dir})
    items = []
    for fn in sorted(os.listdir(starts_dir), key=_natural_sort_key):
        if not fn.lower().endswith(".xlsx"):
            continue
        if fn.startswith("~$") or fn.startswith("._") or fn.startswith("_"):
            continue
        if not fnmatch.fnmatch(fn.lower(), pattern.lower()):
            continue
        fp = os.path.join(starts_dir, fn)
        row_count = 0
        title_count = 0
        try:
            wb = openpyxl.load_workbook(fp, data_only=True, read_only=True)
            try:
                sh = wb.active
                max_row = int(sh.max_row or 0)
                row_count = max(0, max_row - 1)
                max_col = int(sh.max_column or 0)
                title_col = 1
                for c in range(1, max_col + 1):
                    hv = sh.cell(row=1, column=c).value
                    if hv is not None and str(hv).strip().lower() == "title":
                        title_col = c
                        break
                for r in range(2, max_row + 1):
                    v = sh.cell(row=r, column=title_col).value
                    if _is_filled_excel_value(v):
                        title_count += 1
            finally:
                wb.close()
        except Exception:
            pass
        items.append(
            {
                "name": fn,
                "row_count": int(row_count),
                "title_count": int(title_count),
                "path": fp,
            }
        )
    return jsonify({"ok": True, "items": items, "starts_dir": starts_dir, "pattern": pattern})


@app.route("/api/starts-read")
def api_starts_read():
    file_name = (request.args.get("file") or "").strip()
    try:
        fp = _safe_start_file_path(file_name)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    if not os.path.isfile(fp):
        return jsonify({"ok": False, "error": "File not found", "file": file_name}), 404

    limit = int(request.args.get("limit", 200) or 200)
    offset = int(request.args.get("offset", 0) or 0)
    if limit < 1:
        limit = 1
    if limit > 2000:
        limit = 2000
    if offset < 0:
        offset = 0

    wb = openpyxl.load_workbook(fp, data_only=True, read_only=True)
    try:
        sh = wb.active
        max_col = int(sh.max_column or 0)
        max_row = int(sh.max_row or 0)
        raw_headers = []
        if max_col > 0:
            for c in range(1, max_col + 1):
                hv = sh.cell(row=1, column=c).value
                h = str(hv).strip() if hv is not None else f"Column_{c}"
                raw_headers.append(h or f"Column_{c}")
        headers = _unique_headers(raw_headers)

        start_excel_row = 2 + offset
        end_excel_row = min(max_row, start_excel_row + limit - 1)
        rows = []
        if max_row >= 2 and max_col > 0 and start_excel_row <= end_excel_row:
            for r in range(start_excel_row, end_excel_row + 1):
                row_obj = {"excel_row": int(r)}
                for c in range(1, max_col + 1):
                    key = headers[c - 1]
                    row_obj[key] = sh.cell(row=r, column=c).value
                rows.append(row_obj)
        return jsonify(
            {
                "ok": True,
                "file": file_name,
                "headers": headers,
                "rows": rows,
                "total_rows": max(0, max_row - 1),
                "offset": offset,
                "limit": limit,
            }
        )
    finally:
        wb.close()


@app.route("/api/starts-create", methods=["POST"])
def api_starts_create():
    data = request.get_json(force=True, silent=True) or {}
    file_name = str(data.get("file") or "").strip()
    headers = data.get("headers")
    if not isinstance(headers, list) or not headers:
        headers = ["Title"]
    hdrs = [str(h).strip() for h in headers if str(h or "").strip()]
    if not hdrs:
        hdrs = ["Title"]
    if not any(h.lower() == "title" for h in hdrs):
        hdrs.insert(0, "Title")
    try:
        fp = _safe_start_file_path(file_name)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    if os.path.exists(fp):
        return jsonify({"ok": False, "error": "File already exists", "file": file_name}), 409
    wb = openpyxl.Workbook()
    try:
        sh = wb.active
        sh.title = "Titles"
        for i, h in enumerate(hdrs, start=1):
            sh.cell(row=1, column=i, value=h)
        wb.save(fp)
    finally:
        wb.close()
    return jsonify({"ok": True, "file": file_name, "path": fp, "headers": hdrs})


@app.route("/api/starts-add-rows", methods=["POST"])
def api_starts_add_rows():
    data = request.get_json(force=True, silent=True) or {}
    file_name = str(data.get("file") or "").strip()
    titles = data.get("titles")
    rows = data.get("rows")
    try:
        fp = _safe_start_file_path(file_name)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    if not os.path.isfile(fp):
        return jsonify({"ok": False, "error": "File not found", "file": file_name}), 404

    normalized_rows = []
    if isinstance(titles, list):
        for t in titles:
            s = str(t or "").strip()
            if s:
                normalized_rows.append({"Title": s})
    if isinstance(rows, list):
        for one in rows:
            if isinstance(one, dict):
                obj = {}
                for k, v in one.items():
                    kk = str(k or "").strip()
                    if not kk:
                        continue
                    obj[kk] = v
                if obj:
                    normalized_rows.append(obj)
    if not normalized_rows:
        return jsonify({"ok": False, "error": "Provide titles[] or rows[]"}), 400

    wb = openpyxl.load_workbook(fp)
    try:
        sh = wb.active
        max_col = int(sh.max_column or 1)
        header_to_col = {}
        for c in range(1, max_col + 1):
            hv = sh.cell(row=1, column=c).value
            if hv is None:
                continue
            header_to_col[str(hv).strip().lower()] = c
        if "title" not in header_to_col:
            sh.cell(row=1, column=1, value="Title")
            header_to_col["title"] = 1
            if max_col < 1:
                max_col = 1

        def ensure_col(name: str) -> int:
            nonlocal max_col
            lk = str(name).strip().lower()
            c0 = header_to_col.get(lk)
            if c0:
                return c0
            max_col = max(max_col, int(sh.max_column or 1)) + 1
            sh.cell(row=1, column=max_col, value=name)
            header_to_col[lk] = max_col
            return max_col

        start_row = int(sh.max_row or 1) + 1
        for i, row_obj in enumerate(normalized_rows):
            rr = start_row + i
            for k, v in row_obj.items():
                col = ensure_col(k)
                sh.cell(row=rr, column=col, value=v)
        wb.save(fp)
        return jsonify(
            {
                "ok": True,
                "file": file_name,
                "added_rows": len(normalized_rows),
                "start_excel_row": int(start_row),
                "end_excel_row": int(start_row + len(normalized_rows) - 1),
            }
        )
    finally:
        wb.close()


@app.route("/api/starts-update-row", methods=["POST"])
def api_starts_update_row():
    data = request.get_json(force=True, silent=True) or {}
    file_name = str(data.get("file") or "").strip()
    excel_row = int(data.get("excel_row", 0) or 0)
    values = data.get("values")
    values_by_col = data.get("values_by_col")
    if excel_row < 2:
        return jsonify({"ok": False, "error": "excel_row must be >= 2"}), 400
    if (not isinstance(values, dict) or not values) and (not isinstance(values_by_col, dict) or not values_by_col):
        return jsonify({"ok": False, "error": "values or values_by_col is required"}), 400
    try:
        fp = _safe_start_file_path(file_name)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    if not os.path.isfile(fp):
        return jsonify({"ok": False, "error": "File not found", "file": file_name}), 404

    wb = openpyxl.load_workbook(fp)
    try:
        sh = wb.active
        max_col = int(sh.max_column or 1)
        header_to_col = {}
        for c in range(1, max_col + 1):
            hv = sh.cell(row=1, column=c).value
            if hv is None:
                continue
            header_to_col[str(hv).strip().lower()] = c

        def ensure_col(name: str) -> int:
            nonlocal max_col
            lk = str(name or "").strip().lower()
            if not lk:
                raise ValueError("Invalid column name")
            c0 = header_to_col.get(lk)
            if c0:
                return c0
            max_col = max(max_col, int(sh.max_column or 1)) + 1
            sh.cell(row=1, column=max_col, value=str(name).strip())
            header_to_col[lk] = max_col
            return max_col

        if isinstance(values_by_col, dict) and values_by_col:
            for k, v in values_by_col.items():
                try:
                    col = int(k)
                except (TypeError, ValueError):
                    continue
                if col < 1:
                    continue
                sh.cell(row=excel_row, column=col, value=v)
        if isinstance(values, dict) and values:
            for k, v in values.items():
                col = ensure_col(str(k))
                sh.cell(row=excel_row, column=col, value=v)
        wb.save(fp)
        return jsonify({"ok": True, "file": file_name, "excel_row": excel_row})
    finally:
        wb.close()


@app.route("/api/starts-delete-rows", methods=["POST"])
def api_starts_delete_rows():
    data = request.get_json(force=True, silent=True) or {}
    file_name = str(data.get("file") or "").strip()
    rows = data.get("excel_rows")
    if not isinstance(rows, list) or not rows:
        return jsonify({"ok": False, "error": "excel_rows list is required"}), 400
    try:
        fp = _safe_start_file_path(file_name)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    if not os.path.isfile(fp):
        return jsonify({"ok": False, "error": "File not found", "file": file_name}), 404

    to_delete = []
    for r in rows:
        try:
            rr = int(r)
        except (TypeError, ValueError):
            continue
        if rr >= 2:
            to_delete.append(rr)
    to_delete = sorted(set(to_delete), reverse=True)
    if not to_delete:
        return jsonify({"ok": False, "error": "No valid excel rows to delete"}), 400

    wb = openpyxl.load_workbook(fp)
    try:
        sh = wb.active
        deleted = 0
        max_row = int(sh.max_row or 1)
        for rr in to_delete:
            if 2 <= rr <= max_row:
                sh.delete_rows(rr, 1)
                deleted += 1
        wb.save(fp)
        return jsonify({"ok": True, "file": file_name, "deleted_rows": deleted})
    finally:
        wb.close()


@app.route("/api/starts-clear-file", methods=["POST"])
def api_starts_clear_file():
    data = request.get_json(force=True, silent=True) or {}
    file_name = str(data.get("file") or "").strip()
    try:
        fp = _safe_start_file_path(file_name)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    if not os.path.isfile(fp):
        return jsonify({"ok": False, "error": "File not found", "file": file_name}), 404

    wb = openpyxl.load_workbook(fp)
    try:
        sh = wb.active
        max_row = int(sh.max_row or 1)
        max_col = int(sh.max_column or 1)
        cleared = 0
        if max_row >= 2:
            for r in range(2, max_row + 1):
                for c in range(1, max_col + 1):
                    sh.cell(row=r, column=c, value=None)
                cleared += 1
        wb.save(fp)
        return jsonify({"ok": True, "file": file_name, "cleared_rows": int(cleared)})
    finally:
        wb.close()


@app.route("/api/recipes-files")
def api_recipes_files():
    items = []
    for u in flat_run_units():
        label = str(u.get("label", "") or "").strip()
        if not label:
            continue
        out_dir = all_out_name_for_label(label)
        file_path = _project_excel_path_by_out_dir(out_dir)
        exists = os.path.isfile(file_path)
        row_count = 0
        title_count = 0
        if exists:
            try:
                wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
                try:
                    sh = wb.active
                    max_row = int(sh.max_row or 0)
                    max_col = int(sh.max_column or 0)
                    row_count = max(0, max_row - 1)
                    title_col = 1
                    for c in range(1, max_col + 1):
                        hv = sh.cell(row=1, column=c).value
                        if hv is not None and str(hv).strip().lower() == "title":
                            title_col = c
                            break
                    for r in range(2, max_row + 1):
                        if _is_filled_excel_value(sh.cell(row=r, column=title_col).value):
                            title_count += 1
                finally:
                    wb.close()
            except Exception:
                pass
        items.append(
            {
                "project": label,
                "out_dir": out_dir,
                "file_path": file_path,
                "exists": bool(exists),
                "row_count": int(row_count),
                "title_count": int(title_count),
            }
        )
    return jsonify({"ok": True, "items": items})


@app.route("/api/recipes-read")
def api_recipes_read():
    project = (request.args.get("project") or "").strip()
    if not project or not is_allowed_project_label(project):
        return jsonify({"ok": False, "error": "Unknown project"}), 404
    out_dir = all_out_name_for_label(project)
    file_path = _project_excel_path_by_out_dir(out_dir)
    if not os.path.isfile(file_path):
        return jsonify({"ok": False, "error": "Recipes file not found", "project": project}), 404

    limit = int(request.args.get("limit", 200) or 200)
    offset = int(request.args.get("offset", 0) or 0)
    limit = max(1, min(limit, 2000))
    offset = max(0, offset)

    wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
    try:
        sh = wb.active
        max_col = int(sh.max_column or 0)
        max_row = int(sh.max_row or 0)
        raw_headers = []
        if max_col > 0:
            for c in range(1, max_col + 1):
                hv = sh.cell(row=1, column=c).value
                h = str(hv).strip() if hv is not None else f"Column_{c}"
                raw_headers.append(h or f"Column_{c}")
        headers = _unique_headers(raw_headers)

        rows = []
        start_excel_row = 2 + offset
        end_excel_row = min(max_row, start_excel_row + limit - 1)
        if max_col > 0 and max_row >= 2 and start_excel_row <= end_excel_row:
            for r in range(start_excel_row, end_excel_row + 1):
                row_obj = {"excel_row": int(r)}
                for c in range(1, max_col + 1):
                    row_obj[headers[c - 1]] = sh.cell(row=r, column=c).value
                rows.append(row_obj)
        return jsonify(
            {
                "ok": True,
                "project": project,
                "file_path": file_path,
                "headers": headers,
                "rows": rows,
                "total_rows": max(0, max_row - 1),
                "offset": offset,
                "limit": limit,
            }
        )
    finally:
        wb.close()


@app.route("/api/recipes-update-row", methods=["POST"])
def api_recipes_update_row():
    data = request.get_json(force=True, silent=True) or {}
    project = str(data.get("project") or "").strip()
    excel_row = int(data.get("excel_row", 0) or 0)
    values = data.get("values")
    values_by_col = data.get("values_by_col")
    if not project or not is_allowed_project_label(project):
        return jsonify({"ok": False, "error": "Unknown project"}), 404
    if excel_row < 2:
        return jsonify({"ok": False, "error": "excel_row must be >= 2"}), 400
    if (not isinstance(values, dict) or not values) and (not isinstance(values_by_col, dict) or not values_by_col):
        return jsonify({"ok": False, "error": "values or values_by_col is required"}), 400

    out_dir = all_out_name_for_label(project)
    file_path = _project_excel_path_by_out_dir(out_dir)
    if not os.path.isfile(file_path):
        return jsonify({"ok": False, "error": "Recipes file not found", "project": project}), 404

    wb = openpyxl.load_workbook(file_path)
    try:
        sh = wb.active
        max_col = int(sh.max_column or 1)
        header_to_col = {}
        for c in range(1, max_col + 1):
            hv = sh.cell(row=1, column=c).value
            if hv is None:
                continue
            header_to_col[str(hv).strip().lower()] = c

        def ensure_col(name: str) -> int:
            nonlocal max_col
            lk = str(name or "").strip().lower()
            if not lk:
                raise ValueError("Invalid column name")
            c0 = header_to_col.get(lk)
            if c0:
                return c0
            max_col = max(max_col, int(sh.max_column or 1)) + 1
            sh.cell(row=1, column=max_col, value=str(name).strip())
            header_to_col[lk] = max_col
            return max_col

        if isinstance(values_by_col, dict) and values_by_col:
            for k, v in values_by_col.items():
                try:
                    col = int(k)
                except (TypeError, ValueError):
                    continue
                if col < 1:
                    continue
                sh.cell(row=excel_row, column=col, value=v)
        if isinstance(values, dict) and values:
            for k, v in values.items():
                col = ensure_col(str(k))
                sh.cell(row=excel_row, column=col, value=v)
        wb.save(file_path)
        return jsonify({"ok": True, "project": project, "excel_row": excel_row})
    finally:
        wb.close()


@app.route("/api/recipes-delete-rows", methods=["POST"])
def api_recipes_delete_rows():
    data = request.get_json(force=True, silent=True) or {}
    project = str(data.get("project") or "").strip()
    rows = data.get("excel_rows")
    if not project or not is_allowed_project_label(project):
        return jsonify({"ok": False, "error": "Unknown project"}), 404
    if not isinstance(rows, list) or not rows:
        return jsonify({"ok": False, "error": "excel_rows list is required"}), 400

    out_dir = all_out_name_for_label(project)
    file_path = _project_excel_path_by_out_dir(out_dir)
    if not os.path.isfile(file_path):
        return jsonify({"ok": False, "error": "Recipes file not found", "project": project}), 404

    to_delete = []
    for r in rows:
        try:
            rr = int(r)
        except (TypeError, ValueError):
            continue
        if rr >= 2:
            to_delete.append(rr)
    to_delete = sorted(set(to_delete), reverse=True)
    if not to_delete:
        return jsonify({"ok": False, "error": "No valid excel rows to delete"}), 400

    wb = openpyxl.load_workbook(file_path)
    try:
        sh = wb.active
        deleted = 0
        max_row = int(sh.max_row or 1)
        for rr in to_delete:
            if 2 <= rr <= max_row:
                sh.delete_rows(rr, 1)
                deleted += 1
        wb.save(file_path)
        return jsonify({"ok": True, "project": project, "deleted_rows": deleted})
    finally:
        wb.close()


@app.route("/api/recipes-clear-file", methods=["POST"])
def api_recipes_clear_file():
    data = request.get_json(force=True, silent=True) or {}
    project = str(data.get("project") or "").strip()
    if not project or not is_allowed_project_label(project):
        return jsonify({"ok": False, "error": "Unknown project"}), 404

    out_dir = all_out_name_for_label(project)
    file_path = _project_excel_path_by_out_dir(out_dir)
    if not os.path.isfile(file_path):
        return jsonify({"ok": False, "error": "Recipes file not found", "project": project}), 404

    wb = openpyxl.load_workbook(file_path)
    try:
        sh = wb.active
        max_row = int(sh.max_row or 1)
        max_col = int(sh.max_column or 1)
        cleared = 0
        if max_row >= 2:
            for r in range(2, max_row + 1):
                for c in range(1, max_col + 1):
                    sh.cell(row=r, column=c, value=None)
                cleared += 1
        wb.save(file_path)
        return jsonify({"ok": True, "project": project, "cleared_rows": int(cleared)})
    finally:
        wb.close()


def _normalize_script_jobs(script_names) -> list:
    """
    (folder, script) | (folder, script, env) | 4- or 5-tuple
    -> (folder, script, env, log_id, line_label)
    log_id: SSE "folder" key and #log_{log_id}
    line_label: text in log lines
    """
    out = []
    for item in script_names:
        if len(item) == 2:
            f, s = item[0], item[1]
            out.append((f, s, {}, _safe_log_dom_id(f), f))
        elif len(item) == 3:
            f, s, e = item[0], item[1], item[2] or {}
            line = f"{f}[{e.get('PINTEREST_SITE_ID')}]" if e.get("PINTEREST_SITE_ID") else f
            out.append((f, s, e, _safe_log_dom_id(line), line))
        elif len(item) == 4:
            f, s, e, a = item[0], item[1], item[2] or {}, item[3]
            out.append((f, s, e, _safe_log_dom_id(a), a))
        else:
            f, s, e, log_id, line_label = item[0], item[1], item[2] or {}, item[3], item[4]
            out.append((f, s, e, log_id, line_label))
    return out


def jobs_for_script(script: str) -> list:
    return [
        (u["folder"], script, u.get("env") or {}, u["log_id"], u["label"])
        for u in flat_run_units()
    ]


def jobs_for_imagine_unit_group(units: list) -> list:
    return [
        (u["folder"], "A.3-IMAGINE.py", u.get("env") or {}, u["log_id"], u["label"])
        for u in (units or [])
    ]


def _unit_by_label(label: str):
    for u in flat_run_units():
        if u["label"] == label or u.get("log_id") == label:
            return u
    return None


def flat_ui_labels() -> list:
    return [u["label"] for u in flat_run_units()]


def is_allowed_project_label(label: str) -> bool:
    return any(u["label"] == label or u.get("log_id") == label for u in flat_run_units())


def _site_index_by_project_label(label: str) -> Optional[int]:
    """Index into config/sites.json sites[] for this dashboard project label (or log_id)."""
    d = _load_sites_file_app()
    if not isinstance(d, dict):
        return None
    sites = d.get("sites")
    if not isinstance(sites, list):
        return None
    u = _unit_by_label(label)
    if not u:
        return None
    e = u.get("env") or {}
    sid = str(e.get("PINTEREST_SITE_ID", "")).strip()
    for i, s in enumerate(sites):
        if not isinstance(s, dict):
            continue
        if sid and str(s.get("id", "")).strip() == sid:
            return i
        stitle = _site_row_public_title(s)
        if stitle == label or str(s.get("id", "")).strip() == label or str(s.get("log_id", "")).strip() == label:
            return i
    return None


SITES_FILE_PATH = os.path.join(_APP_CONFIG, "sites.json")

# Keys saved as plain strings in the form (optional empty = drop or keep secret, see _site_from_form)
_SITE_FORM_STRING_KEYS = (
    "id",
    "display_name",
    "out_dir",
    "start_file",
    "log_id",
    "prompts_dir",
    "openai_api_key",
    "openai_model",
    "useapi_token",
    "useapi_midjourney_channel",
    "r2_account_id",
    "r2_access_key_id",
    "r2_secret_access_key",
    "r2_bucket",
    "r2_public_base_url",
    "wordpress_url",
    "wordpress_user",
    "wordpress_app_password",
)

# If user leaves these blank in the form, keep previous file values (same as password UX)
_SITE_SECRET_REUSE_KEYS = (
    "openai_api_key",
    "useapi_token",
    "useapi_midjourney_channel",
    "r2_access_key_id",
    "r2_secret_access_key",
    "r2_account_id",
    "r2_bucket",
    "r2_public_base_url",
    "wordpress_app_password",
)


def _write_sites_doc(doc: dict) -> None:
    os.makedirs(os.path.dirname(SITES_FILE_PATH) or ".", exist_ok=True)
    txt = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    tmp = SITES_FILE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(txt)
    os.replace(tmp, SITES_FILE_PATH)


def _next_default_site_id(sites: list) -> str:
    nmax = 0
    for s in sites:
        if not isinstance(s, dict):
            continue
        sid = str(s.get("id", "")).strip()
        m = re.match(r"^p?(\d+)$", sid, re.I)
        if m:
            nmax = max(nmax, int(m.group(1)))
    for k in range(nmax + 1, 999):
        candidate = f"p{k:02d}"
        if not any(isinstance(s, dict) and str(s.get("id", "")).strip() == candidate for s in sites):
            return candidate
    return "p99"


def _site_from_form(form, i: int, old: Optional[dict]) -> dict:
    old = old or {}
    p = f"site_{i}_"
    s: dict = {}
    for k in _SITE_FORM_STRING_KEYS:
        v = (form.get(p + k) or "").strip()
        if v:
            s[k] = v
    if form.get(p + "no_shared_settings") == "1":
        s["no_shared_settings"] = True
    if form.get(p + "no_shared_prompts") == "1":
        s["no_shared_prompts"] = True
    t = (form.get(p + "settings_json") or "").strip()
    if t:
        try:
            s["settings"] = json.loads(t)
        except json.JSONDecodeError as e:
            raise ValueError(f"Site {i + 1} settings JSON: {e}") from e
    else:
        if "settings" in old:
            s["settings"] = old["settings"]
    t2 = (form.get(p + "prompts_json") or "").strip()
    if t2:
        try:
            s["prompts"] = json.loads(t2)
        except json.JSONDecodeError as e:
            raise ValueError(f"Site {i + 1} prompts JSON: {e}") from e
    else:
        if "prompts" in old:
            s["prompts"] = old["prompts"]
    for k in _SITE_SECRET_REUSE_KEYS:
        if s.get(k):
            continue
        if k in old and (old.get(k) is not None) and str(old.get(k) or "").strip() != "":
            s[k] = old[k]
    return s


def _default_new_site(sites: list) -> dict:
    sid = _next_default_site_id(sites)
    return {
        "id": sid,
        "display_name": f"New site ({sid})",
        "out_dir": f"{sid}-out",
        "wordpress_url": "https://",
        "wordpress_user": "",
        "wordpress_app_password": "",
    }


_A1_CONFIG_MODULES: dict = {}
_site_config_lock = threading.Lock()


def _a1_config_module_for_pipeline_folder(folder: str):
    p = os.path.join(_APP_ROOT, folder, "a1_config.py")
    if not os.path.isfile(p):
        return None
    if folder in _A1_CONFIG_MODULES:
        return _A1_CONFIG_MODULES[folder]
    mname = "a1_config__" + re.sub(r"[^a-zA-Z0-9_]+", "_", folder)
    spec = importlib.util.spec_from_file_location(mname, p)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    _A1_CONFIG_MODULES[folder] = mod
    return mod


def load_project_folders() -> list:
    """
    - If config/projects.json has non-empty "folders", use that order (only existing dirs).
    - Otherwise every direct subfolder that contains A.1-START.py, sorted naturally.
    """
    pc = _load_app_projects_file()
    explicit = pc.get("folders")
    if isinstance(explicit, list) and len(explicit) > 0:
        return [f for f in explicit if f and os.path.isdir(os.path.join(_APP_ROOT, f))]
    names: list = []
    for name in os.listdir(_APP_ROOT):
        if name in _SKIP_PROJECT_PARENTS or name.startswith("."):
            continue
        p = os.path.join(_APP_ROOT, name)
        if not os.path.isdir(p):
            continue
        if not _is_pipeline_project(name):
            continue
        names.append(name)
    names.sort(key=_natural_sort_key)
    return names


def _split_folder_groups(folders: list, n: int) -> list:
    """Split `folders` into n consecutive index ranges (n UI slots); sizes differ by at most 1."""
    L = len(folders)
    if n <= 0:
        return []
    if L == 0:
        return [[] for _ in range(n)]
    base, rem = divmod(L, n)
    out, start = [], 0
    for i in range(n):
        sz = base + (1 if i < rem else 0)
        out.append(folders[start : start + sz])
        start += sz
    return out


def _split_unit_groups(units: list, n: int) -> list:
    """Like _split_folder_groups but each chunk is a list of run-unit dicts."""
    L = len(units)
    if n <= 0:
        return []
    if L == 0:
        return [[] for _ in range(n)]
    base, rem = divmod(L, n)
    out, start = [], 0
    for i in range(n):
        sz = base + (1 if i < rem else 0)
        out.append(units[start : start + sz])
        start += sz
    return out


PROJECT_FOLDERS = load_project_folders()
if not PROJECT_FOLDERS and os.path.isdir(os.path.join(_APP_ROOT, "A1-Pinterest_01")):
    PROJECT_FOLDERS = ["A1-Pinterest_01"]

_PC = _load_app_projects_file()
_s2 = _PC.get("start2_folders")
if isinstance(_s2, list):
    START2_PROJECTS = [x for x in _s2 if isinstance(x, str) and x]
else:
    START2_PROJECTS = []


def _unit_in_start2_list(u: dict) -> bool:
    s2 = set(START2_PROJECTS)
    if not s2:
        return False
    if u.get("label") in s2 or u.get("log_id") in s2:
        return True
    sid = (u.get("env") or {}).get("PINTEREST_SITE_ID", "")
    return sid in s2


def jobs_for_start1_all_except_s2() -> list:
    o = []
    for u in flat_run_units():
        if _unit_in_start2_list(u):
            continue
        o.append(
            (u["folder"], "A.1-START.py", u.get("env") or {}, u["log_id"], u["label"])
        )
    return o


def _read_titles_from_start_workbook(path: str) -> list:
    titles: list = []
    try:
        wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    except Exception:
        return titles
    try:
        sh = wb.active
        title_col = 1
        used_col = 0
        max_col = max(1, int(sh.max_column or 1))
        for c in range(1, max_col + 1):
            hv = sh.cell(row=1, column=c).value
            if hv is None:
                continue
            hk = str(hv).strip().lower()
            if hk == "title":
                title_col = c
                break
        for c in range(1, max_col + 1):
            hv = sh.cell(row=1, column=c).value
            if hv is None:
                continue
            if str(hv).strip().lower() == "used":
                used_col = c
                break

        def _is_used_true(v) -> bool:
            if v is None:
                return False
            if isinstance(v, bool):
                return v is True
            if isinstance(v, (int, float)):
                return int(v) == 1
            s = str(v).strip().lower()
            if not s:
                return False
            return s in {"1", "true", "yes", "y", "used"}

        max_row = int(sh.max_row or 1)
        for r in range(2, max_row + 1):
            if used_col > 0 and _is_used_true(sh.cell(row=r, column=used_col).value):
                continue
            v = sh.cell(row=r, column=title_col).value
            if v is None:
                continue
            t = str(v).strip()
            if t:
                titles.append({"title": t, "source_row": r})
    finally:
        wb.close()
    return titles


def _write_start_usage_columns(starts_dir: str, xlsx_files: list, used_map: dict, stamp: str) -> None:
    """
    Update each STARTS workbook with run usage metadata:
    - used: 1 for assigned, 0 otherwise
    - used_at: timestamp for assigned rows
    - used_project: project label for assigned rows
    """
    for fn in xlsx_files:
        fp = os.path.join(starts_dir, fn)
        try:
            wb = openpyxl.load_workbook(fp)
        except Exception:
            continue
        try:
            sh = wb.active
            max_col = max(1, int(sh.max_column or 1))
            max_row = int(sh.max_row or 1)

            header_to_col = {}
            for c in range(1, max_col + 1):
                hv = sh.cell(row=1, column=c).value
                if hv is None:
                    continue
                header_to_col[str(hv).strip().lower()] = c

            def ensure_col(name: str) -> int:
                lk = name.strip().lower()
                c0 = header_to_col.get(lk)
                if c0:
                    return c0
                new_c = int(sh.max_column or 1) + 1
                sh.cell(row=1, column=new_c, value=name)
                header_to_col[lk] = new_c
                return new_c

            used_col = ensure_col("used")
            used_at_col = ensure_col("used_at")
            used_project_col = ensure_col("used_project")

            by_row = used_map.get(fn, {})
            for r in range(2, max_row + 1):
                rec = by_row.get(r)
                if rec:
                    sh.cell(row=r, column=used_col, value=1)
                    sh.cell(row=r, column=used_at_col, value=stamp)
                    sh.cell(row=r, column=used_project_col, value=rec.get("project", ""))
                else:
                    sh.cell(row=r, column=used_col, value=0)
                    sh.cell(row=r, column=used_at_col, value="")
                    sh.cell(row=r, column=used_project_col, value="")

            wb.save(fp)
        finally:
            wb.close()


def _build_global_start_runtime_jobs(base_jobs: list) -> tuple[list, dict]:
    """
    Build temp START files for this click only (no sites.json change):
    - Reads all titles from STARTS/*.xlsx
    - Distributes titles evenly over current jobs
    - Writes per-job runtime .xlsx and passes override through env
    - Writes one usage report with Used=true/false
    """
    jobs = list(base_jobs or [])
    starts_dir = os.path.join(_APP_ROOT, "STARTS")
    if not jobs:
        return jobs, {"mode": "no_jobs", "titles_total": 0}
    if not os.path.isdir(starts_dir):
        return jobs, {"mode": "missing_starts_folder", "titles_total": 0}

    xlsx_files = [
        f
        for f in os.listdir(starts_dir)
        if f.lower().endswith(".xlsx")
        and not f.startswith("~$")
        and not f.startswith("._")
        and not f.startswith("_")
        and os.path.isfile(os.path.join(starts_dir, f))
    ]
    xlsx_files.sort(key=_natural_sort_key)
    if not xlsx_files:
        return jobs, {"mode": "no_xlsx_files", "titles_total": 0}

    title_rows: list = []
    for fn in xlsx_files:
        fp = os.path.join(starts_dir, fn)
        for rec in _read_titles_from_start_workbook(fp):
            title_rows.append(
                {
                    "title": rec["title"],
                    "source_file": fn,
                    "source_row": int(rec.get("source_row", 0) or 0),
                }
            )

    if not title_rows:
        return jobs, {"mode": "no_titles_found", "titles_total": 0}

    n_jobs = len(jobs)
    chunks = [[] for _ in range(n_jobs)]
    start_idx = int(_GLOBAL_START_ROTATION.get("cursor", 0) or 0) % max(1, n_jobs)
    for i, row in enumerate(title_rows):
        chunks[(start_idx + i) % n_jobs].append(row)
    _GLOBAL_START_ROTATION["cursor"] = (start_idx + 1) % max(1, n_jobs)

    runtime_root = os.path.join(starts_dir, "_runtime_global_start")
    os.makedirs(runtime_root, exist_ok=True)
    for name in os.listdir(runtime_root):
        p = os.path.join(runtime_root, name)
        if os.path.isfile(p):
            try:
                os.remove(p)
            except OSError:
                pass

    patched_jobs = []
    usage_rows = []
    per_project_counts = {}
    for i, job in enumerate(jobs):
        folder, script, env, log_id, line_label = job
        rows = chunks[i]
        wb = openpyxl.Workbook()
        sh = wb.active
        sh.title = "Titles"
        sh.cell(row=1, column=1, value="Title")
        sh.cell(row=1, column=2, value="source_file")
        sh.cell(row=1, column=3, value="source_row")
        for r, item in enumerate(rows, start=2):
            sh.cell(row=r, column=1, value=item["title"])
            sh.cell(row=r, column=2, value=item.get("source_file", ""))
            sh.cell(row=r, column=3, value=int(item.get("source_row", 0) or 0))
            usage_rows.append(
                {
                    "Title": item["title"],
                    "Source File": item["source_file"],
                    "Assigned Project": line_label,
                    "Used": True,
                }
            )
        out_name = f"{i+1:04d}_{_safe_log_dom_id(str(line_label))}.xlsx"
        out_path = os.path.join(runtime_root, out_name)
        wb.save(out_path)
        wb.close()
        env2 = dict(env or {})
        env2["PINTEREST_START_FILE_OVERRIDE"] = out_path
        patched_jobs.append((folder, script, env2, log_id, line_label))
        per_project_counts[str(line_label)] = len(rows)

    used_titles = set()
    for c in chunks:
        for item in c:
            used_titles.add((item["title"], item["source_file"]))
    for item in title_rows:
        k = (item["title"], item["source_file"])
        if k in used_titles:
            continue
        usage_rows.append(
            {
                "Title": item["title"],
                "Source File": item["source_file"],
                "Assigned Project": "",
                "Used": False,
            }
        )

    usage_path = os.path.join(runtime_root, "_global_usage.xlsx")
    wb_u = openpyxl.Workbook()
    sh_u = wb_u.active
    sh_u.title = "Usage"
    headers = ["Title", "Source File", "Assigned Project", "Used"]
    for c, h in enumerate(headers, start=1):
        sh_u.cell(row=1, column=c, value=h)
    for r, row in enumerate(usage_rows, start=2):
        sh_u.cell(row=r, column=1, value=row["Title"])
        sh_u.cell(row=r, column=2, value=row["Source File"])
        sh_u.cell(row=r, column=3, value=row["Assigned Project"])
        sh_u.cell(row=r, column=4, value=row["Used"])
    wb_u.save(usage_path)
    wb_u.close()

    return patched_jobs, {
        "mode": "allocated",
        "titles_total": len(title_rows),
        "projects_total": n_jobs,
        "rotation_start_index": int(start_idx),
        "runtime_dir": runtime_root,
        "usage_file": usage_path,
        "per_project_counts": per_project_counts,
    }


def jobs_for_start2_only() -> list:
    return [
        (u["folder"], "A.1-START.py", u.get("env") or {}, u["log_id"], u["label"])
        for u in flat_run_units()
        if _unit_in_start2_list(u)
    ]


FLAT_UNITS = flat_run_units()
IMAGINE_NUM_GROUPS = int(_PC.get("imagine_num_groups", 17))
IMAGINE_SLOT_GROUPS = _split_unit_groups(FLAT_UNITS, IMAGINE_NUM_GROUPS)
# stream-imagine-group1 … = slots of sites (or folders) in order
IMAGINE_GROUP1 = IMAGINE_SLOT_GROUPS[0] if len(IMAGINE_SLOT_GROUPS) > 0 else []
IMAGINE_GROUP2 = IMAGINE_SLOT_GROUPS[1] if len(IMAGINE_SLOT_GROUPS) > 1 else []
IMAGINE_GROUP3 = IMAGINE_SLOT_GROUPS[2] if len(IMAGINE_SLOT_GROUPS) > 2 else []
IMAGINE_GROUP4 = IMAGINE_SLOT_GROUPS[3] if len(IMAGINE_SLOT_GROUPS) > 3 else []
IMAGINE_GROUP5 = IMAGINE_SLOT_GROUPS[4] if len(IMAGINE_SLOT_GROUPS) > 4 else []
IMAGINE_GROUP6 = IMAGINE_SLOT_GROUPS[5] if len(IMAGINE_SLOT_GROUPS) > 5 else []
IMAGINE_GROUP7 = IMAGINE_SLOT_GROUPS[6] if len(IMAGINE_SLOT_GROUPS) > 6 else []
IMAGINE_GROUP8 = IMAGINE_SLOT_GROUPS[7] if len(IMAGINE_SLOT_GROUPS) > 7 else []
IMAGINE_GROUP9 = IMAGINE_SLOT_GROUPS[8] if len(IMAGINE_SLOT_GROUPS) > 8 else []
IMAGINE_GROUP10 = IMAGINE_SLOT_GROUPS[9] if len(IMAGINE_SLOT_GROUPS) > 9 else []
IMAGINE_GROUP11 = IMAGINE_SLOT_GROUPS[10] if len(IMAGINE_SLOT_GROUPS) > 10 else []
IMAGINE_GROUP12 = IMAGINE_SLOT_GROUPS[11] if len(IMAGINE_SLOT_GROUPS) > 11 else []
IMAGINE_GROUP13 = IMAGINE_SLOT_GROUPS[12] if len(IMAGINE_SLOT_GROUPS) > 12 else []
IMAGINE_GROUP14 = IMAGINE_SLOT_GROUPS[13] if len(IMAGINE_SLOT_GROUPS) > 13 else []
IMAGINE_GROUP15 = IMAGINE_SLOT_GROUPS[14] if len(IMAGINE_SLOT_GROUPS) > 14 else []
IMAGINE_GROUP16 = IMAGINE_SLOT_GROUPS[15] if len(IMAGINE_SLOT_GROUPS) > 15 else []
IMAGINE_GROUP17 = IMAGINE_SLOT_GROUPS[16] if len(IMAGINE_SLOT_GROUPS) > 16 else []
_tuples = _PC.get("imagine_all_ranges")
if isinstance(_tuples, list) and _tuples:
    IMAGINE_ALL_RANGES = [tuple(x) for x in _tuples]  # type: ignore
else:
    _n = len(FLAT_UNITS)
    if _n <= 0:
        IMAGINE_ALL_RANGES = []
    elif _n == 1:
        IMAGINE_ALL_RANGES = [(1, 1)]
    else:
        _mid = (_n + 1) // 2
        IMAGINE_ALL_RANGES = [(1, _mid), (_mid + 1, _n)]

# -------------------- Global list to track running subprocesses --------------------
running_processes = []


# -------------------- 1) Concurrency / SSE Logging --------------------
def generate_log_parallel(script_names, env_extra=None):
    """
    Runs scripts concurrently in separate threads and yields SSE log lines.
    (No concurrency cap)
    script_names: list of 2- to 5-tuples; final form (folder, script, env, log_id, line_label).
    """
    q = queue.Queue()
    threads = []
    base_env = _subprocess_env(env_extra)
    jobs = _normalize_script_jobs(script_names)

    def run_process(folder, script, job_env, log_id, line_label):
        folder_abs = os.path.join(os.getcwd(), folder)
        script_path = os.path.join(folder_abs, script)
        if not os.path.exists(script_path):
            q.put(
                {
                    "folder": log_id,
                    "line": f"Script {line_label}/{script} not found.",
                }
            )
            return
        be = {**base_env, **(job_env or {})}
        q.put({"folder": log_id, "line": f"Running {line_label}/{script}..."})
        proc = _popen_pipeline_script(folder_abs, script, be)

        running_processes.append(proc)
        for line in proc.stdout:
            q.put({"folder": log_id, "line": line.rstrip()})
        proc.stdout.close()
        proc.wait()
        try:
            running_processes.remove(proc)
        except ValueError:
            pass
        q.put({"folder": log_id, "line": f"Finished {line_label}/{script}"})

    for folder, script, job_env, log_id, line_label in jobs:
        t = threading.Thread(
            target=run_process, args=(folder, script, job_env, log_id, line_label)
        )
        t.start()
        threads.append(t)

    while any(t.is_alive() for t in threads) or not q.empty():
        try:
            msg = q.get(timeout=0.1)
            yield f"data: {json.dumps(msg)}\n\n"
        except queue.Empty:
            pass

    yield "data: " + json.dumps({"folder": "all", "line": "Finished all processes."}) + "\n\n"

def generate_log_imagine_all_grouped(env_extra=None):
    """
    Run A.3-IMAGINE.py for ALL projects in GROUPS:
    - المجموعات كيتحددو ف IMAGINE_ALL_RANGES (1-based indices)
    - كل مجموعة كتخدم ف Thread بوحدها (Parallel)
    - داخل كل مجموعة المشاريع كيتخدمو واحد مور واحد (Sequential)
    """
    q = queue.Queue()
    base_env = _subprocess_env(env_extra)

    # نحضرو اللوائح ديال الفولدرات لكل مجموعة
    groups = []
    for i, (start_idx_1, end_idx_1) in enumerate(IMAGINE_ALL_RANGES, start=1):
        start_idx_1 = max(1, start_idx_1)
        end_idx_1 = min(len(FLAT_UNITS), end_idx_1)
        if start_idx_1 > end_idx_1:
            continue
        start0 = start_idx_1 - 1
        end0 = end_idx_1
        uchunk = FLAT_UNITS[start0:end0]
        if not uchunk:
            continue
        label = f"Group {i} ({start_idx_1}-{end_idx_1})"
        groups.append((label, uchunk))

    def run_group(label, units):
        for unit in units:
            script = "A.3-IMAGINE.py"
            folder = unit["folder"]
            job_env = {**base_env, **(unit.get("env") or {})}
            line_label = unit.get("label", folder)
            log_id = unit.get("log_id", _safe_log_dom_id(line_label))
            folder_abs = os.path.join(os.getcwd(), folder)
            script_path = os.path.join(folder_abs, script)
            if not os.path.exists(script_path):
                q.put(
                    {
                        "folder": log_id,
                        "line": f"[{label}] Script {line_label}/{script} not found.",
                    }
                )
                continue

            q.put({"folder": log_id, "line": f"[{label}] Running {line_label}/{script}..."})
            proc = _popen_pipeline_script(folder_abs, script, job_env)
            running_processes.append(proc)
            for line in proc.stdout:
                q.put({"folder": log_id, "line": f"[{label}] " + line.rstrip()})
            proc.stdout.close()
            proc.wait()
            try:
                running_processes.remove(proc)
            except ValueError:
                pass
            q.put(
                {
                    "folder": log_id,
                    "line": f"[{label}] Finished {line_label}/{script} (exit={proc.returncode}).",
                }
            )

        q.put({"folder": "all", "line": f"[{label}] Finished all projects in this group."})

    threads = []
    for label, folders in groups:
        t = threading.Thread(target=run_group, args=(label, folders), daemon=True)
        t.start()
        threads.append(t)

    # نخرجو اللوغات حتى يساليو جميع الثريدات
    while any(t.is_alive() for t in threads) or not q.empty():
        try:
            msg = q.get(timeout=0.1)
            yield "data: " + json.dumps(msg) + "\n\n"
        except queue.Empty:
            pass

    yield "data: " + json.dumps({"folder": "all", "line": "Finished all IMAGINE ALL groups."}) + "\n\n"


# -------------------- 2) Pool Runner (Fixed-size concurrency) --------------------
def generate_log_pool(script_names, max_concurrency=10, env_extra=None):
    """
    Fixed-size pool: keeps up to max_concurrency running; if one finishes or is SKIPPED,
    immediately starts the next.
    """
    q = queue.Queue()
    lock = threading.Lock()
    job_list = _normalize_script_jobs(script_names)
    scripts_iter = iter(job_list)
    active_threads = []
    base_env = _subprocess_env(env_extra)

    def run_process(folder, script, job_env, log_id, line_label):
        folder_abs = os.path.join(os.getcwd(), folder)
        script_path = os.path.join(folder_abs, script)
        if not os.path.exists(script_path):
            q.put(
                {
                    "folder": log_id,
                    "line": f"Script {line_label}/{script} not found (SKIPPED).",
                }
            )
        else:
            be = {**base_env, **(job_env or {})}
            q.put({"folder": log_id, "line": f"Running {line_label}/{script}..."})
            proc = _popen_pipeline_script(folder_abs, script, be)

            running_processes.append(proc)
            for line in proc.stdout:
                q.put({"folder": log_id, "line": line.rstrip()})
            proc.stdout.close()
            proc.wait()
            try:
                running_processes.remove(proc)
            except ValueError:
                pass
            q.put({"folder": log_id, "line": f"Finished {line_label}/{script}"})

        # refill slot
        with lock:
            try:
                nxt = next(scripts_iter)
                t = threading.Thread(
                    target=run_process,
                    args=(nxt[0], nxt[1], nxt[2], nxt[3], nxt[4]),
                )
                t.start()
                active_threads.append(t)
            except StopIteration:
                pass

    # prime pool
    for _ in range(min(max_concurrency, len(job_list))):
        try:
            f, s, e, lid, llab = next(scripts_iter)
            t = threading.Thread(target=run_process, args=(f, s, e, lid, llab))
            t.start()
            active_threads.append(t)
        except StopIteration:
            break

    # stream logs
    while any(t.is_alive() for t in active_threads) or not q.empty():
        try:
            msg = q.get(timeout=0.2)
            yield f"data: {json.dumps(msg)}\n\n"
        except queue.Empty:
            pass

    yield "data: " + json.dumps({"folder": "all", "line": "Finished all processes."}) + "\n\n"


# -------------------- 2b) BATCH Runner (Strict batches: wait for N to finish, then next N) --------------------
def generate_log_in_batches(script_names, batch_size=3, env_extra=None):
    """
    Runs scripts in strict batches of size `batch_size`.
    - Start at most `batch_size` processes.
    - Wait until ALL of them finish.
    - Then start the next batch.
    Streams all stdout/stderr lines via SSE.
    """
    q = queue.Queue()
    base_env = _subprocess_env(env_extra)
    job_list = _normalize_script_jobs(script_names)

    def run_process(folder, script, job_env, log_id, line_label):
        folder_abs = os.path.join(os.getcwd(), folder)
        script_path = os.path.join(folder_abs, script)
        if not os.path.exists(script_path):
            q.put(
                {
                    "folder": log_id,
                    "line": f"Script {line_label}/{script} not found.",
                }
            )
            return

        be = {**base_env, **(job_env or {})}
        q.put({"folder": log_id, "line": f"Running {line_label}/{script}..."})
        proc = _popen_pipeline_script(folder_abs, script, be)
        # stream output
        for line in proc.stdout:
            q.put({"folder": log_id, "line": line.rstrip()})
        proc.stdout.close()
        proc.wait()
        q.put(
            {
                "folder": log_id,
                "line": f"Finished {line_label}/{script} (exit={proc.returncode}).",
            }
        )

    # Helper: chunk list into batches
    def chunked(seq, n):
        for i in range(0, len(seq), n):
            yield seq[i:i + n]

    threads = []
    # Process by batches
    for batch in chunked(list(job_list), batch_size):
        # start a batch
        batch_threads = []
        for f, s, e, lid, llab in batch:
            t = threading.Thread(
                target=run_process, args=(f, s, e, lid, llab), daemon=True
            )
            t.start()
            batch_threads.append(t)
            threads.append(t)

        # While this batch is running, keep yielding queue messages
        while any(t.is_alive() for t in batch_threads):
            try:
                msg = q.get(timeout=0.1)
                yield f"data: {json.dumps(msg)}\n\n"
            except queue.Empty:
                pass
        # drain remaining queue lines for this batch
        while True:
            try:
                msg = q.get_nowait()
                yield f"data: {json.dumps(msg)}\n\n"
            except queue.Empty:
                break

    # ensure all threads done
    for t in threads:
        t.join(timeout=0.1)

    yield "data: " + json.dumps({"folder": "all", "line": "Finished all processes (batched)."}) + "\n\n"


# -------------------- 3) Streaming Endpoints --------------------

@app.route("/stream-all-start")
def stream_all_start():
    jobs, info = _build_global_start_runtime_jobs(jobs_for_start1_all_except_s2())
    if info.get("mode") == "allocated":
        app.logger.info(
            "Global START allocation: %s titles for %s projects. Usage report: %s",
            info.get("titles_total"),
            info.get("projects_total"),
            info.get("usage_file"),
        )
    return Response(
        generate_log_parallel(jobs), mimetype="text/event-stream"
    )



@app.route("/stream-all-prompt")
def stream_all_prompt():
    return Response(
        generate_log_parallel(jobs_for_script("A.2-PROMPT.py")),
        mimetype="text/event-stream",
    )

@app.route("/stream-all-json")
def stream_all_json():
    scripts_to_run = jobs_for_script("A.2-JSON.py")

    # باش نعطيك Done X/Y
    total = len(scripts_to_run)

    def gen():
        done = 0
        for chunk in generate_log_in_batches(scripts_to_run, batch_size=5):
            # chunk = "data: {...}\n\n" أو "data: {...}\n\n"
            # كنحسبو "Finished ..." باش نعرفو شحال تسالا
            if '"line": "Finished ' in chunk:
                done += 1
            yield chunk

        yield "data: " + json.dumps({"folder": "all", "line": f"JSON Done {done}/{total}"}) + "\n\n"

    return Response(gen(), mimetype="text/event-stream")

@app.route("/stream-imagine-all")
def stream_imagine_all():
    """
    IMAGINE ALL:
    - كيشغّل A.3-IMAGINE.py على جميع المشاريع ولكن بالمجموعات:
      * كل مجموعة (range) كتخدم ف Thread بوحدها (Parallel).
      * داخل كل مجموعة المشاريع كيتخدمو واحد مور واحد (Sequential).
    - المجموعات كيتحددو من IMAGINE_ALL_RANGES.
    """
    return Response(
        generate_log_imagine_all_grouped(),
        mimetype="text/event-stream"
    )



@app.route("/stream-imagine-group1")
def stream_imagine_group1():
    return Response(
        generate_log_parallel(jobs_for_imagine_unit_group(IMAGINE_GROUP1)),
        mimetype="text/event-stream",
    )


@app.route("/stream-imagine-group2")
def stream_imagine_group2():
    return Response(
        generate_log_parallel(jobs_for_imagine_unit_group(IMAGINE_GROUP2)),
        mimetype="text/event-stream",
    )


@app.route("/stream-imagine-group3")
def stream_imagine_group3():
    return Response(
        generate_log_parallel(jobs_for_imagine_unit_group(IMAGINE_GROUP3)),
        mimetype="text/event-stream",
    )


@app.route("/stream-imagine-group4")
def stream_imagine_group4():
    return Response(
        generate_log_parallel(jobs_for_imagine_unit_group(IMAGINE_GROUP4)),
        mimetype="text/event-stream",
    )


@app.route("/stream-imagine-group5")
def stream_imagine_group5():
    return Response(
        generate_log_parallel(jobs_for_imagine_unit_group(IMAGINE_GROUP5)),
        mimetype="text/event-stream",
    )


@app.route("/stream-imagine-group6")
def stream_imagine_group6():
    return Response(
        generate_log_parallel(jobs_for_imagine_unit_group(IMAGINE_GROUP6)),
        mimetype="text/event-stream",
    )


@app.route("/stream-imagine-group7")
def stream_imagine_group7():
    return Response(
        generate_log_parallel(jobs_for_imagine_unit_group(IMAGINE_GROUP7)),
        mimetype="text/event-stream",
    )


@app.route("/stream-imagine-group8")
def stream_imagine_group8():
    return Response(
        generate_log_parallel(jobs_for_imagine_unit_group(IMAGINE_GROUP8)),
        mimetype="text/event-stream",
    )


@app.route("/stream-imagine-group9")
def stream_imagine_group9():
    return Response(
        generate_log_parallel(jobs_for_imagine_unit_group(IMAGINE_GROUP9)),
        mimetype="text/event-stream",
    )


@app.route("/stream-imagine-group10")
def stream_imagine_group10():
    return Response(
        generate_log_parallel(jobs_for_imagine_unit_group(IMAGINE_GROUP10)),
        mimetype="text/event-stream",
    )


@app.route("/stream-imagine-group11")
def stream_imagine_group11():
    return Response(
        generate_log_parallel(jobs_for_imagine_unit_group(IMAGINE_GROUP11)),
        mimetype="text/event-stream",
    )


@app.route("/stream-imagine-group12")
def stream_imagine_group12():
    return Response(
        generate_log_parallel(jobs_for_imagine_unit_group(IMAGINE_GROUP12)),
        mimetype="text/event-stream",
    )


@app.route("/stream-imagine-group13")
def stream_imagine_group13():
    return Response(
        generate_log_parallel(jobs_for_imagine_unit_group(IMAGINE_GROUP13)),
        mimetype="text/event-stream",
    )


@app.route("/stream-imagine-group14")
def stream_imagine_group14():
    return Response(
        generate_log_parallel(jobs_for_imagine_unit_group(IMAGINE_GROUP14)),
        mimetype="text/event-stream",
    )


@app.route("/stream-imagine-group15")
def stream_imagine_group15():
    return Response(
        generate_log_parallel(jobs_for_imagine_unit_group(IMAGINE_GROUP15)),
        mimetype="text/event-stream",
    )


@app.route("/stream-imagine-group16")
def stream_imagine_group16():
    return Response(
        generate_log_parallel(jobs_for_imagine_unit_group(IMAGINE_GROUP16)),
        mimetype="text/event-stream",
    )


@app.route("/stream-imagine-group17")
def stream_imagine_group17():
    return Response(
        generate_log_parallel(jobs_for_imagine_unit_group(IMAGINE_GROUP17)),
        mimetype="text/event-stream",
    )


# -------------------- UPDATED: Articles (pool 10 ب 10) --------------------
@app.route("/stream-all-article")
def stream_all_article():
    scripts_to_run = jobs_for_script("A.4-ARTICLES.py")
    return Response(
        generate_log_pool(scripts_to_run, max_concurrency=10),
        mimetype="text/event-stream"
    )


# -------------------- UPDATED: PIN DATA (pool 10 ب 10) + Skip Existing Rows flag --------------------
@app.route("/stream-all-pin-data")
def stream_all_pin_data():
    """
    كنشغل A.5-PIN DATA.py لكل مشروع، ومعاه env PIN_SKIP_EXISTING=1
    باش السكريبت ديال PIN DATA يتخطّى الصفوف العامرة وميرجعش يعاود لها.
    خاصك تزاد سنيبت فـ A.5-PIN DATA.py (أسفل) باش يفعل هاد السلوك.
    """
    scripts_to_run = jobs_for_script("A.5-PIN DATA.py")
    env_extra = {"PIN_SKIP_EXISTING": "1"}
    return Response(
        generate_log_pool(scripts_to_run, max_concurrency=10, env_extra=env_extra),
        mimetype="text/event-stream"
    )


@app.route("/stream-all-pin-image")
def stream_all_pin_image():
    BATCH_SIZE = 5
    _units = flat_run_units()
    total = len(_units)

    @stream_with_context
    def stream():
        done = 0
        yield f"data: 🚀 Starting Pin Image for {total} folders (batch={BATCH_SIZE})\n\n"

        for i in range(0, total, BATCH_SIZE):
            batch_u = _units[i : i + BATCH_SIZE]
            start = i + 1
            end = i + len(batch_u)

            yield f"data: 🚀 Batch {start}-{end} / {total}\n\n"

            scripts_to_run = [
                (u["folder"], "A.6-PIN IMAGES.py", u.get("env") or {}, u["log_id"], u["label"])
                for u in batch_u
            ]

            # run this batch
            for line in generate_log_parallel(scripts_to_run):
                # ✅ مهم: فلتر رسالة النهاية ديال generate_log_parallel باش مايتسدّش SSE وسط الخدمة
                if '"folder": "all"' in line and "Finished all processes." in line:
                    continue
                yield line

            done += len(batch_u)
            yield f"data: ✅ Done {done}/{total}\n\n"

        # ✅ رسالة نهاية واحدة فقط فالأخير
        yield "data: 🎉 ALL PIN IMAGE DONE\n\n"
        yield 'data: {"folder":"all","line":"Finished all processes."}\n\n'

    return Response(
        stream(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )



@app.route("/stream-all-pin-bulk")
def stream_all_pin_bulk():
    return Response(
        generate_log_parallel(jobs_for_script("A.8-PIN BULK.py")),
        mimetype="text/event-stream",
    )


# -------------------- Stream Endpoint for START2 --------------------
@app.route("/stream_start2")
def stream_start2():
    return Response(
        generate_log_parallel(jobs_for_start2_only()), mimetype="text/event-stream"
    )


# -------------------- Stream Endpoint for Single Project Actions --------------------
@app.route("/stream-single")
def stream_single():
    """
    Re-trigger a specific action for one project.
    ?project=<project>&action=<action>
    """
    project = request.args.get("project")
    action = request.args.get("action")
    if not project or not action:
        return Response("Missing parameters", status=400)

    action_to_script = {
        "start": "A.1-START.py",
        "json": "A.2-JSON.py",
        "prompt": "A.2-PROMPT.py",
        "imagine": "A.3-IMAGINE.py",
        "article": "A.4-ARTICLES.py",
        "pin_data": "A.5-PIN DATA.py",
        "pin_image": "A.6-PIN IMAGES.py",
        "wp_upload": "A.7-WP UPLOAD.py",
        "pin_bulk": "A.8-PIN BULK.py",
        "start2": "A.1-START.py"
    }
    script = action_to_script.get(action)
    if not script:
        return Response("Invalid action", status=400)

    u = _unit_by_label(project)
    if not u:
        return Response("Unknown project", status=404)
    return Response(
        generate_log_parallel(
            [
                (
                    u["folder"],
                    script,
                    u.get("env") or {},
                    u["log_id"],
                    u["label"],
                )
            ]
        ),
        mimetype="text/event-stream",
    )


@app.route("/api/site-config")
def api_site_config():
    """
    Merged config for one dashboard log card (same as subprocess would see for PINTEREST_SITE_ID).
    Query: ?project=<label or log_id> — same value as the START / stream-single buttons.
    """
    project = (request.args.get("project") or "").strip()
    if not project or not is_allowed_project_label(project):
        return jsonify({"error": "Unknown project"}), 404
    u = _unit_by_label(project)
    if not u:
        return jsonify({"error": "Unknown project"}), 404
    folder = (u.get("folder") or "").strip() or "A1-Pinterest_01"
    with _site_config_lock:
        old_sid = os.environ.get("PINTEREST_SITE_ID")
        e = u.get("env") or {}
        try:
            if "PINTEREST_SITE_ID" in e:
                os.environ["PINTEREST_SITE_ID"] = str(e["PINTEREST_SITE_ID"])
            else:
                os.environ.pop("PINTEREST_SITE_ID", None)
            mod = _a1_config_module_for_pipeline_folder(folder)
            if mod is None or not hasattr(mod, "resolved_runtime_snapshot"):
                return jsonify({"error": "a1_config not found in " + folder}), 500
            snap = mod.resolved_runtime_snapshot()
            snap["unit"] = {
                "folder": folder,
                "label": u.get("label"),
                "log_id": u.get("log_id"),
                "subprocess_env": e,
            }
            return jsonify(snap)
        finally:
            if old_sid is not None:
                os.environ["PINTEREST_SITE_ID"] = old_sid
            else:
                os.environ.pop("PINTEREST_SITE_ID", None)


@app.route("/api/site-editor", methods=["GET", "POST"])
def api_site_editor():
    """
    GET: merged snapshot + raw sites.json row for this dashboard project (for Info / edit modal).
    POST JSON { "project": "<label>", "raw_site": { ... } } — writes that row to config/sites.json.
    """
    if request.method == "GET":
        project = (request.args.get("project") or "").strip()
        if not project or not is_allowed_project_label(project):
            return jsonify({"error": "Unknown project"}), 404
        u = _unit_by_label(project)
        if not u:
            return jsonify({"error": "Unknown project"}), 404
        folder = (u.get("folder") or "").strip() or "A1-Pinterest_01"
        idx = _site_index_by_project_label(project)
        raw_site = None
        if idx is not None:
            sites = _load_sites_file_app().get("sites") or []
            if 0 <= idx < len(sites) and isinstance(sites[idx], dict):
                raw_site = copy.deepcopy(sites[idx])
        with _site_config_lock:
            old_sid = os.environ.get("PINTEREST_SITE_ID")
            e = u.get("env") or {}
            try:
                if raw_site and str(raw_site.get("id", "")).strip():
                    os.environ["PINTEREST_SITE_ID"] = str(raw_site.get("id")).strip()
                elif "PINTEREST_SITE_ID" in e:
                    os.environ["PINTEREST_SITE_ID"] = str(e["PINTEREST_SITE_ID"])
                else:
                    os.environ.pop("PINTEREST_SITE_ID", None)
                mod = _a1_config_module_for_pipeline_folder(folder)
                if mod is None or not hasattr(mod, "resolved_runtime_snapshot"):
                    return jsonify({"error": "a1_config not found in " + folder}), 500
                snap = mod.resolved_runtime_snapshot()
            finally:
                if old_sid is not None:
                    os.environ["PINTEREST_SITE_ID"] = old_sid
                else:
                    os.environ.pop("PINTEREST_SITE_ID", None)
        return jsonify(
            {
                "project": project,
                "snapshot": snap,
                "raw_site": raw_site,
                "can_edit_sites_row": raw_site is not None,
            }
        )
    # POST
    data = request.get_json(force=True, silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Send JSON: { project, raw_site }"}), 400
    project = (data.get("project") or "").strip()
    raw_site = data.get("raw_site")
    if not project or not is_allowed_project_label(project):
        return jsonify({"error": "Unknown project"}), 404
    if not isinstance(raw_site, dict):
        return jsonify({"error": "raw_site must be a JSON object"}), 400
    if not str(raw_site.get("id", "")).strip():
        return jsonify({"error": "raw_site.id is required"}), 400
    doc = _load_sites_file_app()
    if not isinstance(doc, dict):
        return jsonify({"error": "sites.json is invalid"}), 500
    sites = doc.get("sites")
    if not isinstance(sites, list):
        return jsonify({"error": "sites.json has no sites array"}), 500
    idx = _site_index_by_project_label(project)
    if idx is None or idx >= len(sites):
        return jsonify({"error": "Project row not found in sites.json"}), 404
    old_row = sites[idx] if isinstance(sites[idx], dict) else {}
    merged = copy.deepcopy(raw_site) if isinstance(raw_site, dict) else {}
    for k in _SITE_SECRET_REUSE_KEYS:
        v = (merged.get(k) if k in merged else None)
        t = (str(v).strip() if v is not None else "")
        if t:
            continue
        if k in old_row and (old_row.get(k) is not None) and str(old_row.get(k) or "").strip() != "":
            merged[k] = old_row[k]
    sites[idx] = merged
    doc["sites"] = sites
    doc.setdefault("pipeline_code_folder", "A1-Pinterest_01")
    try:
        _write_sites_doc(doc)
    except OSError as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"ok": True, "message": "config/sites.json updated for this project row."})


@app.route("/api/project-stats")
def api_project_stats():
    project = (request.args.get("project") or "").strip()
    if not project or not is_allowed_project_label(project):
        return jsonify({"ok": False, "error": "Unknown project"}), 404
    s = _project_column_stats(project)
    s["project"] = project
    return jsonify(s)


@app.route("/api/projects-stats")
def api_projects_stats():
    items = []
    for u in flat_run_units():
        label = str(u.get("label", "") or "").strip()
        log_id = str(u.get("log_id", "") or "").strip()
        if not label or not log_id:
            continue
        s = _project_column_stats(label)
        s["project"] = label
        s["log_id"] = log_id
        items.append(s)
    return jsonify({"ok": True, "items": items})


@app.route("/api/project-column-details")
def api_project_column_details():
    project = (request.args.get("project") or "").strip()
    column = (request.args.get("column") or "").strip()
    if not project or not is_allowed_project_label(project):
        return jsonify({"ok": False, "error": "Unknown project"}), 404
    if not column:
        return jsonify({"ok": False, "error": "Missing column"}), 400
    d = _project_column_details(project, column)
    d["project"] = project
    return jsonify(d)


@app.route("/manage_sites", methods=["GET", "POST"])
def manage_sites():
    if request.method == "POST":
        act = (request.form.get("action") or "save").strip()
        if act == "add":
            data = _load_sites_file_app()
            if not isinstance(data, dict):
                data = {}
            sites = data.get("sites")
            if not isinstance(sites, list):
                sites = []
            sites.append(_default_new_site(sites))
            data["sites"] = sites
            data["pipeline_code_folder"] = (str(data.get("pipeline_code_folder") or "A1-Pinterest_01").strip() or "A1-Pinterest_01")
            try:
                _write_sites_doc(data)
            except OSError as e:
                flash("Could not save sites.json: " + str(e), "error")
                return redirect(url_for("manage_sites"))
            flash("New project added. Edit fields below, then save all.", "success")
            return redirect(url_for("manage_sites"))
        if act == "delete":
            did = (request.form.get("site_id") or "").strip()
            if did:
                data = _load_sites_file_app()
                sites = [s for s in (data.get("sites") or []) if isinstance(s, dict) and str(s.get("id", "")) != did]
                data["sites"] = sites
                data.setdefault("pipeline_code_folder", "A1-Pinterest_01")
                try:
                    _write_sites_doc(data)
                except OSError as e:
                    flash("Could not save sites.json: " + str(e), "error")
                    return redirect(url_for("manage_sites"))
                flash("Removed project " + did, "success")
            return redirect(url_for("manage_sites"))
        # full save
        n = int(request.form.get("site_count", 0) or 0)
        pl = (request.form.get("pipeline_code_folder") or "").strip() or "A1-Pinterest_01"
        old_list = _load_sites_file_app().get("sites") or []
        if not isinstance(old_list, list):
            old_list = []
        old_by_id: Dict[str, dict] = {
            str(s.get("id")): s for s in old_list if isinstance(s, dict) and s.get("id")
        }
        seen: set = set()
        sites_out: List[dict] = []
        for i in range(n):
            sub_id = (request.form.get(f"site_{i}_id") or "").strip()
            old = old_by_id.get(sub_id, {})
            try:
                one = _site_from_form(request.form, i, old)
            except ValueError as e:
                flash(str(e), "error")
                return redirect(url_for("manage_sites"))
            if not (one or {}).get("id"):
                continue
            if one["id"] in seen:
                flash("Duplicate site id: " + str(one["id"]), "error")
                return redirect(url_for("manage_sites"))
            seen.add(one["id"])
            sites_out.append(one)
        if not sites_out:
            flash("At least one site with an id is required.", "error")
            return redirect(url_for("manage_sites"))
        doc = {"pipeline_code_folder": pl, "sites": sites_out}
        try:
            _write_sites_doc(doc)
        except OSError as e:
            flash("Could not write config/sites.json: " + str(e), "error")
            return redirect(url_for("manage_sites"))
        flash(
            "config/sites.json saved. Refresh the dashboard; restart the app if IMAGINE group buttons should match the new site list.",
            "success",
        )
        return redirect(url_for("manage_sites"))
    d = _load_sites_file_app()
    if not isinstance(d, dict) or "sites" not in d or not isinstance(d.get("sites"), list):
        d = {"pipeline_code_folder": "A1-Pinterest_01", "sites": []}
    d.setdefault("pipeline_code_folder", "A1-Pinterest_01")
    sites_view: List[dict] = []
    for s in d.get("sites") or []:
        if not isinstance(s, dict):
            continue
        sv = dict(s)
        st = s.get("settings")
        sv["_settings_json"] = (
            json.dumps(st, ensure_ascii=False, indent=2) if isinstance(st, (dict, list)) else ""
        )
        pr = s.get("prompts")
        sv["_prompts_json"] = (
            json.dumps(pr, ensure_ascii=False, indent=2) if isinstance(pr, (dict, list)) else ""
        )
        sites_view.append(sv)
    return render_template(
        "manage_sites.html",
        data=d,
        sites_view=sites_view,
        site_count=len(sites_view),
    )


@app.route("/manage_starts")
def manage_starts():
    return render_template("manage_starts.html")


@app.route("/manage_recipes")
def manage_recipes():
    return render_template("manage_recipes.html")


# -------------------- WP UPLOAD (pool 10 ب 10) --------------------
@app.route("/stream-all-wp-upload")
def stream_all_wp_upload():
    return Response(
        generate_log_pool(jobs_for_script("A.7-WP UPLOAD.py"), max_concurrency=10),
        mimetype="text/event-stream"
    )

# -------------------- Endpoint to Stop Running Scripts --------------------
@app.route("/stop_scripts", methods=["POST"])
def stop_scripts():
    global running_processes
    for proc in running_processes[:]:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    running_processes.clear()
    return jsonify({"status": "success", "message": "All running scripts have been stopped."})


# -------------------- 3) Delete 'ALL' Folder --------------------
@app.route("/delete-all-folder", methods=["POST"])
def delete_all_folder():
    folder_path = os.path.join(os.getcwd(), "ALL")
    if os.path.exists(folder_path):
        try:
            shutil.rmtree(folder_path)
            return "<h1>'ALL' folder deleted successfully.</h1><a href='/'>Back</a>"
        except Exception as e:
            return f"<h1>Error deleting folder: {e}</h1><a href='/'>Back</a>"
    else:
        return "<h1>'ALL' folder not found.</h1><a href='/'>Back</a>"


# ------------------------------------------------------------------
# 4) Bulk Titles Upload (OpenAI line-by-line, NO JSON from OpenAI)
# ------------------------------------------------------------------

def filter_only_recipes_with_openai(raw_titles):
    """
    Keep ONLY the lines that are actual cooking recipe titles.
    - Do NOT add, rewrite, or translate any titles.
    - Output must be a subset of the INPUT lines (verbatim), one per line.
    - Remove empty lines, URLs, hashtags, @mentions, emails, and generic non-recipe lines.
    - Deduplicate while preserving original order.
    """
    # Quick pre-filter (regex) to remove obvious junk before sending to OpenAI
    import re
    junk_patterns = [
        r'https?://\S+',
        r'www\.\S+',
        r'\b(?:privacy|terms|policy|cookies?|login|signin|register|subscribe|newsletter|about|contact|homepage|copyright)\b',
        r'#\w+',
        r'@\w+',
        r'\b(?:ingredients?|instructions?|directions?|introduction|recipe overview|conclusion|notes?)\b',
        r'^\s*[\-\*\•\·]+\s*$',
        r'^\s*\d+\s*$',
        r'^\s*$'
    ]
    rx = re.compile("|".join(junk_patterns), re.IGNORECASE)

    cleaned = []
    seen = set()
    for line in raw_titles:
        s = line.strip()
        if not s:
            continue
        if rx.search(s):
            continue
        # Very short tokens (likely noise) -> skip
        if len(s) < 4:
            continue
        # Deduplicate (case-insensitive) while preserving original casing
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(s)

    if not cleaned:
        return []

    # Build OpenAI prompt: strict subset, no rewriting, no additions
    system_msg = (
        "You are a strict filter for cooking recipe titles. "
        "From the user's input lines, return ONLY the lines that are actual cooking recipes. "
        "Do not add new lines, do not rewrite or translate, do not change casing or punctuation. "
        "Output exactly one original input line per line. If none are recipes, return nothing."
    )
    user_payload = "INPUT LINES:\\n" + "\\n".join(cleaned) + "\\n\\nOUTPUT (subset of input, unchanged, one per line):"

    try:
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_payload},
        ]
        resp = chat_completion_with_retry(
            messages, model="gpt-4o-mini", temperature=0
        )
        assistant_msg = resp["choices"][0]["message"]["content"].strip()

        # Post-validate: keep only lines that existed in cleaned (verbatim match ignoring trailing spaces)
        valid_set = {c.strip(): True for c in cleaned}
        out = []
        for ln in assistant_msg.splitlines():
            ln2 = ln.strip()
            if not ln2:
                continue
            if ln2 in valid_set:
                out.append(ln2)
        # Final dedupe preserving order
        final = []
        seen2 = set()
        for s in out:
            if s.lower() not in seen2:
                seen2.add(s.lower())
                final.append(s)
        return final
    except Exception as e:
        print("OpenAI filter_only_recipes_with_openai error:", e)
        # Fallback: return the pre-cleaned list
        return cleaned
def filter_titles_with_openai(raw_titles):
    """
    Filter ONLY. Do not rewrite or generate new titles.
    - Input: list of lines (raw_titles)
    - Output: subset of those lines that are valid cooking recipe titles.
    Rules:
      * Keep original text exactly (no rephrasing, no capitalization changes).
      * Preserve the original order of the kept lines.
      * Do NOT add any new lines.
      * Remove lines that are clearly not recipes: URLs, hashtags, social handles, generic section headers
        (e.g., Introduction, Ingredients, Instructions, Conclusion), promotional/legal text (subscribe, privacy,
        login, terms, cookie), non-food content, or anything unrelated to a dish/recipe name.
      * Do NOT deduplicate similar titles; if the same title appears multiple times, keep all occurrences.
    """
    import re

    # Local quick pre-filter for obvious junk
    cleaned = []
    for line in raw_titles:
        t = line.strip()
        if not t:
            continue
        # Drop anything that looks like a link or handle
        if re.search(r'(https?://|www\.|\.com\b|\.net\b|\.org\b|@\w+|#\w+)', t, re.IGNORECASE):
            continue
        cleaned.append(t)

    if not cleaned:
        return []

    system_content = (
        "You are a strict filter. From the provided list of lines, return ONLY the lines that are genuine cooking "
        "recipe TITLES. Do not invent, rewrite, paraphrase, translate, or fix spelling. Only select from the input. "
        "Return the kept titles exactly as-is, one per line, preserving original order. Remove non-recipe lines such as "
        "URLs, hashtags, social handles, section headers (Introduction/Ingredients/Instructions/Conclusion), and generic/promotional/legal text "
        "(subscribe, privacy, login, terms, cookie, comment, rating, share, follow). Do not deduplicate."
    )

    # Put the lines under a clear marker so the model cannot hallucinate extras
    user_content = "INPUT LINES (one per line):\n" + "\n".join(cleaned) + "\n\n" +                    "Return ONLY the subset that are valid cooking recipe titles, EXACTLY as they appear. One per line. No extra text."

    try:
        resp = chat_completion_with_retry(
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
            ],
            model="gpt-4o-mini",
            temperature=0,
        )
        text = resp["choices"][0]["message"]["content"]
    except Exception as e:
        print("Error calling OpenAI API or parsing response:", e)
        # fallback: just do a conservative local filter with heuristics
        heuristics = []
        for t in cleaned:
            if re.search(r'(\brecipe\b|\bchicken\b|\bbeef\b|\bpasta\b|\bcake\b|\bbrownies\b|\bsalad\b|\bsoup\b|\bcasserole\b|\btacos\b|\bpancakes\b|\bair\s*fryer\b|\binstant\s*pot\b|\bcrock\s*pot\b)', t, re.IGNORECASE):
                heuristics.append(t)
        return heuristics if heuristics else cleaned

    # Parse lines; keep order; remove any accidental extras like bullet prefixes
    kept = []
    for line in text.splitlines():
        s = line.strip(" -• ")
        if not s:
            continue
        # Guard again against links
        if re.search(r'(https?://|www\.|\.com\b|\.net\b|\.org\b)', s, re.IGNORECASE):
            continue
        # Only keep if it existed in the cleaned input (exact match)
        if s in cleaned:
            kept.append(s)

    return kept
@app.route("/upload_titles", methods=["POST"])
def upload_titles():
    """
    2-step process:
      1) preview_only=1 -> use filter_titles_with_openai(...) but do NOT save to XLSX; return them for preview
      2) preview_only=0 -> expects final_titles (the user-edited list) to write to XLSX
    """
    preview_only = request.form.get("preview_only", "0")

    # ------------------ Step 1: PREVIEW ------------------
    if preview_only == "1":
        titles_text = request.form.get("titles", "")
        if not titles_text.strip():
            return jsonify({"status": "error", "message": "No titles provided."}), 400

        raw_titles = [line.strip() for line in titles_text.splitlines() if line.strip()]
        if not raw_titles:
            return jsonify({"status": "error", "message": "No valid titles."}), 400

        filtered_titles = filter_titles_with_openai(raw_titles)
        if not filtered_titles:
            return jsonify({"status": "error", "message": "OpenAI returned no valid recipe titles."}), 400

        return jsonify({
            "status": "preview",
            "message": "Preview of filtered titles (not written to XLSX).",
            "filtered_titles": filtered_titles
        })

    # ------------------ Step 2: CONFIRM & WRITE XLSX ------------------
    else:
        final_titles_json = request.form.get("final_titles", "")
        if not final_titles_json.strip():
            return jsonify({"status": "error", "message": "No final titles provided."}), 400

        try:
            final_titles = json.loads(final_titles_json)
        except:
            return jsonify({"status": "error", "message": "Invalid JSON in final_titles."}), 400

        if not isinstance(final_titles, list) or not final_titles:
            return jsonify({"status": "error", "message": "No valid final titles list."}), 400

        starts_folder = os.path.join(os.getcwd(), "STARTS")
        if not os.path.exists(starts_folder):
            return jsonify({"status": "error", "message": "STARTS folder not found."}), 400

        xlsx_files = [
            f for f in os.listdir(starts_folder)
            if f.lower().endswith(".xlsx") and not f.startswith("~$")
        ]
        if not xlsx_files:
            return jsonify({"status": "error", "message": "No XLSX files in STARTS."}), 400

        num_files = len(xlsx_files)

        def split_list(lst, n):
            k, m = divmod(len(lst), n)
            return [lst[i] for i in range(len(lst))],  # simplified; implement as needed

        # توزيع عادل على الملفات
        chunks = [[] for _ in range(num_files)]
        for i, title in enumerate(final_titles):
            chunks[i % num_files].append(title)

        file_counts = {}

        for file_name, chunk in zip(xlsx_files, chunks):
            file_path = os.path.join(starts_folder, file_name)
            try:
                wb = openpyxl.load_workbook(file_path)
                sheet = wb.active

                # Clear old data (row 2..end)
                for row in sheet.iter_rows(min_row=2, max_row=sheet.max_row):
                    for cell in row:
                        cell.value = None

                # Insert the chunk
                for row_num, title in enumerate(chunk, start=2):
                    sheet.cell(row=row_num, column=1, value=title)

                wb.save(file_path)
                file_counts[file_name] = len(chunk)
            except Exception as e:
                return jsonify({"status": "error", "message": f"Error in {file_name}: {e}"}), 500

        return jsonify({
            "status": "success",
            "message": "Final titles uploaded to XLSX files.",
            "total": len(final_titles),
            "counts": file_counts
        })


# ------------------------------------------------------------------
# 5) Clear FAILED Rows  (UPDATED: supports 'statu' AND 'statu_ing')
# ------------------------------------------------------------------
@app.route("/clear_failed", methods=["POST"])
def clear_failed():
    """
    كيمسح أي صف فـ Recipes.xlsx (أو images.xlsx القديم) إذا:
      - 'statu' = FAILED أو خاوي
      - أو 'statu_ing' = FAILED أو خاوي
    إذا كاين غير واحد فيهم، خدام. إذا جوج ما كاينينش كيرجع رسالة مناسبة.
    """
    results = {}
    for project in flat_ui_labels():
        out_folder = all_out_name_for_label(project)
        file_path = _project_excel_path_by_out_dir(out_folder)

        if not os.path.exists(file_path):
            results[project] = "File not found"
            continue

        try:
            wb = openpyxl.load_workbook(file_path)
            sheet = wb.active

            # Locate columns (case-insensitive)
            status_col = None
            status_ing_col = None
            for col in range(1, sheet.max_column + 1):
                v = sheet.cell(row=1, column=col).value
                if not v:
                    continue
                name = str(v).strip().lower()
                if name == "statu":
                    status_col = col
                elif name == "statu_ing":
                    status_ing_col = col

            if not status_col and not status_ing_col:
                results[project] = "No 'statu' or 'statu_ing' column"
                continue

            def needs_delete(row_idx: int) -> bool:
                """
                True إذا خاص الصف يتحيد بناءً على واحد من الأعمدة المتوفّرين:
                - 'statu' أو 'statu_ing' : FAILED أو فارغ
                """

                def cell_val(col_idx):
                    if not col_idx:
                        return None
                    raw = sheet.cell(row=row_idx, column=col_idx).value
                    return str(raw).strip() if raw is not None else ""

                v_statu = cell_val(status_col)
                v_statu_ing = cell_val(status_ing_col)

                cond_statu = (v_statu == "" or (isinstance(v_statu, str) and v_statu.upper() == "FAILED"))
                cond_statu_ing = (
                            v_statu_ing == "" or (isinstance(v_statu_ing, str) and v_statu_ing.upper() == "FAILED"))

                # خدم بالـ OR: إذا شي واحد فيهم مطبق، تحيد الصف
                # إلا بغيتها AND بدّل لـ (cond_statu and cond_statu_ing)
                return cond_statu or cond_statu_ing

            removed_count = 0
            for row in range(sheet.max_row, 1, -1):
                if needs_delete(row):
                    sheet.delete_rows(row)
                    removed_count += 1

            wb.save(file_path)
            results[project] = f"Removed {removed_count} rows"
        except Exception as e:
            results[project] = f"Error: {e}"

    return jsonify({"status": "success", "results": results})


# ------------------------------------------------------------------
# 6) Manage Images (UI)
# ------------------------------------------------------------------
@app.route("/manage_images")
def manage_images():
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="utf-8" />
      <title>Manage Images | Materio-Like UI</title>
      <!-- Bootstrap 5 + Boxicons -->
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css" rel="stylesheet">
      <link href="https://unpkg.com/boxicons@2.1.4/css/boxicons.min.css" rel="stylesheet">
      <style>
        body { background-color: #f8f9fd; }
        .materio-sidebar { width: 250px; min-height: 100vh; background-color: #fff; border-right: 1px solid #eceef1; position: fixed; left: 0; top: 0; padding: 20px; }
        .materio-sidebar .sidebar-title { font-size: 1.3rem; font-weight: bold; margin-bottom: 1rem; display: flex; align-items: center; }
        .materio-sidebar .sidebar-title i { font-size: 1.5rem; margin-right: 10px; color: #7367F0; }
        .materio-sidebar ul { list-style: none; padding: 0; }
        .materio-sidebar ul li { margin: 10px 0; }
        .materio-sidebar ul li a { text-decoration: none; color: #626262; font-weight: 500; display: block; padding: 8px 10px; border-radius: 6px; }
        .materio-sidebar ul li a:hover { background-color: #7367F0; color: #fff; }
        .navbar-materio { margin-left: 270px; background-color: #fff; border-bottom: 1px solid #eceef1; height: 60px; display: flex; align-items: center; justify-content: space-between; padding: 0 20px; position: fixed; width: calc(100% - 270px); top: 0; z-index: 1000; }
        .navbar-materio h5 { margin: 0; }
        .materio-content { margin-left: 270px; padding: 20px; margin-top: 80px; }
        .card-image-table img { max-width: 60px; border-radius: 4px; }
        .table thead th { vertical-align: bottom; }
        .badge-row { font-size: 0.9rem; }
      </style>
    </head>
    <body>
      <div class="materio-sidebar">
        <div class="sidebar-title">
          <i class='bx bxs-component'></i>
          <span>AUTOMATION</span>
        </div>
        <ul>
          <li><a href="/"><i class='bx bx-home-alt'></i> Dashboard</a></li>
          <li><a href="/manage_images"><i class='bx bx-image'></i> Manage Images</a></li>
          <li><a href="/manage_articles"><i class='bx bx-file'></i> Manage Articles</a></li>
          <li><a href="#" onclick="history.back()"><i class='bx bx-left-arrow-alt'></i> Go Back</a></li>
        </ul>
      </div>

      <div class="navbar-materio">
        <h5>Manage Images</h5>
        <div>
          <i class='bx bx-bell' style="font-size: 20px; margin-right: 20px;'></i>
          <i class='bx bx-user-circle' style="font-size: 24px;"></i>
        </div>
      </div>

      <div class="materio-content">
        <div class="row row-cols-1 row-cols-md-2 g-4">
    """

    for project in flat_ui_labels():
        file_path = _project_excel_path_by_out_dir(all_out_name_for_label(project))
        if not os.path.exists(file_path):
            html += f"""
            <div class="col">
              <div class="card h-100 mb-4">
                <div class="card-body">
                  <h4 class="card-title">{project}</h4>
                  <p class="card-text text-danger">Recipes.xlsx not found.</p>
                </div>
              </div>
            </div>
            """
            continue

        wb = openpyxl.load_workbook(file_path)
        sheet = wb.active

        headers = {}
        for col in range(1, sheet.max_column + 1):
            val = sheet.cell(row=1, column=col).value
            if val and val.strip().lower() in ["image_1", "image_2", "image_3", "image_4"]:
                headers[val.strip().lower()] = col

        html += f"""
          <div class="col">
            <div class="card h-100 card-image-table">
              <div class="card-header bg-light">
                <strong>{project}</strong>
              </div>
              <div class="card-body p-0 table-responsive">
                <table class="table table-striped table-hover mb-0 align-middle">
                  <thead class="table-light">
                    <tr>
                      <th style="width: 60px;">Row</th>
                      <th>image_1</th>
                      <th>image_2</th>
                      <th>image_3</th>
                      <th>image_4</th>
                      <th style="width: 80px;">Action</th>
                    </tr>
                  </thead>
                  <tbody>
        """

        for row_idx in range(2, sheet.max_row + 1):
            image_tags = []
            for img_col_name in ["image_1", "image_2", "image_3", "image_4"]:
                col_index = headers.get(img_col_name)
                if col_index:
                    cell_val = sheet.cell(row=row_idx, column=col_index).value
                    if cell_val:
                        image_tags.append(
                            f"<img src='{cell_val}?r={row_idx}_{img_col_name}' alt='{cell_val}' />"
                        )
                    else:
                        image_tags.append("")
                else:
                    image_tags.append("")

            delete_form = f"""
            <form class="delete-form" action="/delete_image_row" method="post" style="display:inline-block;" onsubmit="return deleteImageRow(event, this);">
              <input type="hidden" name="project" value="{project}" />
              <input type="hidden" name="row_number" value="{row_idx}" />
              <button class="btn btn-sm btn-danger" type="submit">Del</button>
            </form>
            """

            html += f"""
            <tr>
              <td><span class="badge bg-secondary badge-row">{row_idx}</span></td>
              <td>{image_tags[0]}</td>
              <td>{image_tags[1]}</td>
              <td>{image_tags[2]}</td>
              <td>{image_tags[3]}</td>
              <td>{delete_form}</td>
            </tr>
            """

        html += f"""
              </tbody>
                </table>
              </div>
              <div class="card-footer"></div>
            </div>
          </div>
        """

    html += """
        </div> <!-- .row -->
      </div> <!-- .materio-content -->

      <script>
        function deleteImageRow(event, form) {
          event.preventDefault();
          fetch(form.action, {
            method: "POST",
            body: new FormData(form)
          })
          .then(response => response.text())
          .then(data => {
            let row = form.closest("tr");
            if(row) { row.remove(); }
          })
          .catch(error => { alert("Error deleting row: " + error); });
          return false;
        }
      </script>

      <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """
    return html


@app.route("/manage_articles")
def manage_articles():
    cols = [
        "Main Keyword", "Recipe", "image_1", "image_2", "image_3", "image_4",
        "article", "pinterest_title", "pinterest_description",
        "pinterest_image_short_title", "category", "pinterest_image"
    ]

    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="utf-8" />
      <title>Manage Articles | Materio-Like UI</title>
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css" rel="stylesheet">
      <link href="https://unpkg.com/boxicons@2.1.4/css/boxicons.min.css" rel="stylesheet">
      <style>
        body { background-color: #f8f9fd; }
        .materio-sidebar { width: 250px; min-height: 100vh; background: #fff; border-right: 1px solid #eceef1; position: fixed; padding: 20px; }
        .navbar-materio { margin-left:270px; background:#fff; border-bottom:1px solid #eceef1; height:60px; display:flex; align-items:center; justify-content:space-between; padding:0 20px; position:fixed; width:calc(100% - 270px); top:0; }
        .materio-content { margin-left:270px; padding:20px; margin-top:80px; }
        table td, table th { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 150px; }
      </style>
    </head>
    <body>
      <div class="materio-sidebar">
        <div class="sidebar-title"><i class='bx bxs-component'></i> <strong>AUTOMATION</strong></div>
        <ul class="list-unstyled">
          <li><a href="/"><i class='bx bx-home-alt'></i> Dashboard</a></li>
          <li><a href="/manage_images"><i class='bx bx-image'></i> Manage Images</a></li>
          <li><a href="/manage_articles"><i class='bx bx-file'></i> Manage Articles</a></li>
        </ul>
      </div>
      <div class="navbar-materio">
        <h5>Manage Articles</h5>
        <div><i class='bx bx-user-circle' style="font-size:24px;"></i></div>
      </div>
      <div class="materio-content">
        <div class="mb-3">
          <form action="/delete_all_article_blanks" method="post">
            <button class="btn btn-danger">Remove All Blank Rows from All Projects</button>
          </form>
        </div>
        <div class="row row-cols-1 g-4">
    """

    for project in flat_ui_labels():
        path = os.path.join(
            os.getcwd(), "ALL", all_out_name_for_label(project), "ARTICLE.xlsx"
        )
        if not os.path.exists(path):
            html += f"""
            <div class="col">
              <div class="card h-100">
                <div class="card-body">
                  <h4 class="card-title">{project}</h4>
                  <p class="text-danger">ARTICLE.xlsx not found.</p>
                </div>
              </div>
            </div>
            """
            continue

        wb = openpyxl.load_workbook(path, data_only=True)
        sheet = wb.active

        header_map = {}
        for c in range(1, sheet.max_column + 1):
            val = sheet.cell(row=1, column=c).value
            if val and val.strip() in cols:
                header_map[val.strip()] = c

        html += f"""
          <div class="col">
            <div class="card h-100">
              <div class="card-header bg-light"><strong>{project}</strong></div>
              <div class="card-body p-0 table-responsive">
                <table class="table table-hover mb-0">
                  <thead class="table-light"><tr>
        """
        for col in cols:
            html += f"<th title='{col}'>{col}</th>"
        html += "</tr></thead><tbody>"

        for r in range(2, sheet.max_row + 1):
            vals = []
            empty_found = False
            for col in cols:
                col_idx = header_map.get(col)
                v = sheet.cell(row=r, column=col_idx).value if col_idx else None
                if v is None or (isinstance(v, str) and not v.strip()):
                    empty_found = True
                    vals.append("")
                else:
                    vals.append(v)
            row_class = "table-danger" if empty_found else ""
            html += f"<tr class='{row_class}'>"
            for v in vals:
                html += f"<td title='{v}'>{v}</td>"
            html += "</tr>"

        html += f"""
                  </tbody>
                </table>
              </div>
              <div class="card-footer">
                <form action="/delete_article_blanks" method="post" style="display:inline-block;">
                  <input type="hidden" name="project" value="{project}" />
                  <button class="btn btn-sm btn-danger">Remove Blank Rows</button>
                </form>
              </div>
            </div>
          </div>
        """

    html += """
        </div>
      </div>
      <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """
    return html


@app.route("/delete_article_blanks", methods=["POST"])
def delete_article_blanks():
    project = request.form.get("project", "")
    cols = [
        "Main Keyword", "Recipe", "image_1", "image_2", "image_3", "image_4",
        "article", "pinterest_title", "pinterest_description",
        "pinterest_image_short_title", "category", "pinterest_image"
    ]
    if not is_allowed_project_label(project):
        return f"<h1>Invalid project: {project}</h1><a href='/manage_articles'>Back</a>"
    path = os.path.join(
        os.getcwd(), "ALL", all_out_name_for_label(project), "ARTICLE.xlsx"
    )
    if not os.path.exists(path):
        return f"<h1>ARTICLE.xlsx not found for {project}</h1><a href='/manage_articles'>Back</a>"

    wb = openpyxl.load_workbook(path)
    sheet = wb.active
    header_map = {}
    for c in range(1, sheet.max_column + 1):
        val = sheet.cell(row=1, column=c).value
        if val and val.strip() in cols:
            header_map[val.strip()] = c

    removed = 0
    for row_idx in range(sheet.max_row, 1, -1):
        if any(
                (sheet.cell(row=row_idx, column=col_idx).value is None or
                 (isinstance(sheet.cell(row=row_idx, column=col_idx).value, str) and not sheet.cell(row=row_idx,
                                                                                                    column=col_idx).value.strip()))
                for col_idx in header_map.values()
        ):
            sheet.delete_rows(row_idx)
            removed += 1
    wb.save(path)
    return f"<h1>Removed {removed} blank rows from {project}</h1><a href='/manage_articles'>Back</a>"


@app.route("/delete_all_article_blanks", methods=["POST"])
def delete_all_article_blanks():
    cols = [
        "Main Keyword", "Recipe", "image_1", "image_2", "image_3", "image_4",
        "article", "pinterest_title", "pinterest_description",
        "pinterest_image_short_title", "category", "pinterest_image"
    ]
    summary = []
    for project in flat_ui_labels():
        path = os.path.join(
            os.getcwd(), "ALL", all_out_name_for_label(project), "ARTICLE.xlsx"
        )
        if not os.path.exists(path):
            summary.append(f"{project}: file not found")
            continue
        wb = openpyxl.load_workbook(path)
        sheet = wb.active
        header_map = {}
        for c in range(1, sheet.max_column + 1):
            val = sheet.cell(row=1, column=c).value
            if val and val.strip() in cols:
                header_map[val.strip()] = c
        removed = 0
        for row_idx in range(sheet.max_row, 1, -1):
            if any(
                    (sheet.cell(row=row_idx, column=col_idx).value is None or
                     (isinstance(sheet.cell(row=row_idx, column=col_idx).value, str) and not sheet.cell(row=row_idx,
                                                                                                        column=col_idx).value.strip()))
                    for col_idx in header_map.values()
            ):
                sheet.delete_rows(row_idx)
                removed += 1
        wb.save(path)
        summary.append(f"{project}: {removed} removed")
    result = "<h1>Bulk Blank Removal Summary</h1><ul>" + "".join(
        f"<li>{s}</li>" for s in summary) + "</ul><a href='/manage_articles'>Back</a>"
    return result


# -------------------- 7) Delete Image Row --------------------
@app.route("/delete_image_row", methods=["POST"])
def delete_image_row():
    project = request.form.get("project", "")
    row_number_str = request.form.get("row_number", "")

    if not project or not row_number_str:
        return "<h1>Missing project/row_number</h1><a href='/manage_images'>Back</a>"

    if not is_allowed_project_label(project):
        return f"<h1>Invalid project: {project}</h1><a href='/manage_images'>Back</a>"

    try:
        row_number = int(row_number_str)
    except:
        return "<h1>Invalid row_number</h1><a href='/manage_images'>Back</a>"

    file_path = _project_excel_path_by_out_dir(all_out_name_for_label(project))
    if not os.path.exists(file_path):
        return f"<h1>Recipes.xlsx not found for {project}</h1><a href='/manage_images'>Back</a>"

    wb = openpyxl.load_workbook(file_path)
    sheet = wb.active

    if 2 <= row_number <= sheet.max_row:
        sheet.delete_rows(row_number, 1)
        wb.save(file_path)
        return f"<h1>Row {row_number} deleted from {project}'s Recipes.xlsx</h1>"
    else:
        return f"<h1>Row {row_number} out of range</h1>"


# -------------------- 8) Main Dashboard Page --------------------
@app.route("/")
def index():
    starts_folder = os.path.join(os.getcwd(), "STARTS")
    if os.path.exists(starts_folder):
        xlsx_files = [f for f in os.listdir(starts_folder) if f.lower().endswith(".xlsx") and not f.startswith("~$")]
        num_xlsx = len(xlsx_files)
    else:
        num_xlsx = 0

    _units = flat_run_units()
    project_folders_json = _json_for_inline_script([u["log_id"] for u in _units])
    project_units_json = _json_for_inline_script(
        [{"log_id": u["log_id"], "label": u["label"]} for u in _units]
    )

    log_boxes = ""
    for u in _units:
        lid = u["log_id"]
        title = u["label"]
        lidj = json.dumps(lid)
        titlej = json.dumps(title)
        log_boxes += f"""
          <div class="col-lg-6 mb-4">
            <div class="card h-100">
              <div class="card-header d-flex justify-content-between align-items-start flex-wrap gap-1">
                <div class="me-2 flex-grow-1">
                  <h6 class="mb-0 text-secondary">{title} Log</h6>
                  <div id="stats_{lid}" class="small text-muted project-stats-line">Loading stats...</div>
                </div>
                <button type="button" class="btn btn-sm btn-outline-info" title="Edit this project in sites.json (tabbed: WordPress, API, Start, a2, pipeline, …)" onclick='showSiteConfigInfo({titlej})'>Info</button>
              </div>
              <div class="card-body overflow-auto" style="height:200px;" id="log_{lid}"></div>
              <div class="card-footer">
                <button class="btn btn-sm btn-primary project-action" onclick='startProjectAction({lidj}, {titlej}, "start", this)'>START</button>
                <button class="btn btn-sm btn-secondary project-action" onclick='startProjectAction({lidj}, {titlej}, "json", this)'>JSON</button>
                <button class="btn btn-sm btn-warning project-action" onclick='startProjectAction({lidj}, {titlej}, "prompt", this)'>PROMPT</button>
                <button class="btn btn-sm btn-info project-action" onclick='startProjectAction({lidj}, {titlej}, "imagine", this)'>IMAGINE</button>
                <button class="btn btn-sm btn-success project-action" onclick='startProjectAction({lidj}, {titlej}, "article", this)'>ARTICLE</button>
                <button class="btn btn-sm btn-dark project-action" onclick='startProjectAction({lidj}, {titlej}, "pin_data", this)'>PIN DATA</button>
                <button class="btn btn-sm btn-dark project-action" onclick='startProjectAction({lidj}, {titlej}, "pin_image", this)'>PIN IMAGE</button>
                <button class="btn btn-sm btn-dark project-action" onclick='startProjectAction({lidj}, {titlej}, "wp_upload", this)'>WP UPLOAD</button>
                <button class="btn btn-sm btn-dark project-action" onclick='startProjectAction({lidj}, {titlej}, "pin_bulk", this)'>PIN BULK</button>
                <button class="btn btn-sm btn-outline-danger" onclick='clearProjectLog({lidj})'>CLEAR LOG</button>
              </div>
            </div>
          </div>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="utf-8" />
      <title>Automation Pinterest</title>
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/css/bootstrap.min.css" rel="stylesheet">
      <link href="https://unpkg.com/boxicons@2.1.4/css/boxicons.min.css" rel="stylesheet">
      <style>
        body {{
          background-color: #f8f9fd;
        }}
        .materio-sidebar {{
          width: 250px;
          min-height: 100vh;
          background-color: #fff;
          border-right: 1px solid #eceef1;
          position: fixed;
          left: 0;
          top: 0;
          padding: 20px;
        }}
        .materio-sidebar .sidebar-title {{
          font-size: 1.3rem;
          font-weight: bold;
          margin-bottom: 1rem;
          display: flex;
          align-items: center;
        }}
        .materio-sidebar .sidebar-title i {{
          font-size: 1.5rem;
          margin-right: 10px;
          color: #7367F0;
        }}
        .materio-sidebar ul {{
          list-style: none;
          padding: 0;
        }}
        .materio-sidebar ul li {{
          margin: 10px 0;
        }}
        .materio-sidebar ul li a {{
          text-decoration: none;
          color: #626262;
          font-weight: 500;
          display: block;
          padding: 8px 10px;
          border-radius: 6px;
        }}
        .materio-sidebar ul li a:hover {{
          background-color: #7367F0;
          color: #fff;
        }}
        .navbar-materio {{
          margin-left: 270px;
          background-color: #fff;
          border-bottom: 1px solid #eceef1;
          height: 60px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 0 20px;
          position: fixed;
          width: calc(100% - 270px);
          top: 0;
          z-index: 1000;
        }}
        .navbar-materio h5 {{ margin: 0; }}
        .materio-content {{ margin-left: 270px; padding: 20px; margin-top: 80px; }}
        .number-button {{
          display: inline-block;
          position: relative;
          margin: 5px;
          padding: 10px 20px 10px 50px;
          background-color: #7367F0;
          color: #fff;
          border: none;
          border-radius: 25px;
          cursor: pointer;
          font-size: 14px;
          transition: background-color 0.3s;
          text-decoration: none;
        }}
        .number-button::before {{
          content: attr(data-number);
          position: absolute;
          left: 10px;
          top: 50%;
          transform: translateY(-50%);
          width: 30px;
          height: 30px;
          background-color: #fff;
          color: #7367F0;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: bold;
        }}
        .number-button:hover {{ background-color: #5b51db; }}
        .number-button.active {{ background-color: yellow; color: #000; }}
        .number-button.finished {{ background-color: #28c76f; }}
        #previewTable td {{ padding: 5px; vertical-align: middle; }}
        #previewTable button {{ margin-left: 10px; }}
        #siteConfigModal .modal-dialog {{ max-width: min(1140px, 96vw); margin-left: auto; margin-right: auto; }}
        #siteConfigModal .nav-tabs .nav-link {{ font-weight: 600; font-size: 0.9rem; padding: 0.45rem 0.7rem; white-space: nowrap; }}
        #siteConfigModal .site-editor-top-tabs {{ border-bottom: 0; flex-wrap: nowrap; }}
        #siteConfigModal .site-editor-form-tab-content {{ min-height: 12rem; }}
        #siteConfigModal #siteEditorFormPane label {{ font-size: 0.8rem; margin-bottom: 0.1rem; }}
        .project-stats-line {{
          max-width: 100%;
          margin-top: 2px;
          white-space: normal;
          overflow-wrap: anywhere;
          word-break: break-word;
          line-height: 1.25;
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
          align-items: center;
        }}
        .stat-chip {{
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 2px 8px;
          border-radius: 999px;
          font-size: 11px;
          font-weight: 600;
          border: 1px solid transparent;
        }}
        .stat-chip i {{ font-size: 14px; line-height: 1; }}
        .stat-chip-good {{
          background: #28c76f;
          color: #fff;
        }}
        .stat-chip-bad {{
          background: #ea5455;
          color: #fff;
        }}
        .stat-chip-neutral {{
          background: #f1f3f5;
          color: #5c6670;
          border-color: #d6dbe1;
        }}
        .stat-chip-name {{
          max-width: 180px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }}
        .stat-chip-open {{ color: inherit !important; }}
        .stat-chip-open:hover {{ opacity: 0.85; }}
      </style>
      <script>
        var source = null;
        var projectFolders = {project_folders_json};
        var projectUnits = {project_units_json};
        var numXlsx = {num_xlsx};
        var _projectLogHistory = {{}};

        function _logStorageKey(logId) {{
          return "pinterest_log_" + String(logId || "");
        }}

        function _persistLog(logId) {{
          try {{
            localStorage.setItem(_logStorageKey(logId), _projectLogHistory[logId] || "");
          }} catch (e) {{}}
        }}

        function _appendProjectLog(logId, line, isFinished) {{
          if (!logId) return;
          var htmlLine = isFinished
            ? "<span style='color: green;'>" + String(line || "") + "</span><br>"
            : String(line || "") + "<br>";
          _projectLogHistory[logId] = String(_projectLogHistory[logId] || "") + htmlLine;
          var logDiv = document.getElementById("log_" + logId);
          if (logDiv) {{
            logDiv.innerHTML = _projectLogHistory[logId];
            logDiv.scrollTop = logDiv.scrollHeight;
          }}
          _persistLog(logId);
        }}

        function clearProjectLog(logId) {{
          if (!logId) return;
          _projectLogHistory[logId] = "";
          var logDiv = document.getElementById("log_" + logId);
          if (logDiv) logDiv.innerHTML = "";
          try {{ localStorage.removeItem(_logStorageKey(logId)); }} catch (e) {{}}
        }}

        function _restoreProjectLogsFromStorage() {{
          (projectFolders || []).forEach(function(logId) {{
            var v = "";
            try {{ v = localStorage.getItem(_logStorageKey(logId)) || ""; }} catch (e) {{ v = ""; }}
            _projectLogHistory[logId] = v;
            var logDiv = document.getElementById("log_" + logId);
            if (logDiv && v) {{
              logDiv.innerHTML = v;
              logDiv.scrollTop = logDiv.scrollHeight;
            }}
          }});
        }}

        function disableActionButtons() {{
          var buttons = document.querySelectorAll(".number-button");
          buttons.forEach(function(btn) {{ btn.disabled = true; }});
        }}

        function enableActionButtons() {{
          var buttons = document.querySelectorAll(".number-button");
          buttons.forEach(function(btn) {{ btn.disabled = false; }});
        }}

        function _escapeHtml(s) {{
          return String(s == null ? "" : s)
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;");
        }}

        function showColumnDetails(projectLabel, columnName) {{
          var modalEl = document.getElementById("columnDetailsModal");
          var titleEl = document.getElementById("columnDetailsTitle");
          var bodyEl = document.getElementById("columnDetailsBody");
          if (!modalEl || !titleEl || !bodyEl) return;
          titleEl.textContent = projectLabel + " — " + columnName;
          bodyEl.innerHTML = "<div class='text-muted'>Loading...</div>";
          if (typeof bootstrap !== "undefined") {{
            new bootstrap.Modal(modalEl).show();
          }}
          fetch("/api/project-column-details?project=" + encodeURIComponent(projectLabel) + "&column=" + encodeURIComponent(columnName))
            .then(function(r) {{ return r.json().then(function(j) {{ if (!r.ok) throw new Error((j && (j.error || j.message)) || ("HTTP " + r.status)); return j; }}); }})
            .then(function(data) {{
              if (!data || !data.ok) {{
                bodyEl.innerHTML = "<div class='alert alert-danger py-2 mb-0'>Could not load details.</div>";
                return;
              }}
              var rows = Array.isArray(data.rows) ? data.rows : [];
              if (!rows.length) {{
                bodyEl.innerHTML = "<div class='alert alert-warning py-2 mb-0'>No rows found.</div>";
                return;
              }}
              var html = "";
              if (!data.column_exists) {{
                html += "<div class='alert alert-warning py-2'>Column does not exist yet in sheet. Showing Title list with empty values.</div>";
              }}
              html += "<div class='table-responsive'><table class='table table-sm table-striped align-middle mb-0'>";
              html += "<thead><tr><th style='width:70px'>#</th><th>Title</th><th style='width:140px'>Status</th><th>Result</th></tr></thead><tbody>";
              rows.forEach(function(r) {{
                var badge = r.filled
                  ? "<span class='badge bg-success'>Done</span>"
                  : "<span class='badge bg-danger'>Missing</span>";
                html += "<tr>"
                  + "<td>" + _escapeHtml(String(r.row || "")) + "</td>"
                  + "<td>" + _escapeHtml(String(r.title || "")) + "</td>"
                  + "<td>" + badge + "</td>"
                  + "<td>" + _escapeHtml(String(r.value || "")) + "</td>"
                  + "</tr>";
              }});
              html += "</tbody></table></div>";
              bodyEl.innerHTML = html;
            }})
            .catch(function(e) {{
              bodyEl.innerHTML = "<div class='alert alert-danger py-2 mb-0'>Error: " + _escapeHtml(e && e.message ? e.message : e) + "</div>";
            }});
        }}

        function showColumnDetailsByEncoded(projectEnc, columnEnc) {{
          var p = decodeURIComponent(String(projectEnc || ""));
          var c = decodeURIComponent(String(columnEnc || ""));
          showColumnDetails(p, c);
        }}

        function refreshProjectStats(logId, projectLabel) {{
          var el = document.getElementById("stats_" + logId);
          if (!el) return;
          function renderCols(cols) {{
            if (!Array.isArray(cols) || !cols.length) {{
              el.textContent = "No columns";
              return;
            }}
            var pieces = cols.map(function(c) {{
              var filled = Number(c.filled || 0);
              var total = Number(c.total || 0);
              var name = String(c.name || "");
              var projEnc = encodeURIComponent(String(projectLabel || ""));
              var nameEnc = encodeURIComponent(name);
              var klass = "stat-chip-neutral";
              var icon = "bx-minus-circle";
              if (total > 0) {{
                if (filled >= total) {{
                  klass = "stat-chip-good";
                  icon = "bx-check-circle";
                }} else {{
                  klass = "stat-chip-bad";
                  icon = "bx-x-circle";
                }}
              }}
              return ""
                + "<span class='stat-chip " + klass + "' data-st-pe='" + projEnc + "' data-st-ce='" + nameEnc
                + "' title='" + _escapeHtml(name + ": " + filled + "/" + total).replace(/'/g, "&#39;") + "'>"
                + "<i class='bx " + icon + "'></i>"
                + "<span class='stat-chip-count'>" + _escapeHtml(String(filled) + "/" + String(total)) + "</span>"
                + "<span class='stat-chip-name'>" + _escapeHtml(name) + "</span>"
                + "<i class='bx bx-expand-alt stat-chip-open' role='button' tabindex='0' title='Show details'></i>"
                + "</span>";
            }});
            el.innerHTML = pieces.join("");
          }}
          fetch("/api/project-stats?project=" + encodeURIComponent(projectLabel))
            .then(function(r) {{ return r.json().then(function(j) {{ if (!r.ok) throw new Error((j && (j.error || j.message)) || ("HTTP " + r.status)); return j; }}); }})
            .then(function(data) {{
              if (!data || !data.ok) {{
                el.textContent = "Stats unavailable";
                return;
              }}
              renderCols(Array.isArray(data.columns) ? data.columns : []);
            }})
            .catch(function() {{
              el.textContent = "Stats unavailable";
            }});
        }}

        function refreshAllProjectStats() {{
          fetch("/api/projects-stats")
            .then(function(r) {{ return r.json().then(function(j) {{ if (!r.ok) throw new Error((j && (j.error || j.message)) || ("HTTP " + r.status)); return j; }}); }})
            .then(function(data) {{
              var items = (data && Array.isArray(data.items)) ? data.items : [];
              if (!items.length) {{
                (projectUnits || []).forEach(function(u) {{ refreshProjectStats(u.log_id, u.label); }});
                return;
              }}
              var seen = {{}};
              items.forEach(function(it) {{
                var lid = String(it.log_id || "");
                var projectLabel = String(it.project || "");
                var el = document.getElementById("stats_" + lid);
                if (!el) return;
                seen[lid] = true;
                if (!it.ok) {{
                  el.textContent = "Stats unavailable";
                  return;
                }}
                var cols = Array.isArray(it.columns) ? it.columns : [];
                if (!cols.length) {{
                  el.textContent = "No columns";
                  return;
                }}
                var pieces = cols.map(function(c) {{
                  var filled = Number(c.filled || 0);
                  var total = Number(c.total || 0);
                  var name = String(c.name || "");
                  var projEnc = encodeURIComponent(String(projectLabel || ""));
                  var nameEnc = encodeURIComponent(name);
                  var klass = "stat-chip-neutral";
                  var icon = "bx-minus-circle";
                  if (total > 0) {{
                    if (filled >= total) {{
                      klass = "stat-chip-good";
                      icon = "bx-check-circle";
                    }} else {{
                      klass = "stat-chip-bad";
                      icon = "bx-x-circle";
                    }}
                  }}
                  return ""
                    + "<span class='stat-chip " + klass + "' data-st-pe='" + projEnc + "' data-st-ce='" + nameEnc
                    + "' title='" + _escapeHtml(name + ": " + filled + "/" + total).replace(/'/g, "&#39;") + "'>"
                    + "<i class='bx " + icon + "'></i>"
                    + "<span class='stat-chip-count'>" + _escapeHtml(String(filled) + "/" + String(total)) + "</span>"
                    + "<span class='stat-chip-name'>" + _escapeHtml(name) + "</span>"
                    + "<i class='bx bx-expand-alt stat-chip-open' role='button' tabindex='0' title='Show details'></i>"
                    + "</span>";
                }});
                el.innerHTML = pieces.join("");
              }});
              (projectUnits || []).forEach(function(u) {{
                if (!seen[String(u.log_id || "")]) refreshProjectStats(u.log_id, u.label);
              }});
            }})
            .catch(function() {{
              (projectUnits || []).forEach(function(u) {{
                refreshProjectStats(u.log_id, u.label);
              }});
            }});
        }}

        document.addEventListener("click", function(ev) {{
          var opener = ev.target.closest(".stat-chip-open");
          if (!opener) return;
          var chip = opener.closest(".stat-chip");
          if (!chip) return;
          var pe = chip.getAttribute("data-st-pe");
          var ce = chip.getAttribute("data-st-ce");
          if (pe !== null && ce !== null && String(pe).length) {{
            showColumnDetailsByEncoded(pe, ce);
          }}
        }});

        function startLog(endpoint, btn) {{
          if(source !== null) {{ return; }}
          disableActionButtons();

          source = new EventSource(endpoint);
          source.onmessage = function(e) {{
            try {{
              let data = JSON.parse(e.data);
              let folder = data.folder;
              let line = data.line;
              if (folder && folder !== "all") {{
                _appendProjectLog(folder, line, line.includes("Finished"));
                if(line.includes("Finished")) {{
                  var pu = (projectUnits || []).find(function(x) {{ return x.log_id === folder; }});
                  if (pu) refreshProjectStats(pu.log_id, pu.label);
                }}
              }}
    if (
      folder === "all" &&
      (
        line.includes("Finished all processes.") ||
        line.includes("Finished all IMAGINE ALL groups.")
      )
    ) {{
      btn.classList.remove("active");
      btn.classList.add("finished");
      enableActionButtons();
      source.close();
      source = null;
    }}

  }} catch (err) {{
    console.error("SSE parse error:", err);
  }}
}};
          source.onerror = function(err) {{
            console.error("EventSource error:", err);
            enableActionButtons();
            source.close();
            source = null;
          }};
          btn.classList.add("active");
        }}

        function stopLog() {{
          if (source) {{
            source.close();
            source = null;
            enableActionButtons();
          }}
          fetch("/stop_scripts", {{ method: "POST" }})
            .then(response => response.json())
            .then(data => {{ console.log("Stopped scripts:", data.message); }})
            .catch(err => {{ console.error("Error stopping scripts:", err); }});
        }}

        function clearFailed() {{
          fetch("/clear_failed", {{ method: "POST" }})
          .then(r => r.json())
          .then(data => {{
            if(data.status === "success") {{
              alert("Clear FAILED done: " + JSON.stringify(data.results));
            }} else {{
              alert("Error: " + data.message);
            }}
          }})
          .catch(err => alert("Error: " + err));
        }}

        document.addEventListener("DOMContentLoaded", function() {{
          let previewForm = document.getElementById("previewForm");
          let previewResult = document.getElementById("previewResult");
          let finalResult = document.getElementById("finalResult");
          let titlesArea = document.getElementById("titles");
          let titleCount = document.getElementById("titleCount");
          let confirmBtn = document.getElementById("confirmBtn");

          if(titlesArea) {{
            titlesArea.addEventListener("input", function() {{
              let lines = titlesArea.value.split(/\\r?\\n/).filter(l => l.trim() !== "");
              let total = lines.length;
              titleCount.innerText = total + " titles";
            }});
          }}

          if(previewForm) {{
            previewForm.addEventListener("submit", function(e) {{
              e.preventDefault();
              previewResult.innerHTML = "Loading preview...";
              finalResult.innerHTML = "";

              let formData = new FormData(previewForm);
              formData.set("preview_only", "1");

              fetch("/upload_titles", {{
                method: "POST",
                body: formData
              }})
              .then(r => r.json())
              .then(data => {{
                if(data.status === "preview") {{
                  const arr = data.filtered_titles;
                  let html = "<table class='table' id='previewTable'><tbody>";
                  for(let i=0; i < arr.length; i++) {{
                    html += "<tr><td>" + arr[i] + "</td>"
                         + "<td><button class='btn btn-sm btn-danger' onclick='removeRow(this)'>Delete</button></td></tr>";
                  }}
                  html += "</tbody></table>";

                  previewResult.innerHTML = html;
                  confirmBtn.style.display = "inline-block";
                }} else {{
                  previewResult.innerHTML = "<span style='color:red'>" + data.message + "</span>";
                  confirmBtn.style.display = "none";
                }}
              }})
              .catch(err => {{
                previewResult.innerHTML = "<span style='color:red'>Error: " + err + "</span>";
                confirmBtn.style.display = "none";
              }});
            }});
          }}

          if(confirmBtn) {{
            confirmBtn.addEventListener("click", function() {{
              finalResult.innerHTML = "Uploading to XLSX...";
              let table = document.getElementById("previewTable");
              if(!table) {{
                finalResult.innerHTML = "<span style='color:red'>No preview table found.</span>";
                return;
              }}
              let rows = table.querySelectorAll("tr");
              let finalTitles = [];
              rows.forEach(r => {{
                let cell = r.querySelector("td");
                if(cell && cell.innerText.trim() !== "") {{
                  finalTitles.push(cell.innerText.trim());
                }}
              }});
              if(finalTitles.length===0) {{
                finalResult.innerHTML = "<span style='color:red'>No titles to upload.</span>";
                return;
              }}

              let formData = new FormData();
              formData.set("preview_only","0");
              formData.set("final_titles", JSON.stringify(finalTitles));

              fetch("/upload_titles", {{
                method: "POST",
                body: formData
              }})
              .then(r => r.json())
              .then(data => {{
                if(data.status==="success") {{
                  finalResult.innerHTML = "<span style='color:green'>" + data.message + "</span>"
                    + "<br>Total: " + data.total
                    + "<br>File distribution: " + JSON.stringify(data.counts);
                }} else {{
                  finalResult.innerHTML = "<span style='color:red'>" + data.message + "</span>";
                }}
              }})
              .catch(err => {{
                finalResult.innerHTML = "<span style='color:red'>Error: " + err + "</span>";
              }});
            }});
          }}
        }});

        function removeRow(btn) {{
          let tr = btn.closest("tr");
          if(tr) tr.remove();
        }}

        var projectStreams = {{}};
        function startProjectAction(logId, projectLabel, action, btn) {{
          if(projectStreams[logId]) {{ return; }}
          var card = btn.closest('.card');
          var buttons = card.querySelectorAll('button.project-action');
          buttons.forEach(function(b) {{ b.disabled = true; }});
          var ep = "/stream-single?project=" + encodeURIComponent(projectLabel) + "&action=" + encodeURIComponent(action);
          var source = new EventSource(ep);
          projectStreams[logId] = source;
          source.onmessage = function(e) {{
            try {{
              let data = JSON.parse(e.data);
              let logDiv = document.getElementById("log_" + data.folder);
              if (!logDiv) logDiv = document.getElementById("log_" + logId);
              var targetLogId = data.folder || logId;
              _appendProjectLog(targetLogId, data.line, data.line.includes("Finished"));
              if(data.line.includes("Finished")) {{
                source.close();
                delete projectStreams[logId];
                buttons.forEach(function(b) {{ b.disabled = false; }});
              }}
            }} catch(err) {{
              console.error("Project SSE parse error:", err);
            }}
          }};
          source.onerror = function(err) {{
            console.error("Project EventSource error:", err);
            source.close();
            delete projectStreams[logId];
            buttons.forEach(function(b) {{ b.disabled = false; }});
          }};
        }}
        document.addEventListener("DOMContentLoaded", function() {{
          _restoreProjectLogsFromStorage();
        }});

        var _siteEditorProject = "";
        var _siteEditorBase = null;
        var _siteEditorRawDirty = false;
        var PROMPT_FORM_KEYS = ["a1_start", "a2_json", "a2_prompt", "a4_articles", "a5_pin_data", "a8_pin_bulk"];
        var _siteEditorPromptFieldSchema = null;
        function _promptGroupContainerId(pr) {{
          if (pr === "a1_start") return "ed_pr_sub_start";
          if (pr === "a2_json" || pr === "a2_prompt") return "ed_pr_sub_a2";
          if (pr === "a4_articles" || pr === "a5_pin_data" || pr === "a8_pin_bulk") return "ed_pr_sub_pipe";
          return "ed_pr_sub_other";
        }}
        function _promptFieldDomId(pr, path) {{ return "edpf_" + pr + "__" + String(path).replace(/\\./g, "__"); }}
        function _fieldIsNonEmpty(f, el) {{
          if (!el) return false;
          if (f.kind === "bool") return !!el.checked;
          if (f.kind === "number") return String(el.value).trim() !== "";
          return String(el.value || "").trim() !== "";
        }}
        function renderPromptsFromSchema(snap) {{
          var sch = (snap && snap.prompts_inline_field_schema) || null;
          window._siteEditorPromptFieldSchema = sch;
          var ids = ["ed_pr_sub_start", "ed_pr_sub_a2", "ed_pr_sub_pipe", "ed_pr_sub_other"];
          ids.forEach(function(id) {{ var n = document.getElementById(id); if (n) n.innerHTML = ""; }});
          var oLbl = document.getElementById("ed_pr_sub_other_lbl");
          if (oLbl) oLbl.classList.add("d-none");
          if (!sch || typeof sch !== "object") {{
            var n0 = document.getElementById("ed_pr_sub_start");
            if (n0) n0.innerHTML = '<p class="text-warning small">No prompt field schema. Add <code>config/prompts/*.json</code> in the repo.</p>';
            return;
          }}
          var order = Object.keys(sch);
          order.sort();
          for (var oi = 0; oi < order.length; oi++) {{
            var pr = order[oi];
            var gid = _promptGroupContainerId(pr);
            var c = document.getElementById(gid);
            if (gid === "ed_pr_sub_other" && oLbl) oLbl.classList.remove("d-none");
            if (!c) continue;
            var block = document.createElement("div");
            block.className = "mb-3 border-bottom pb-2";
            var title = document.createElement("div");
            title.className = "fw-bold text-secondary small";
            title.textContent = pr;
            block.appendChild(title);
            var layerP = document.createElement("p");
            layerP.className = "form-text small mb-2";
            layerP.id = "ed_src_pr_" + pr;
            layerP.style.fontSize = "0.68rem";
            block.appendChild(layerP);
            var flist = sch[pr] || [];
            for (var fi = 0; fi < flist.length; fi++) {{
              var f = flist[fi];
              if (!f || !f.path) continue;
              var pid = _promptFieldDomId(pr, f.path);
              var wrap = document.createElement("div");
              wrap.className = "mb-2";
              var lab = document.createElement("label");
              lab.className = "form-label small text-muted d-block mb-0";
              lab.setAttribute("for", pid);
              lab.textContent = f.path + "  (" + (f.kind || "text") + ")";
              wrap.appendChild(lab);
              var el;
              var knd = f.kind || "text";
              if (knd === "bool") {{
                el = document.createElement("input");
                el.type = "checkbox";
                el.className = "form-check-input";
                el.id = pid;
              }} else if (knd === "number") {{
                el = document.createElement("input");
                el.type = "number";
                el.step = "any";
                el.className = "form-control form-control-sm";
                el.id = pid;
              }} else if (knd === "textarea" || knd === "json" || knd === "lines") {{
                el = document.createElement("textarea");
                el.className = "form-control form-control-sm" + (knd === "json" || knd === "lines" ? " font-monospace" : "");
                el.id = pid;
                el.spellcheck = false;
                if (knd === "json") el.rows = 5;
                else if (knd === "lines") el.rows = 4;
                else el.rows = 3;
              }} else {{
                el = document.createElement("input");
                el.type = "text";
                el.className = "form-control form-control-sm";
                el.id = pid;
                el.spellcheck = false;
              }}
              wrap.appendChild(el);
              var effHint = document.createElement("p");
              effHint.className = "form-text text-muted mb-0 d-none";
              effHint.id = "edeff_" + pr + "__" + String(f.path).replace(/\\./g, "__");
              effHint.style.fontSize = "0.68rem";
              effHint.setAttribute("aria-hidden", "true");
              wrap.appendChild(effHint);
              block.appendChild(wrap);
            }}
            c.appendChild(block);
          }}
        }}
        function _getNested(obj, path) {{
          if (!obj || !path) return undefined;
          var c = obj;
          var p = path.split(".");
          for (var i = 0; i < p.length; i++) {{ if (c == null) return undefined; c = c[p[i]]; }}
          return c;
        }}
        function _setNested(obj, path, val) {{
          if (!obj || !path) return;
          var p = path.split(".");
          var c = obj;
          for (var i = 0; i < p.length - 1; i++) {{
            var k = p[i];
            if (!c[k] || typeof c[k] !== "object" || c[k] === null) c[k] = {{}};
            c = c[k];
          }}
          c[p[p.length - 1]] = val;
        }}
        function _removeNestedPath(obj, path) {{
          if (!obj || !path) return;
          var p = path.split(".");
          function walk(o, d) {{
            if (o == null || typeof o !== "object") return;
            if (d === p.length - 1) {{ delete o[p[d]]; return; }}
            if (!(p[d] in o)) return;
            var ch = o[p[d]];
            walk(ch, d + 1);
            if (ch && typeof ch === "object" && !Array.isArray(ch) && !Object.keys(ch).length) delete o[p[d]];
          }}
          walk(obj, 0);
        }}
        function _pruneEmpty(obj) {{
          if (obj == null || typeof obj !== "object" || Array.isArray(obj)) return;
          for (var k in obj) {{ if (Object.prototype.hasOwnProperty.call(obj, k)) _pruneEmpty(obj[k]); }}
          for (var k2 in obj) {{
            if (Object.prototype.hasOwnProperty.call(obj, k2)) {{
              var v = obj[k2];
              if (v && typeof v === "object" && !Array.isArray(v) && !Object.keys(v).length) delete obj[k2];
            }}
          }}
        }}
        function _isDeepEmptyObject(o) {{
          if (o == null) return true;
          if (typeof o !== "object" || Array.isArray(o)) return false;
          return Object.keys(o).length === 0;
        }}
        function _fillPromptFieldsFromRow(s) {{
          if (!s || typeof s !== "object") return;
          var sch = window._siteEditorPromptFieldSchema;
          if (!sch) return;
          var pm = s.prompts || {{}};
          Object.keys(sch).forEach(function(pr) {{
            (sch[pr] || []).forEach(function(f) {{
              var el = document.getElementById(_promptFieldDomId(pr, f.path));
              if (!el) return;
              var node = pm[pr];
              var v = _getNested(node, f.path);
              var knd = f.kind || "text";
              if (knd === "bool") {{ el.checked = !!v; return; }}
              if (knd === "number") {{
                el.value = (v != null && v !== "" && !isNaN(Number(v))) ? String(v) : "";
                return;
              }}
              if (knd === "lines" && v && Array.isArray(v)) {{ el.value = v.join("\\n"); return; }}
              if (knd === "json") {{
                el.value = (v == null) ? "" : JSON.stringify(v, null, 2);
                return;
              }}
              el.value = (v == null) ? "" : String(v);
            }});
          }});
        }}
        function _readPromptsFromFormInto(bp, b) {{
          var sch = window._siteEditorPromptFieldSchema;
          if (!sch) return;
          Object.keys(sch).forEach(function(name) {{
            var fields = sch[name] || [];
            if (!fields.length) return;
            var anySet = fields.some(function(f) {{
              return _fieldIsNonEmpty(f, document.getElementById(_promptFieldDomId(name, f.path)));
            }});
            if (!anySet) {{ delete bp[name]; return; }}
            var m = (b.prompts && b.prompts[name] && typeof b.prompts[name] === "object")
              ? JSON.parse(JSON.stringify(b.prompts[name])) : {{}};
            fields.forEach(function(f) {{
              var e2 = document.getElementById(_promptFieldDomId(name, f.path));
              if (!e2) return;
              var knd = f.kind || "text";
              if (!_fieldIsNonEmpty(f, e2)) {{
                if (f.path.indexOf(".") === -1) delete m[f.path];
                else {{ _removeNestedPath(m, f.path); _pruneEmpty(m); }}
                return;
              }}
              if (knd === "bool") {{ _setNested(m, f.path, !!e2.checked); return; }}
              if (knd === "number") {{
                var n = Number(e2.value);
                if (isNaN(n)) throw new Error("prompts." + name + " " + f.path + ": not a number");
                _setNested(m, f.path, n);
                return;
              }}
              if (knd === "lines") {{
                var lines = String(e2.value).split(/\\r?\\n/).map(function(x) {{ return x.trim(); }}).filter(Boolean);
                _setNested(m, f.path, lines);
                return;
              }}
              if (knd === "json") {{
                try {{ _setNested(m, f.path, JSON.parse(e2.value.trim())); }}
                catch (err) {{ throw new Error("prompts." + name + " " + f.path + ": " + (err.message || err)); }}
                return;
              }}
              _setNested(m, f.path, String(e2.value));
            }});
            _pruneEmpty(m);
            if (_isDeepEmptyObject(m) || (typeof m === "object" && !Object.keys(m).length)) delete bp[name];
            else bp[name] = m;
          }});
        }}
        var PROVENANCE_FIELD_IDS = [
          "wordpress_url", "wordpress_user", "wordpress_app_password", "openai_api_key", "openai_model",
          "useapi_token", "useapi_midjourney_channel", "r2_account_id", "r2_access_key_id", "r2_secret_access_key",
          "r2_bucket", "r2_public_base_url"
        ];
        function _applyProvenanceToForm(snap) {{
          var prov = (snap && snap.keys_provenance) || {{}};
          PROVENANCE_FIELD_IDS.forEach(function(k) {{
            var e = document.getElementById("ed_src_" + k);
            if (e) e.textContent = prov[k] ? ("Key: " + k + " — " + prov[k]) : "";
          }});
          var ph = (snap && snap.prompts_form_hints) || {{}};
          PROMPT_FORM_KEYS.forEach(function(name) {{
            var e = document.getElementById("ed_src_pr_" + name);
            if (e) e.textContent = ph[name] ? ("Layers: " + ph[name]) : "";
          }});
        }}
        function _promptPathHasRowOverride(s, pr, path) {{
          if (!s || !pr || !path) return false;
          var node = s.prompts && s.prompts[pr];
          if (node == null || typeof node !== "object") return false;
          return _getNested(node, path) !== undefined;
        }}
        function _strEffForUi(v) {{
          if (v === null || v === undefined) return "";
          if (typeof v === "object") return JSON.stringify(v, null, 2);
          if (typeof v === "boolean") return v ? "true" : "false";
          return String(v);
        }}
        function _applyEffectivePromptPlaceholders(snap, s) {{
          var eff = (snap && snap.prompts_effective_by_path) || null;
          var excl = (snap && snap.prompts_excluding_row_inline_by_path) || null;
          if (!eff || typeof eff !== "object") return;
          if (!excl) excl = {{}};
          var sch = window._siteEditorPromptFieldSchema;
          if (!sch) return;
          Object.keys(sch).forEach(function(pr) {{
            var pmap = (eff[pr] && typeof eff[pr] === "object") ? eff[pr] : {{}};
            var xmap = (excl[pr] && typeof excl[pr] === "object") ? excl[pr] : {{}};
            (sch[pr] || []).forEach(function(f) {{
              if (!f || !f.path) return;
              var el = document.getElementById(_promptFieldDomId(pr, f.path));
              if (!el) return;
              var hintId = "edeff_" + pr + "__" + String(f.path).replace(/\\./g, "__");
              var hint = document.getElementById(hintId);
              if (!Object.prototype.hasOwnProperty.call(pmap, f.path)) {{
                if (f.kind === "bool") el.removeAttribute("title");
                else {{ el.placeholder = ""; el.removeAttribute("title"); }}
                if (hint) {{ hint.textContent = ""; hint.classList.add("d-none"); }}
                return;
              }}
              var pe = pmap[f.path];
              var xb = Object.prototype.hasOwnProperty.call(xmap, f.path) ? xmap[f.path] : undefined;
              var full = _strEffForUi(pe);
              var fullBase = (xb === undefined) ? "" : _strEffForUi(xb);
              var knd = f.kind || "text";
              var hasO = _promptPathHasRowOverride(s, pr, f.path);
              if (knd === "bool") {{
                if (hint) {{
                  if (!hasO) {{ hint.textContent = "No per-row value — effective merged: " + (pe ? "true" : "false") + "."; hint.classList.remove("d-none"); }}
                  else {{ hint.textContent = (xb === undefined) ? "Row overrides. No file baseline for this key (inline-only or nested)." : ("Row sets explicit checkbox. From file layers (no row inline): " + (xb ? "true" : "false") + "."); hint.classList.remove("d-none"); }}
                }}
                el.setAttribute("title", hasO
                  ? ((xb === undefined) ? "Effective merged (includes row): " + full : ("From file layers (no row inline `prompts`): " + fullBase + " — effective with row: " + full))
                  : ("Effective merged: " + full));
                return;
              }}
              if (!hasO) {{
                el.placeholder = (full.length > 220) ? (full.slice(0, 217) + "…") : full;
                el.setAttribute("title", "Merged when the row has no key for " + f.path + " (hover for full if truncated).\\n" + full);
                if (hint) {{ hint.textContent = (full.length > 160) ? ("Effective merged: " + full.slice(0, 157) + "…") : ("Effective merged: " + full); hint.classList.remove("d-none"); }}
              }} else {{
                el.placeholder = "";
                el.setAttribute("title", (xb === undefined) ? "Row overrides. Effective at this path: " + full
                  : "Row inline overrides. From file layers (no `prompts` in row): " + fullBase + "\\n--\\nWith row, effective: " + full);
                if (hint) {{ var hb = (fullBase.length > 100) ? fullBase.slice(0, 97) + "…" : fullBase; hint.textContent = (xb === undefined) ? "Row overrides. No separate file-baseline for this key." : ("Row overrides. File-layer baseline: " + hb); hint.classList.remove("d-none"); }}
              }}
            }});
          }});
        }}
        function siteEditorApplyKeepSecretsFromBase(base, o) {{
          if (!base || !o || typeof o !== "object") return;
          var keys = [
            "wordpress_app_password", "openai_api_key", "useapi_token", "useapi_midjourney_channel",
            "r2_account_id", "r2_access_key_id", "r2_secret_access_key", "r2_bucket", "r2_public_base_url"
          ];
          keys.forEach(function(k) {{
            var t = o[k] != null ? String(o[k]).trim() : "";
            if (t) return;
            if (base[k] != null && String(base[k]).trim() !== "") o[k] = base[k];
          }});
        }}
        function _getV(id) {{ var e = document.getElementById(id); return e ? (e.value || "").trim() : ""; }}
        function _setV(id, v) {{ var e = document.getElementById(id); if (e) e.value = (v != null && v !== undefined) ? String(v) : ""; }}
        function _rowStr(s, k) {{
          if (!s || typeof s !== "object" || !k) return "";
          var x = s[k];
          if (x == null) return "";
          return String(x).trim();
        }}
        function _setPh(id, text) {{
          var e = document.getElementById(id);
          if (!e) return;
          e.placeholder = text != null ? String(text) : "";
          if (text) e.setAttribute("title", "Effective merged (what the run uses): " + String(text).slice(0, 400));
          else e.removeAttribute("title");
        }}
        function _fillOrPlaceholder(s, kf, rowKey, elId) {{
          var r = _rowStr(s, rowKey);
          if (r) {{ _setV(elId, r); _setPh(elId, ""); return; }}
          _setV(elId, "");
          var m = (kf && kf[rowKey] != null) ? kf[rowKey] : null;
          var hint = (m != null && String(m).trim() !== "") ? String(m) : "";
          if (!hint) hint = "(not on this row — use merged keys: open the API & R2 tab for placeholders / Source lines.)";
          _setPh(elId, hint);
        }}
        function _fillSecretOrPh(s, kf, rowKey, elId) {{
          var r = _rowStr(s, rowKey);
          if (r) {{ _setV(elId, r); _setPh(elId, "leave blank=keep; replace to change in row"); return; }}
          _setV(elId, "");
          var m = (kf && kf[rowKey] != null) ? kf[rowKey] : null;
          var hint = (m != null && String(m).trim() !== "")
            ? String(m)
            : "(not on row — merged from shared / project / env. See the API & R2 tab. Leave empty to not store in row.)";
          _setPh(elId, hint);
        }}
        function siteEditorFillForm(s, snap) {{
          if (!s || typeof s !== "object") return;
          var kf = (snap && snap.keys && typeof snap.keys === "object") ? snap.keys : {{}};
          _setV("ed_id", s.id);
          _setV("ed_display_name", s.display_name);
          _setV("ed_out_dir", s.out_dir);
          _setV("ed_start_file", s.start_file);
          _setV("ed_log_id", s.log_id);
          _setV("ed_prompts_dir", s.prompts_dir);
          _fillOrPlaceholder(s, kf, "wordpress_url", "ed_wordpress_url");
          _fillOrPlaceholder(s, kf, "wordpress_user", "ed_wordpress_user");
          _setV("ed_wordpress_app_password", "");
          _setPh("ed_wordpress_app_password", _rowStr(s, "wordpress_app_password")
            ? "leave blank=keep; replace to change in row"
            : ((kf.wordpress_app_password != null && String(kf.wordpress_app_password).trim() !== "")
                ? String(kf.wordpress_app_password)
                : "blank=keep; effective from merged keys (if set)"));
          _fillSecretOrPh(s, kf, "openai_api_key", "ed_openai_api_key");
          _fillOrPlaceholder(s, kf, "openai_model", "ed_openai_model");
          _fillSecretOrPh(s, kf, "useapi_token", "ed_useapi_token");
          _fillOrPlaceholder(s, kf, "useapi_midjourney_channel", "ed_useapi_midjourney_channel");
          _fillOrPlaceholder(s, kf, "r2_account_id", "ed_r2_account_id");
          _fillSecretOrPh(s, kf, "r2_access_key_id", "ed_r2_access_key_id");
          _fillSecretOrPh(s, kf, "r2_secret_access_key", "ed_r2_secret_access_key");
          _fillOrPlaceholder(s, kf, "r2_bucket", "ed_r2_bucket");
          _fillOrPlaceholder(s, kf, "r2_public_base_url", "ed_r2_public_base_url");
          var nss = document.getElementById("ed_no_shared_settings");
          if (nss) nss.checked = !!s.no_shared_settings;
          var nsp = document.getElementById("ed_no_shared_prompts");
          if (nsp) nsp.checked = !!s.no_shared_prompts;
          var es = s.settings;
          _setV("ed_settings_json", (es && typeof es === "object") ? JSON.stringify(es, null, 2) : "");
          var stSet = document.getElementById("ed_settings_json");
          var mset = (snap && snap.settings) ? JSON.stringify(snap.settings, null, 2) : "";
          if (!es || typeof es !== "object") {{
            if (mset && mset.length) {{
              _setPh("ed_settings_json", mset.length > 520 ? mset.slice(0, 517) + "…" : mset);
              if (stSet) stSet.setAttribute("title", "Merged settings if you leave this field empty. Full JSON in hover.\\n" + mset);
            }} else {{
              _setPh("ed_settings_json", "Empty = use merged project settings. Paste {{}} to clear a previous row override.");
              if (stSet) stSet.removeAttribute("title");
            }}
          }} else {{ _setPh("ed_settings_json", ""); if (stSet) stSet.removeAttribute("title"); }}
          renderPromptsFromSchema(snap);
          _fillPromptFieldsFromRow(s);
          _applyProvenanceToForm(snap);
          _applyEffectivePromptPlaceholders(snap, s);
        }}
        function siteEditorReadMerged() {{
          var b = _siteEditorBase;
          if (!b) return null;
          var o = JSON.parse(JSON.stringify(b));
          var sk = ["display_name","out_dir","start_file","log_id","prompts_dir","wordpress_url","wordpress_user","openai_model"];
          sk.forEach(function(k) {{ var v = _getV("ed_" + k); if (v) o[k] = v; else if (b[k] !== undefined) o[k] = b[k]; }});
          var pass = _getV("ed_wordpress_app_password");
          if (pass) o.wordpress_app_password = pass;
          var sec = ["openai_api_key","useapi_token","useapi_midjourney_channel","r2_account_id","r2_access_key_id","r2_secret_access_key","r2_bucket","r2_public_base_url"];
          sec.forEach(function(k) {{
            var v = _getV("ed_" + k);
            if (v) o[k] = v; else if (b[k] !== undefined) o[k] = b[k];
          }});
          var nss = document.getElementById("ed_no_shared_settings");
          if (nss && nss.checked) o.no_shared_settings = true; else delete o.no_shared_settings;
          var nsp = document.getElementById("ed_no_shared_prompts");
          if (nsp && nsp.checked) o.no_shared_prompts = true; else delete o.no_shared_prompts;
          var stEl = document.getElementById("ed_settings_json");
          var st = (stEl && stEl.value) ? stEl.value.trim() : "";
          if (st) {{ try {{ o.settings = JSON.parse(st); }} catch (e) {{ throw new Error("settings JSON: " + e.message); }} }}
          else {{ if (b.settings) o.settings = JSON.parse(JSON.stringify(b.settings)); else delete o.settings; }}
          var bp = (b.prompts && typeof b.prompts === "object") ? JSON.parse(JSON.stringify(b.prompts)) : {{}};
          _readPromptsFromFormInto(bp, b);
          if (Object.keys(bp).length) o.prompts = bp; else delete o.prompts;
          if (!_getV("ed_id")) {{ throw new Error("id is required"); }}
          o.id = _getV("ed_id");
          return o;
        }}
        function showSiteConfigInfo(projectLabel) {{
          _siteEditorProject = projectLabel;
          _siteEditorBase = null;
          _siteEditorRawDirty = false;
          var fe = document.getElementById("siteEditorFetchErr");
          var ta = document.getElementById("siteEditorRaw");
          var saveBtn = document.getElementById("siteEditorSaveBtn");
          var formPane = document.getElementById("siteEditorFormPane");
          var formMissing = document.getElementById("siteEditorFormMissing");
          var titleEl = document.getElementById("siteConfigModalLabel");
          if (titleEl) titleEl.textContent = "Project — " + projectLabel;
          if (fe) {{ fe.classList.add("d-none"); fe.textContent = ""; }}
          if (ta) {{ ta.value = ""; ta.disabled = true; }}
          if (formPane) formPane.classList.add("d-none");
          if (formMissing) {{ formMissing.classList.add("d-none"); }}
          if (saveBtn) saveBtn.disabled = true;
          var mEl = document.getElementById("siteConfigModal");
          if (!mEl) return;
          if (typeof bootstrap === "undefined") {{
            if (fe) {{ fe.classList.remove("d-none"); fe.textContent = "Bootstrap is not loaded."; }}
            return;
          }}
          new bootstrap.Modal(mEl).show();
          var tabP = document.getElementById("tab-se-proj");
          if (tabP) {{ var tr = new bootstrap.Tab(tabP); tr.show(); }}
          fetch("/api/site-editor?project=" + encodeURIComponent(projectLabel))
            .then(function(r) {{ if (!r.ok) return r.text().then(function(t) {{ throw new Error(t || "HTTP " + r.status); }}); return r.json(); }})
            .then(function(data) {{
              if (fe) fe.classList.add("d-none");
              if (data.raw_site) {{
                _siteEditorBase = data.raw_site;
                _siteEditorRawDirty = false;
                siteEditorFillForm(data.raw_site, data.snapshot || null);
                if (ta) {{ ta.value = JSON.stringify(data.raw_site, null, 2); ta.disabled = false; }}
                if (formPane) formPane.classList.remove("d-none");
                if (formMissing) formMissing.classList.add("d-none");
                if (saveBtn) saveBtn.disabled = false;
              }} else {{
                if (ta) {{ ta.value = ""; }}
                if (formMissing) formMissing.classList.remove("d-none");
              }}
            }})
            .catch(function(e) {{ var fe2 = document.getElementById("siteEditorFetchErr"); if (fe2) {{ fe2.classList.remove("d-none"); fe2.textContent = "Error: " + (e && e.message ? e.message : e); }} }});
        }}
        function siteEditorSave() {{
          if (!_siteEditorProject) return;
          var obj = null;
          var ta0 = document.getElementById("siteEditorRaw");
          if (_siteEditorBase) {{
            if (_siteEditorRawDirty && ta0 && !ta0.disabled && (ta0.value || "").trim()) {{
              try {{
                obj = JSON.parse(ta0.value.trim());
                if (obj == null || typeof obj !== "object" || Array.isArray(obj)) throw new Error("Site must be a JSON object");
                siteEditorApplyKeepSecretsFromBase(_siteEditorBase, obj);
              }} catch (e) {{ alert(e.message || e); return; }}
            }} else {{
              try {{ obj = siteEditorReadMerged(); }} catch (e) {{ alert(e.message || e); return; }}
            }}
          }} else {{
            if (!ta0 || !ta0.value || ta0.disabled) {{ alert("Nothing to save"); return; }}
            try {{ obj = JSON.parse(ta0.value.trim()); }} catch (e) {{ alert("Invalid JSON: " + e); return; }}
          }}
          if (typeof obj !== "object" || obj === null || Array.isArray(obj)) {{ alert("Site must be a JSON object"); return; }}
          fetch("/api/site-editor", {{
            method: "POST",
            headers: {{ "Content-Type": "application/json" }},
            body: JSON.stringify({{ project: _siteEditorProject, raw_site: obj }})
          }})
            .then(function(r) {{ return r.json().then(function(j) {{ if (!r.ok) throw new Error(j.error || r.status); return j; }}); }})
            .then(function() {{ alert("Saved to config/sites.json. Refresh the page if the label changed."); }})
            .catch(function(e) {{ alert("Save failed: " + e); }});
        }}
        document.addEventListener("DOMContentLoaded", function() {{
          refreshAllProjectStats();
          var fp = document.getElementById("siteEditorFormPane");
          if (fp) fp.addEventListener("input", function() {{ _siteEditorRawDirty = false; }}, true);
          var taR = document.getElementById("siteEditorRaw");
          if (taR) taR.addEventListener("input", function() {{ _siteEditorRawDirty = true; }});
        }});
      </script>
    </head>
    <body>
      <div class="materio-sidebar">
        <div class="sidebar-title">
          <i class='bx bx-grid-alt'></i>
          <span>AUTOMATION</span>
        </div>
        <ul>
          <li><a href="/"><i class='bx bx-home-alt'></i> Dashboard</a></li>
          <li><a href="/manage_sites"><i class='bx bx-list-ul'></i> Projects (sites)</a></li>
          <li><a href="/manage_starts"><i class='bx bx-table'></i> Manage STARTS</a></li>
          <li><a href="/manage_recipes"><i class='bx bx-food-menu'></i> Manage Recipes</a></li>
          <li><a href="/manage_images"><i class='bx bx-image'></i> Manage Images</a></li>
          <li><a href="/manage_articles"><i class='bx bx-file'></i> Manage Articles</a></li>
        </ul>
      </div>

      <div class="navbar-materio">
        <h5>Dashboard</h5>
        <div>
          <i class='bx bx-bell' style="font-size: 20px; margin-right: 20px;'></i>
          <i class='bx bx-user-circle' style="font-size: 24px;"></i>
        </div>
      </div>

      <div class="materio-content">
        <div class="card mb-4">
          <div class="card-header">
            <strong>Bulk Recipe Titles - Preview & Review</strong>
          </div>
          <div class="card-body">
            <form id="previewForm" action="/upload_titles" method="post">
              <label for="titles" class="form-label">Enter Titles (one per line)</label>
              <textarea id="titles" name="titles" class="form-control mb-2" rows="3"></textarea>
              <div id="titleCount" class="text-muted mb-2">0 titles</div>
              <button class="btn btn-primary" type="submit">Preview</button>
            </form>
            <div id="previewResult" class="mt-3"></div>
            <button class="btn btn-success mt-3" id="confirmBtn" style="display:none;">Confirm & Upload</button>
            <div id="finalResult" class="mt-3"></div>
          </div>
        </div>

        <div class="card mb-4">
          <div class="card-header">
            <strong>Actions</strong>
          </div>
          <div class="card-body">
            <button class="number-button" data-number="1" onclick="startLog('/stream-all-start', this)">START</button>
            <button class="number-button" data-number="2" onclick="startLog('/stream-all-json', this)">JSON</button>
            <button class="number-button" data-number="2" onclick="startLog('/stream-all-prompt', this)">PROMPT</button>
            <button class="number-button" data-number="ALL" onclick="startLog('/stream-imagine-all', this)">IMAGINE ALL</button>
            <button class="number-button" data-number="3" onclick="startLog('/stream-imagine-group1', this)">IMAGINE 1</button>
            <button class="number-button" data-number="4" onclick="startLog('/stream-imagine-group2', this)">IMAGINE 2</button>
            <button class="number-button" data-number="5" onclick="startLog('/stream-imagine-group3', this)">IMAGINE 3</button>
            <button class="number-button" data-number="6" onclick="startLog('/stream-imagine-group4', this)">IMAGINE 4</button>
            <button class="number-button" data-number="7" onclick="startLog('/stream-imagine-group5', this)">IMAGINE 5</button>
            <button class="number-button" data-number="8" onclick="startLog('/stream-imagine-group6', this)">IMAGINE 6</button>
            <button class="number-button" data-number="9" onclick="startLog('/stream-imagine-group7', this)">IMAGINE 7</button>
            <button class="number-button" data-number="10" onclick="startLog('/stream-imagine-group8', this)">IMAGINE 8</button>
            <button class="number-button" data-number="11" onclick="startLog('/stream-imagine-group9', this)">IMAGINE 9</button>
            <button class="number-button" data-number="12" onclick="startLog('/stream-imagine-group10', this)">IMAGINE 10</button>
            <button class="number-button" data-number="13" onclick="startLog('/stream-imagine-group11', this)">IMAGINE 11</button>
            <button class="number-button" data-number="14" onclick="startLog('/stream-imagine-group12', this)">IMAGINE 12</button>
            <button class="number-button" data-number="15" onclick="startLog('/stream-imagine-group13', this)">IMAGINE 13</button>
            <button class="number-button" data-number="16" onclick="startLog('/stream-imagine-group14', this)">IMAGINE 14</button>
            <button class="number-button" data-number="17" onclick="startLog('/stream-imagine-group15', this)">IMAGINE 15</button>
            <button class="number-button" data-number="18" onclick="startLog('/stream-imagine-group16', this)">IMAGINE 16</button>
            <button class="number-button" data-number="19" onclick="startLog('/stream-imagine-group17', this)">IMAGINE 17</button>
            <button class="number-button" onclick="clearFailed()">CLEAR IMAGINE</button>
            <button class="number-button" data-number="8" onclick="startLog('/stream_start2', this)">START2</button>

            <!-- ARTICLES, PIN DATA, WP UPLOAD: كلهم 10 ب 10 -->
            <button class="number-button" data-number="9" onclick="startLog('/stream-all-article', this)">ARTICLE</button>
            <button class="number-button" data-number="10" onclick="startLog('/stream-all-pin-data', this)">PIN DATA</button>
            <button class="number-button" data-number="11" onclick="startLog('/stream-all-pin-image', this)">PIN IMAGE</button>
            <button class="number-button" data-number="12" onclick="startLog('/stream-all-wp-upload', this)">WP UPLOAD</button>
            <button class="number-button" data-number="13" onclick="startLog('/stream-all-pin-bulk', this)">PIN BULK</button>

            <form action="/delete-all-folder" method="post" style="display:inline-block;">
              <button class="btn btn-secondary ms-2" type="submit">Delete 'ALL'</button>
            </form>
          </div>
        </div>

        <div class="row">
          {log_boxes}
        </div>

        <div class="modal fade" id="siteConfigModal" tabindex="-1" aria-hidden="true">
          <div class="modal-dialog modal-xl modal-dialog-scrollable">
            <div class="modal-content">
              <div class="modal-header">
                <h5 class="modal-title" id="siteConfigModalLabel">Project</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
              </div>
              <div class="modal-body p-0">
                <div class="px-3 pt-2 pb-1 border-bottom bg-light">
                  <div class="alert alert-info py-2 small mb-2">
                    Edits the <strong>one site object</strong> in <code>config/sites.json</code>. Use the tabs: <strong>Project</strong> (ids, paths) → <strong>WordPress</strong> → <strong>API &amp; R2</strong> (IMAGINE / UseAPI) → <strong>Settings</strong> → <strong>Start (a1)</strong> → <strong>JSON (a2)</strong> (JSON + text prompts) → <strong>Pipeline (a4–a8)</strong> → <strong>Row JSON</strong>. <strong>Save</strong> stores the row. Empty fields and gray placeholders use merged values from shared + project + files; see “Layers” and hints under each prompt block.
                  </div>
                  <p id="siteEditorFetchErr" class="text-danger small mb-2 d-none" role="alert"></p>
                  <p id="siteEditorFormMissing" class="text-warning small d-none mb-0">No <code>config/sites.json</code> row for this card. Add sites in <a href="/manage_sites" target="_blank">Projects (sites)</a>.</p>
                </div>
                <div id="siteEditorFormPane" class="d-none">
                  <div class="overflow-x-auto border-bottom" style="white-space: nowrap;">
                    <ul class="nav nav-tabs site-editor-top-tabs border-0 flex-nowrap px-2 pt-1 mb-0" id="siteEditorTopTabs" role="tablist" style="min-width: min-content; flex-wrap: nowrap;">
                      <li class="nav-item" role="presentation">
                        <button class="nav-link active" id="tab-se-proj" data-bs-toggle="tab" data-bs-target="#pane-se-proj" type="button" role="tab" aria-selected="true">Project</button>
                      </li>
                      <li class="nav-item" role="presentation">
                        <button class="nav-link" id="tab-se-wp" data-bs-toggle="tab" data-bs-target="#pane-se-wp" type="button" role="tab">WordPress</button>
                      </li>
                      <li class="nav-item" role="presentation">
                        <button class="nav-link" id="tab-se-api" data-bs-toggle="tab" data-bs-target="#pane-se-api" type="button" role="tab">API &amp; R2</button>
                      </li>
                      <li class="nav-item" role="presentation">
                        <button class="nav-link" id="tab-se-st" data-bs-toggle="tab" data-bs-target="#pane-se-st" type="button" role="tab">Settings</button>
                      </li>
                      <li class="nav-item" role="presentation">
                        <button class="nav-link" id="tab-se-p1" data-bs-toggle="tab" data-bs-target="#pane-se-p1" type="button" role="tab">a1 Start</button>
                      </li>
                      <li class="nav-item" role="presentation">
                        <button class="nav-link" id="tab-se-p2" data-bs-toggle="tab" data-bs-target="#pane-se-p2" type="button" role="tab">a2 JSON + prompt</button>
                      </li>
                      <li class="nav-item" role="presentation">
                        <button class="nav-link" id="tab-se-pp" data-bs-toggle="tab" data-bs-target="#pane-se-pp" type="button" role="tab">Pipeline a4–a8</button>
                      </li>
                      <li class="nav-item" role="presentation">
                        <button class="nav-link" id="tab-se-adv" data-bs-toggle="tab" data-bs-target="#pane-se-adv" type="button" role="tab">Row JSON</button>
                      </li>
                    </ul>
                  </div>
                  <div class="tab-content site-editor-form-tab-content px-3 py-2" id="siteEditorFormTabContent" style="max-height: min(62vh, 680px); overflow-y: auto;">
                    <div class="tab-pane fade show active" id="pane-se-proj" role="tabpanel" aria-labelledby="tab-se-proj">
                      <p class="text-muted small">Site <code>id</code> and output paths. Matches <code>config/sites.json</code> for this dashboard card.</p>
                      <div class="row g-2">
                        <div class="col-md-2 col-6"><label class="form-label">id</label><input id="ed_id" class="form-control form-control-sm" required /></div>
                        <div class="col-md-3 col-6"><label class="form-label">display_name</label><input id="ed_display_name" class="form-control form-control-sm" /></div>
                        <div class="col-md-3 col-6"><label class="form-label">out_dir</label><input id="ed_out_dir" class="form-control form-control-sm" /></div>
                        <div class="col-md-2 col-6"><label class="form-label">start_file</label><input id="ed_start_file" class="form-control form-control-sm" placeholder="xlsx" /></div>
                        <div class="col-md-2 col-6"><label class="form-label">log_id</label><input id="ed_log_id" class="form-control form-control-sm" /></div>
                        <div class="col-md-3 col-6"><label class="form-label">prompts_dir</label><input id="ed_prompts_dir" class="form-control form-control-sm" placeholder="config/site_prompts/…" /></div>
                      </div>
                    </div>
                    <div class="tab-pane fade" id="pane-se-wp" role="tabpanel" aria-labelledby="tab-se-wp">
                      <h6 class="text-secondary small text-uppercase">WordPress</h6>
                      <p class="text-muted small mb-2">Not in <code>shared_keys</code> — this row, or <code>WP_URL</code> / <code>WP_USER</code> / <code>WP_APP_PASSWORD</code> in env. Blank app password = keep the value already in <code>sites.json</code>.</p>
                      <div class="row g-2">
                        <div class="col-md-4">
                          <label class="form-label small mb-0">Site URL <span class="text-muted">(wordpress_url)</span></label>
                          <input id="ed_wordpress_url" class="form-control form-control-sm" autocomplete="off" />
                          <p class="form-text mb-0" id="ed_src_wordpress_url" style="font-size:0.7rem"></p>
                        </div>
                        <div class="col-md-3">
                          <label class="form-label small mb-0">User</label>
                          <input id="ed_wordpress_user" class="form-control form-control-sm" autocomplete="off" />
                          <p class="form-text mb-0" id="ed_src_wordpress_user" style="font-size:0.7rem"></p>
                        </div>
                        <div class="col-md-5">
                          <label class="form-label small mb-0">App password</label>
                          <input id="ed_wordpress_app_password" class="form-control form-control-sm" type="text" autocomplete="off" />
                          <p class="form-text mb-0" id="ed_src_wordpress_app_password" style="font-size:0.7rem"></p>
                        </div>
                      </div>
                    </div>
                    <div class="tab-pane fade" id="pane-se-api" role="tabpanel" aria-labelledby="tab-se-api">
                      <h6 class="text-secondary small text-uppercase">OpenAI · UseAPI (IMAGINE) · R2</h6>
                      <p class="text-muted small mb-2">IMAGINE / Midjourney actions use the <strong>MJ channel</strong> and <strong>UseAPI</strong> fields here. Gray placeholders: merged from <code>shared_keys.json</code> + project <code>keys.json</code> + this row. “Source” lines show where each key came from.</p>
                      <div class="row g-2 mb-1">
                        <div class="col-md-4">
                          <label class="form-label small mb-0">OpenAI API key</label>
                          <input id="ed_openai_api_key" class="form-control form-control-sm" type="text" spellcheck="false" autocomplete="off" />
                          <p class="form-text mb-0" id="ed_src_openai_api_key" style="font-size:0.7rem"></p>
                        </div>
                        <div class="col-md-2">
                          <label class="form-label small mb-0">Model</label>
                          <input id="ed_openai_model" class="form-control form-control-sm" spellcheck="false" autocomplete="off" />
                          <p class="form-text mb-0" id="ed_src_openai_model" style="font-size:0.7rem"></p>
                        </div>
                        <div class="col-md-3">
                          <label class="form-label small mb-0">UseAPI token</label>
                          <input id="ed_useapi_token" class="form-control form-control-sm" type="text" spellcheck="false" autocomplete="off" />
                          <p class="form-text mb-0" id="ed_src_useapi_token" style="font-size:0.7rem"></p>
                        </div>
                        <div class="col-md-3">
                          <label class="form-label small mb-0">Midjourney channel</label>
                          <input id="ed_useapi_midjourney_channel" class="form-control form-control-sm" spellcheck="false" autocomplete="off" />
                          <p class="form-text mb-0" id="ed_src_useapi_midjourney_channel" style="font-size:0.7rem"></p>
                        </div>
                      </div>
                      <div class="row g-2">
                        <div class="col-md-2 col-6">
                          <label class="form-label small mb-0">R2 account</label>
                          <input id="ed_r2_account_id" class="form-control form-control-sm" spellcheck="false" autocomplete="off" />
                          <p class="form-text mb-0" id="ed_src_r2_account_id" style="font-size:0.7rem"></p>
                        </div>
                        <div class="col-md-2 col-6">
                          <label class="form-label small mb-0">R2 access key</label>
                          <input id="ed_r2_access_key_id" class="form-control form-control-sm" type="text" spellcheck="false" autocomplete="off" />
                          <p class="form-text mb-0" id="ed_src_r2_access_key_id" style="font-size:0.7rem"></p>
                        </div>
                        <div class="col-md-2 col-6">
                          <label class="form-label small mb-0">R2 secret</label>
                          <input id="ed_r2_secret_access_key" class="form-control form-control-sm" type="text" spellcheck="false" autocomplete="off" />
                          <p class="form-text mb-0" id="ed_src_r2_secret_access_key" style="font-size:0.7rem"></p>
                        </div>
                        <div class="col-md-2 col-6">
                          <label class="form-label small mb-0">R2 bucket</label>
                          <input id="ed_r2_bucket" class="form-control form-control-sm" spellcheck="false" autocomplete="off" />
                          <p class="form-text mb-0" id="ed_src_r2_bucket" style="font-size:0.7rem"></p>
                        </div>
                        <div class="col-md-4">
                          <label class="form-label small mb-0">R2 public URL</label>
                          <input id="ed_r2_public_base_url" class="form-control form-control-sm" spellcheck="false" autocomplete="off" />
                          <p class="form-text mb-0" id="ed_src_r2_public_base_url" style="font-size:0.7rem"></p>
                        </div>
                      </div>
                    </div>
                    <div class="tab-pane fade" id="pane-se-st" role="tabpanel" aria-labelledby="tab-se-st">
                      <h6 class="text-secondary small text-uppercase">Settings merge + row object</h6>
                      <p class="text-muted small mb-2">Toggles and optional per-row <code>settings</code> JSON. Empty = use merged project settings; placeholder shows the merged object.</p>
                      <div class="border rounded p-2 mb-3 small">
                        <div class="form-check mb-1">
                          <input class="form-check-input" type="checkbox" id="ed_no_shared_settings" name="x" value="1" />
                          <label class="form-check-label" for="ed_no_shared_settings"><code>no_shared_settings</code> — do not load <code>config/shared_settings.json</code> (use project <code>settings.json</code> + this row only).</label>
                        </div>
                        <div class="form-check mb-0">
                          <input class="form-check-input" type="checkbox" id="ed_no_shared_prompts" name="x" value="1" />
                          <label class="form-check-label" for="ed_no_shared_prompts"><code>no_shared_prompts</code> — do not load repo <code>config/prompts/*.json</code> (project <code>config/prompts</code> + <code>site_prompts/…</code> + row inline <code>prompts</code> still apply).</label>
                        </div>
                      </div>
                      <label class="form-label small">Override <code>settings</code> (JSON) on this row</label>
                      <textarea id="ed_settings_json" class="form-control form-control-sm font-monospace" rows="8" spellcheck="false" placeholder="{{}}"></textarea>
                    </div>
                    <div class="tab-pane fade" id="pane-se-p1" role="tabpanel" aria-labelledby="tab-se-p1">
                      <h6 class="text-secondary small text-uppercase">START — a1_start</h6>
                      <p class="text-muted small mb-2">Fields from <code>config/prompts/a1_start.json</code> shape. Merged on save with file layers; “Layers” under each name shows the merge order.</p>
                      <div id="ed_pr_sub_start"></div>
                    </div>
                    <div class="tab-pane fade" id="pane-se-p2" role="tabpanel" aria-labelledby="tab-se-p2">
                      <h6 class="text-secondary small text-uppercase">a2 — JSON + prompt (PROMPT / IMAGINE text)</h6>
                      <p class="text-muted small mb-2"><code>a2_json</code> and <code>a2_prompt</code>: same names as the dashboard JSON / PROMPT steps. IMAGINE buttons use the UseAPI + Midjourney settings in <strong>API &amp; R2</strong>.</p>
                      <div id="ed_pr_sub_a2"></div>
                    </div>
                    <div class="tab-pane fade" id="pane-se-pp" role="tabpanel" aria-labelledby="tab-se-pp">
                      <h6 class="text-secondary small text-uppercase">a4, a5, a8 — articles, pin data, pin bulk</h6>
                      <p class="text-muted small mb-2">Pipeline prompts (ARTICLE, PIN DATA, PIN BULK on the dashboard). “Other” captures any future prompt name not listed above.</p>
                      <div id="ed_pr_sub_pipe" class="mb-2"></div>
                      <p id="ed_pr_sub_other_lbl" class="text-muted small d-none">Other script prompt(s) in the repo</p>
                      <div id="ed_pr_sub_other" class="mb-1"></div>
                    </div>
                    <div class="tab-pane fade" id="pane-se-adv" role="tabpanel" aria-labelledby="tab-se-adv">
                      <h6 class="text-secondary small text-uppercase">Full row JSON</h6>
                      <p class="text-muted small mb-2">The exact object saved in <code>config/sites.json</code>. If you edit here, the raw text wins on <strong>Save</strong> (unless the form is edited afterward — then the form merge is used). Leave secrets blank in the form to keep existing file values when saving from the form.</p>
                      <textarea id="siteEditorRaw" class="form-control font-monospace" style="min-height: 200px; font-size: 11px;" spellcheck="false" disabled></textarea>
                    </div>
                  </div>
                </div>
              </div>
              <div class="modal-footer">
                <button type="button" class="btn btn-primary" id="siteEditorSaveBtn" onclick="siteEditorSave()" disabled>Save to <code>config/sites.json</code></button>
                <a href="/manage_sites" class="btn btn-outline-secondary" target="_blank" rel="noopener">Full projects form</a>
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
              </div>
            </div>
          </div>
        </div>

        <div class="modal fade" id="columnDetailsModal" tabindex="-1" aria-hidden="true">
          <div class="modal-dialog modal-xl modal-dialog-scrollable">
            <div class="modal-content">
              <div class="modal-header">
                <h5 class="modal-title" id="columnDetailsTitle">Column Details</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
              </div>
              <div class="modal-body" id="columnDetailsBody">
                <div class="text-muted">Loading...</div>
              </div>
              <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
              </div>
            </div>
          </div>
        </div>

      </div>
      <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.0.2/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """
# ---- Patch: Ensure IMAGINE ALL button turns green after batches complete ----
try:
    _orig_generate_log_in_batches = generate_log_in_batches
    def generate_log_in_batches(script_names, batch_size=3, env_extra=None):
        for chunk in _orig_generate_log_in_batches(script_names, batch_size=batch_size, env_extra=env_extra):
            yield chunk
        # السطر اللي كيسالي وكيخلي الزرّ يخضر
        yield "data: " + json.dumps({"folder": "all", "line": "Finished all processes."}) + "\n\n"
except NameError:
    pass


if __name__ == "__main__":
    app.run(debug=True, threaded=True)
