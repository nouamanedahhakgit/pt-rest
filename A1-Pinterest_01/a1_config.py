"""
Load secrets (config/keys.json) and non-secret settings (config/settings.json)
and optional prompt JSON files under config/prompts/.

Precedence: environment variables override keys.json values.
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
    Secrets and optional per-machine overrides.
    Tries config/keys.json, then config/keys.example.json (placeholders only).
    """
    keys_path = CONFIG_DIR / "keys.json"
    ex_path = CONFIG_DIR / "keys.example.json"
    if keys_path.is_file():
        data = _read_json(keys_path)
    else:
        data = _read_json(ex_path)

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
