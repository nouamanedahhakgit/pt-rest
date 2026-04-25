import os
import shutil
import subprocess
import threading
import queue
import json
import re
from flask import Flask, Response, request, jsonify, stream_with_context
import openpyxl
import openai
import sys
import time
import random
import logging
from typing import Callable, Any, Optional


app = Flask(__name__)

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
    return Response(
        generate_log_parallel(jobs_for_start1_all_except_s2()), mimetype="text/event-stream"
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
    كيمسح أي صف فـ images.xlsx إذا:
      - 'statu' = FAILED أو خاوي
      - أو 'statu_ing' = FAILED أو خاوي
    إذا كاين غير واحد فيهم، خدام. إذا جوج ما كاينينش كيرجع رسالة مناسبة.
    """
    results = {}
    for project in flat_ui_labels():
        out_folder = all_out_name_for_label(project)
        file_path = os.path.join(os.getcwd(), "ALL", out_folder, "images.xlsx")

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
        file_path = os.path.join(
            os.getcwd(), "ALL", all_out_name_for_label(project), "images.xlsx"
        )
        if not os.path.exists(file_path):
            html += f"""
            <div class="col">
              <div class="card h-100 mb-4">
                <div class="card-body">
                  <h4 class="card-title">{project}</h4>
                  <p class="card-text text-danger">images.xlsx not found.</p>
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

    file_path = os.path.join(
        os.getcwd(), "ALL", all_out_name_for_label(project), "images.xlsx"
    )
    if not os.path.exists(file_path):
        return f"<h1>images.xlsx not found for {project}</h1><a href='/manage_images'>Back</a>"

    wb = openpyxl.load_workbook(file_path)
    sheet = wb.active

    if 2 <= row_number <= sheet.max_row:
        sheet.delete_rows(row_number, 1)
        wb.save(file_path)
        return f"<h1>Row {row_number} deleted from {project}'s images.xlsx</h1>"
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
    project_folders_json = json.dumps([u["log_id"] for u in _units])

    log_boxes = ""
    for u in _units:
        lid = u["log_id"]
        title = u["label"]
        lidj = json.dumps(lid)
        titlej = json.dumps(title)
        log_boxes += f"""
          <div class="col-lg-6 mb-4">
            <div class="card h-100">
              <div class="card-header">
                <h6 class="mb-0 text-secondary">{title} Log</h6>
              </div>
              <div class="card-body overflow-auto" style="height:200px;" id="log_{lid}"></div>
              <div class="card-footer">
                <button class="btn btn-sm btn-primary project-action" onclick="startProjectAction({lidj}, {titlej}, 'start', this)">START</button>
                <button class="btn btn-sm btn-secondary project-action" onclick="startProjectAction({lidj}, {titlej}, 'json', this)">JSON</button>
                <button class="btn btn-sm btn-warning project-action" onclick="startProjectAction({lidj}, {titlej}, 'prompt', this)">PROMPT</button>
                <button class="btn btn-sm btn-info project-action" onclick="startProjectAction({lidj}, {titlej}, 'imagine', this)">IMAGINE</button>
                <button class="btn btn-sm btn-success project-action" onclick="startProjectAction({lidj}, {titlej}, 'article', this)">ARTICLE</button>
                <button class="btn btn-sm btn-dark project-action" onclick="startProjectAction({lidj}, {titlej}, 'pin_data', this)">PIN DATA</button>
                <button class="btn btn-sm btn-dark project-action" onclick="startProjectAction({lidj}, {titlej}, 'pin_image', this)">PIN IMAGE</button>
                <button class="btn btn-sm btn-dark project-action" onclick="startProjectAction({lidj}, {titlej}, 'wp_upload', this)">WP UPLOAD</button>
                <button class="btn btn-sm btn-dark project-action" onclick="startProjectAction({lidj}, {titlej}, 'pin_bulk', this)">PIN BULK</button>
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
      </style>
      <script>
        var source = null;
        var projectFolders = {project_folders_json};
        var numXlsx = {num_xlsx};

        function disableActionButtons() {{
          var buttons = document.querySelectorAll(".number-button");
          buttons.forEach(function(btn) {{ btn.disabled = true; }});
        }}

        function enableActionButtons() {{
          var buttons = document.querySelectorAll(".number-button");
          buttons.forEach(function(btn) {{ btn.disabled = false; }});
        }}

        function startLog(endpoint, btn) {{
          if(source !== null) {{ return; }}
          disableActionButtons();
          projectFolders.forEach(function(folder) {{
            let div = document.getElementById("log_" + folder);
            if(div) div.innerHTML = "";
          }});

          source = new EventSource(endpoint);
          source.onmessage = function(e) {{
            try {{
              let data = JSON.parse(e.data);
              let folder = data.folder;
              let line = data.line;
              let logDiv = document.getElementById("log_" + folder);
              if(logDiv) {{
                if(line.includes("Finished")) {{
                  logDiv.innerHTML += "<span style='color: green;'>" + line + "</span><br>";
                }} else {{
                  logDiv.innerHTML += line + "<br>";
                }}
                logDiv.scrollTop = logDiv.scrollHeight;
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
              if(logDiv) {{
                if(data.line.includes("Finished")) {{
                  logDiv.innerHTML += "<span style='color: green;'>" + data.line + "</span><br>";
                }} else {{
                  logDiv.innerHTML += data.line + "<br>";
                }}
                logDiv.scrollTop = logDiv.scrollHeight;
              }}
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
