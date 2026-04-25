"""
Load secrets: repo config/shared_keys.json merged with <project>/config/keys.json,
non-secret settings (config/settings.json), and optional prompt JSON under config/prompts/.

Precedence: environment variables override merged keys. Project keys override shared.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

A1_DIR = Path(__file__).resolve().parent
CONFIG_DIR = A1_DIR / "config"
PROMPTS_DIR = CONFIG_DIR / "prompts"
REPO_ROOT = A1_DIR.parent
# One file for the whole repo: OpenAI, UseAPI, R2. Per-project config/keys.json merges on top (WordPress, overrides).
REPO_CONFIG_DIR = REPO_ROOT / "config"
SHARED_KEYS_PATH = REPO_CONFIG_DIR / "shared_keys.json"
SITES_PATH = REPO_CONFIG_DIR / "sites.json"


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def load_settings() -> Dict[str, Any]:
    """Non-secret defaults (language, word counts, paths relative names, etc.)."""
    return _read_json(CONFIG_DIR / "settings.json")


def load_keys() -> Dict[str, Any]:
    """
    Merges repo-wide shared keys (config/shared_keys.json) with this project's config/keys.json.
    Project values override shared (e.g. put only WordPress in the project file; openai/r2 in shared).
    Tries project keys.json, then keys.example.json if missing.
    """
    shared = _read_json(SHARED_KEYS_PATH)
    keys_path = CONFIG_DIR / "keys.json"
    ex_path = CONFIG_DIR / "keys.example.json"
    if keys_path.is_file():
        local = _read_json(keys_path)
    else:
        local = _read_json(ex_path)
    data: Dict[str, Any] = {**shared, **local}

    # Blanks in project keys.json must not erase shared_keys.json (only non-empty local overrides)
    for k in (
        "openai_api_key",
        "openai_model",
        "useapi_token",
        "useapi_midjourney_channel",
        "r2_account_id",
        "r2_access_key_id",
        "r2_secret_access_key",
        "r2_bucket",
        "r2_public_base_url",
    ):
        v = data.get(k)
        if isinstance(v, str) and not v.strip() and shared.get(k) and str(shared.get(k, "")).strip():
            data[k] = shared[k]

    # WordPress (and any site fields) from config/sites.json for PINTEREST_SITE_ID
    site = get_active_site()
    for k in ("wordpress_url", "wordpress_user", "wordpress_app_password"):
        v = site.get(k) if isinstance(site, dict) else None
        if v is not None and str(v).strip() != "":
            data[k] = v

    # --- env overrides (standard names) ---
    if os.environ.get("OPENAI_API_KEY"):
        data["openai_api_key"] = os.environ["OPENAI_API_KEY"]
    if os.environ.get("OPENAI_MODEL"):
        data["openai_model"] = os.environ["OPENAI_MODEL"]

    if os.environ.get("USEAPI_NET_API_TOKEN") or os.environ.get("USEAPI_TOKEN"):
        data["useapi_token"] = os.environ.get("USEAPI_NET_API_TOKEN") or os.environ.get("USEAPI_TOKEN", "")
    if os.environ.get("USEAPI_MJ_CHANNEL") or os.environ.get("USEAPI_MIDJOURNEY_CHANNEL"):
        v = os.environ.get("USEAPI_MJ_CHANNEL") or os.environ.get("USEAPI_MIDJOURNEY_CHANNEL", "")
        if v:
            data["useapi_midjourney_channel"] = v

    for a, b in [
        ("CLOUDFLARE_ACCOUNT_ID", "r2_account_id"),
        ("R2_ACCESS_KEY_ID", "r2_access_key_id"),
        ("R2_SECRET_ACCESS_KEY", "r2_secret_access_key"),
        ("R2_BUCKET", "r2_bucket"),
        ("R2_PUBLIC_BASE_URL", "r2_public_base_url"),
    ]:
        if os.environ.get(a):
            data[b] = os.environ[a]

    if os.environ.get("WP_URL"):
        data["wordpress_url"] = os.environ["WP_URL"]
    if os.environ.get("WP_USER"):
        data["wordpress_user"] = os.environ["WP_USER"]
    if os.environ.get("WP_APP_PASSWORD"):
        data["wordpress_app_password"] = os.environ["WP_APP_PASSWORD"]

    return data


def load_prompts(name: str) -> Dict[str, Any]:
    """Load config/prompts/{name}.json (no extension in name)."""
    return _read_json(PROMPTS_DIR / f"{name}.json")


def read_excel_with_retry(
    path: str, *, sheet_name=0, retries: int = 10, delay: float = 0.4
):
    """
    Read an .xlsx while another process (or Excel) may briefly lock the file.
    Close the workbook in Excel if errors persist.
    """
    import time
    import pandas as pd

    last: Optional[Exception] = None
    for i in range(retries):
        try:
            return pd.read_excel(path, sheet_name=sheet_name)
        except PermissionError as e:
            last = e
            time.sleep(delay * (1 + i))
    assert last is not None
    raise last


def to_excel_with_retry(
    df, path: str, *, index: bool = False, retries: int = 10, delay: float = 0.4
) -> None:
    import time

    last: Optional[Exception] = None
    for i in range(retries):
        try:
            df.to_excel(path, index=index)
            return
        except PermissionError as e:
            last = e
            time.sleep(delay * (1 + i))
    assert last is not None
    raise last


def get_openai_model(settings: Optional[Dict[str, Any]] = None, keys: Optional[Dict[str, Any]] = None) -> str:
    s = settings if settings is not None else load_settings()
    k = keys if keys is not None else load_keys()
    return (k.get("openai_model") or s.get("openai_model") or "gpt-4o-mini").strip()


def set_openai_key_from_keys(keys: Optional[Dict[str, Any]] = None) -> str:
    import openai

    k = keys if keys is not None else load_keys()
    key = (k.get("openai_api_key") or os.environ.get("OPENAI_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("Missing openai_api_key: set in config/keys.json or environment OPENAI_API_KEY.")
    openai.api_key = key
    return key


def load_sites() -> Dict[str, Any]:
    return _read_json(SITES_PATH)


def active_site_id() -> str:
    return (os.environ.get("PINTEREST_SITE_ID") or "").strip()


def get_active_site() -> Dict[str, Any]:
    """
    Resolves the site row for the current run (PINTEREST_SITE_ID) or a single default.
    When no sites.json: default output dir matches legacy A1 layout.
    """
    raw = load_sites()
    sites = raw.get("sites")
    sid = active_site_id()
    default_out = "A1-Pinterest_01-out"
    if isinstance(sites, list) and len(sites) > 0:
        for s in sites:
            if not isinstance(s, dict):
                continue
            if sid and str(s.get("id", "")).strip() == sid:
                d = dict(s)
                d.setdefault("out_dir", (d.get("out_dir") or f"{d.get('id', 'out')}-out").strip())
                return d
        s0 = dict(sites[0])
        s0.setdefault("out_dir", (s0.get("out_dir") or f"{s0.get('id', 'out')}-out").strip())
        if not sid:
            return s0
    if sid:
        out = (os.environ.get("PINTEREST_OUT_DIR") or f"{sid}-out").strip()
        return {"id": sid, "out_dir": out}
    return {"id": "default", "out_dir": default_out}


def all_output_dir() -> str:
    s = get_active_site()
    sub = (s.get("out_dir") or f"{s.get('id', 'out')}-out").strip()
    return str((REPO_ROOT / "ALL" / sub).resolve())


def all_output_join(*parts: str) -> str:
    base = Path(all_output_dir())
    p = base
    for a in parts:
        p = p / a
    return str(p.resolve())


def resolve_start_titles_excel() -> str:
    """
    Titles for A.1-START: STARTS/{start_file} if set, else STARTS/{site_id}.xlsx, else STARTS/START1.xlsx
    """
    site = get_active_site()
    d = REPO_ROOT / "STARTS"
    sid = str(site.get("id", "default"))
    if site.get("start_file"):
        c = d / str(site["start_file"])
        if c.is_file():
            return str(c)
    for name in (f"{sid}.xlsx", "START1.xlsx"):
        c = d / name
        if c.is_file():
            return str(c)
    return str(d / f"{sid}.xlsx")
