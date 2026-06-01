"""
Cloudflare R2 provisioning for the Pinterest pipeline.

Architecture:
  - One shared *disposable* bucket (temporary images: grids, extra splits, Pinterest pins).
    Lifecycle auto-deletes all objects after N days (default 7).
  - One *permanent* bucket per site (image_1 + image_ing_1 for WordPress / live site).
    Created automatically; public r2.dev URL stored on the site row in sites.json.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_DISPOSABLE_BUCKET = "pinterest-disposable"
DEFAULT_SITE_BUCKET_PREFIX = "pinterest-site-"
DEFAULT_AUTO_DELETE_DAYS = 7


def cf_credentials_from_shared(shared: Dict[str, Any]) -> Dict[str, str]:
    account_id = str(
        shared.get("cloudflare_account_id") or shared.get("r2_account_id") or ""
    ).strip()
    token = str(shared.get("cloudflare_api_token") or "").strip()
    return {"account_id": account_id, "token": token}


def sanitize_bucket_name(name: str) -> str:
    s = re.sub(r"[^a-z0-9-]", "-", str(name or "").lower())
    s = re.sub(r"-+", "-", s).strip("-")
    if len(s) < 3:
        s = f"bucket-{s or 'x'}"
    return s[:63]


def site_permanent_bucket_name(site_id: str, prefix: Optional[str] = None) -> str:
    p = str(prefix or DEFAULT_SITE_BUCKET_PREFIX).strip() or DEFAULT_SITE_BUCKET_PREFIX
    return sanitize_bucket_name(f"{p}{site_id}")


def disposable_bucket_name(shared: Dict[str, Any]) -> str:
    raw = str(shared.get("r2_disposable_bucket") or "").strip()
    return sanitize_bucket_name(raw or DEFAULT_DISPOSABLE_BUCKET)


def auto_delete_days(shared: Dict[str, Any]) -> int:
    try:
        return max(1, int(shared.get("r2_disposable_auto_delete_days") or DEFAULT_AUTO_DELETE_DAYS))
    except (TypeError, ValueError):
        return DEFAULT_AUTO_DELETE_DAYS


def _cf_api(
    method: str,
    account_id: str,
    token: str,
    path: str,
    body: Optional[dict] = None,
) -> Tuple[bool, dict, str]:
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}{path}"
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            doc = json.loads(raw) if raw else {}
            if isinstance(doc, dict) and doc.get("success"):
                return True, doc, ""
            err = ""
            if isinstance(doc, dict):
                errs = doc.get("errors") or []
                if errs and isinstance(errs[0], dict):
                    err = str(errs[0].get("message") or errs[0])
            return False, doc if isinstance(doc, dict) else {}, err or "Cloudflare API error"
    except urllib.error.HTTPError as e:
        try:
            doc = json.loads(e.read().decode("utf-8", errors="replace"))
        except Exception:
            doc = {}
        err = ""
        if isinstance(doc, dict):
            errs = doc.get("errors") or []
            if errs and isinstance(errs[0], dict):
                err = str(errs[0].get("message") or errs[0])
        if e.code == 409 and "already exists" in err.lower():
            return True, doc, ""
        return False, doc if isinstance(doc, dict) else {}, err or f"HTTP {e.code}"
    except Exception as e:
        return False, {}, str(e)


def bucket_exists(account_id: str, token: str, bucket_name: str) -> bool:
    ok, _, _ = _cf_api("GET", account_id, token, f"/r2/buckets/{bucket_name}")
    return ok


def create_bucket(account_id: str, token: str, bucket_name: str) -> Tuple[bool, str]:
    ok, _, err = _cf_api(
        "POST",
        account_id,
        token,
        "/r2/buckets",
        {"name": bucket_name, "storageClass": "Standard"},
    )
    return ok, err


def enable_managed_public_domain(
    account_id: str, token: str, bucket_name: str
) -> Tuple[bool, str, str]:
    """Enable r2.dev public access; returns (ok, public_base_url, error)."""
    ok, _, err = _cf_api(
        "PUT",
        account_id,
        token,
        f"/r2/buckets/{bucket_name}/domains/managed",
        {"enabled": True},
    )
    if not ok:
        return False, "", err
    ok2, doc, err2 = _cf_api(
        "GET", account_id, token, f"/r2/buckets/{bucket_name}/domains/managed"
    )
    if not ok2:
        return False, "", err2
    result = doc.get("result") if isinstance(doc, dict) else {}
    domain = ""
    if isinstance(result, dict):
        domain = str(result.get("domain") or "").strip()
    if not domain:
        return False, "", "Could not read r2.dev domain after enable"
    public = f"https://{domain.rstrip('/')}"
    return True, public, ""


def set_auto_delete_lifecycle(
    account_id: str, token: str, bucket_name: str, days: int
) -> Tuple[bool, str]:
    max_age = int(days) * 86400
    body = {
        "rules": [
            {
                "id": f"auto-delete-after-{days}-days",
                "enabled": True,
                "conditions": {"prefix": ""},
                "deleteObjectsTransition": {
                    "condition": {"type": "Age", "maxAge": max_age},
                },
            }
        ]
    }
    ok, _, err = _cf_api(
        "PUT",
        account_id,
        token,
        f"/r2/buckets/{bucket_name}/lifecycle",
        body,
    )
    return ok, err


def ensure_bucket_with_public_url(
    creds: Dict[str, str],
    bucket_name: str,
    *,
    lifecycle_days: Optional[int] = None,
) -> Dict[str, Any]:
    """Create bucket if missing, enable r2.dev, optional lifecycle. Returns result dict."""
    account_id = creds.get("account_id") or ""
    token = creds.get("token") or ""
    out: Dict[str, Any] = {
        "bucket": bucket_name,
        "created": False,
        "public_base_url": "",
        "lifecycle_days": lifecycle_days,
        "errors": [],
    }
    if not account_id or not token:
        out["errors"].append("Missing cloudflare_account_id or cloudflare_api_token")
        return out

    if not bucket_exists(account_id, token, bucket_name):
        ok, err = create_bucket(account_id, token, bucket_name)
        if not ok:
            out["errors"].append(f"create bucket: {err}")
            return out
        out["created"] = True

    ok_pub, public, err_pub = enable_managed_public_domain(account_id, token, bucket_name)
    if ok_pub:
        out["public_base_url"] = public
    else:
        out["errors"].append(f"public domain: {err_pub}")

    if lifecycle_days is not None:
        ok_lc, err_lc = set_auto_delete_lifecycle(
            account_id, token, bucket_name, lifecycle_days
        )
        if not ok_lc:
            out["errors"].append(f"lifecycle: {err_lc}")

    out["ok"] = not out["errors"] or bool(out["public_base_url"])
    return out


def ensure_disposable_bucket(shared: Dict[str, Any]) -> Dict[str, Any]:
    creds = cf_credentials_from_shared(shared)
    name = disposable_bucket_name(shared)
    days = auto_delete_days(shared)
    result = ensure_bucket_with_public_url(creds, name, lifecycle_days=days)
    result["role"] = "disposable"
    return result


def ensure_site_permanent_bucket(
    shared: Dict[str, Any], site_id: str
) -> Dict[str, Any]:
    creds = cf_credentials_from_shared(shared)
    prefix = str(shared.get("r2_site_bucket_prefix") or DEFAULT_SITE_BUCKET_PREFIX).strip()
    name = site_permanent_bucket_name(site_id, prefix)
    result = ensure_bucket_with_public_url(creds, name, lifecycle_days=None)
    result["role"] = "permanent"
    result["site_id"] = site_id
    return result


def provision_all_sites(
    sites: List[dict], shared: Dict[str, Any], *, force_public: bool = False
) -> Dict[str, Any]:
    """
    Ensure disposable bucket + each site's permanent bucket.
    Returns { disposable, sites: [{site_id, bucket, public_base_url, ...}], shared_updates }.
    """
    auto = shared.get("r2_auto_provision_buckets")
    if auto is False:
        return {"ok": False, "skipped": True, "reason": "r2_auto_provision_buckets is false"}

    out: Dict[str, Any] = {
        "ok": True,
        "disposable": ensure_disposable_bucket(shared),
        "sites": [],
        "shared_updates": {},
    }

    disp = out["disposable"]
    if disp.get("public_base_url"):
        out["shared_updates"]["r2_disposable_public_base_url"] = disp["public_base_url"]
    if disp.get("bucket"):
        out["shared_updates"]["r2_disposable_bucket"] = disp["bucket"]

    prefix = str(shared.get("r2_site_bucket_prefix") or DEFAULT_SITE_BUCKET_PREFIX).strip()
    for s in sites:
        if not isinstance(s, dict):
            continue
        sid = str(s.get("id") or "").strip()
        if not sid:
            continue
        existing_bucket = str(s.get("r2_bucket") or "").strip()
        existing_url = str(s.get("r2_public_base_url") or "").strip()
        if existing_bucket and existing_url and not force_public:
            # Verify bucket exists; refresh public URL if needed
            creds = cf_credentials_from_shared(shared)
            if creds.get("account_id") and creds.get("token"):
                if bucket_exists(creds["account_id"], creds["token"], existing_bucket):
                    out["sites"].append(
                        {
                            "site_id": sid,
                            "bucket": existing_bucket,
                            "public_base_url": existing_url,
                            "skipped": True,
                        }
                    )
                    continue
        row = ensure_site_permanent_bucket(shared, sid)
        row["site_updates"] = {}
        if row.get("bucket"):
            row["site_updates"]["r2_bucket"] = row["bucket"]
        if row.get("public_base_url"):
            row["site_updates"]["r2_public_base_url"] = row["public_base_url"]
        out["sites"].append(row)
        if row.get("errors"):
            out["ok"] = False

    if out["disposable"].get("errors"):
        out["ok"] = False
    return out
