from flask import Flask, render_template_string, request, url_for, send_file, flash, redirect
import requests
from datetime import datetime, timedelta
import pytz
import json
from pathlib import Path
from dateutil import parser
import os
import logging
import pandas as pd
import re
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from tenacity import retry, stop_after_attempt, wait_random_exponential, retry_if_exception_type

# ——————————————————————————————————
# Config & boilerplate
# ——————————————————————————————————
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "pinterest-analytics-dashboard-secret")

# ——————————————————————————————————
# Define multiple Pinterest/Metricool API sources,
# each with its own token. Accounts will be fetched dynamically.
# ——————————————————————————————————
api_sources = [
    {
        "id": "pinterest1",
        "name": "Pinterest Source 1",
        "color": "#e60023",
        "icon": "pinterest",
        "token": os.environ.get("METRICOOL_TOKEN_1",
                                "MMTOKBYJALBKSANEBQAFSSDLCHRTVBNGVQLEHFWSYKSHAXDNWWWWZIDYGBZFLQJF"),
    },
    {
        "id": "pinterest2",
        "name": "Pinterest Source 2",
        "color": "#c8232c",
        "icon": "pinterest",
        "token": os.environ.get("METRICOOL_TOKEN_2",
                                "QFGWEIWPJFAYNFCRWXZWRZKORZMXOFAXMRYBKJOPZYROJXYLBPBUIMBGSPPSNLTR"),
    },
    # Add more sources here if needed
]

# Custom nice names
CUSTOM_ACCOUNT_NAMES = {
    "Le Nice": "Itsoupy",
    "Recipes With Patricia": "Anitasrezepte",
    "Petit Plate Perfection": "Rezeptejetzt",
    "Family Feast Favorites": "Recipesure",
    "Yummy American Eats": "Weltrezepten",
    "American Bite Bliss": "Cheftaling",
    "Flavors By Patricia": "Pagosarecipes",
    "The Ultimate Recipe Source": "Emmasrezepte",
    "Delicious American Eats": "Chellesrecipes",
    "American Flavor Feast": "Recipeinsight",
    "Granny’s Secret Ingredients": "Echterezepte",
    "Patricia Recipes": "Goodsouppot",
    "Savory Bites & Delights": "Pinrezepte",
    "Sabby and Sofia fans": "Mydishspin",
}

DEFAULT_BLOG_IDS = [
    "4330866",  # cheftaling
    "4334699",  # recipesinsight
    "4332216",  # chellesrecipes
    "4330626",  # recipesure
    "4330874",  # pagossarecipe
    "4330619",  # itsoupy
]

# Metricool endpoints
SIMPLE_PROFILES_URL = "https://app.metricool.com/api/admin/simpleProfiles"
METRICOOL_BASE_URL = "https://app.metricool.com/api/v2/analytics/timelines"
METRICOOL_POSTS_URL = "https://app.metricool.com/api/v2/analytics/posts/pinterest"

# Timezone
TZ = pytz.timezone("Africa/Casablanca")

def _default_range():
    """Return (from_iso, to_iso, from_str, to_str) for the last 30 days."""
    now = datetime.now(TZ)
    from_dt = (now - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
    to_dt = now
    return (
        from_dt.isoformat(timespec="seconds"),
        to_dt.isoformat(timespec="seconds"),
        from_dt.strftime("%Y-%m-%d"),
        to_dt.strftime("%Y-%m-%d"),
    )

def _range_from_request():
    """
    Read ?from=YYYY-MM-DD&to=YYYY-MM-DD; fallback to last 30 days if invalid/missing.
    """
    q_from = request.args.get("from")
    q_to = request.args.get("to")
    try:
        if q_from and q_to:
            from_dt = TZ.localize(datetime.strptime(q_from, "%Y-%m-%d")).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            to_dt = TZ.localize(datetime.strptime(q_to, "%Y-%m-%d")).replace(
                hour=23, minute=59, second=59, microsecond=0
            )
            if from_dt > to_dt:
                raise ValueError
            return (
                from_dt.isoformat(timespec="seconds"),
                to_dt.isoformat(timespec="seconds"),
                q_from,
                q_to,
            )
    except Exception:
        pass
    return _default_range()

# NEW: retries & backoff
@retry(wait=wait_random_exponential(min=1, max=10), stop=stop_after_attempt(5),
       retry=retry_if_exception_type(requests.exceptions.RequestException))
def fetch_accounts(api_source):
    """
    Fetch all Pinterest-capable accounts for this API source via simpleProfiles endpoint.
    Returns a list of dicts: {"user_id": ..., "blog_id": ..., "name": ...}.
    """
    headers = {"X-Mc-Auth": api_source["token"]}
    logging.debug(f"Fetching accounts for source: {api_source['id']}")
    resp = requests.get(SIMPLE_PROFILES_URL, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    accounts = []
    for item in data:
        if item.get("pinterest") is not None:
            raw_name = item["label"] or f"Account {item['id']}"
            friendly = CUSTOM_ACCOUNT_NAMES.get(raw_name, raw_name)
            accounts.append({
                "user_id": item["userId"],
                "blog_id": str(item["id"]),
                "name": friendly,
            })
    return accounts

@retry(wait=wait_random_exponential(min=1, max=10), stop=stop_after_attempt(5),
       retry=retry_if_exception_type(requests.exceptions.RequestException))
def fetch_metric(api_source, user_id, blog_id, metric_name, from_iso, to_iso):
    """
    Fetch a time-series metric (IMPRESSION, OUTBOUND_CLICK, SAVE) for one account.
    Returns a sorted list of (datetime, value) tuples.
    """
    params = {
        "from": from_iso,
        "to": to_iso,
        "metric": metric_name,
        "network": "pinterest",
        "timezone": "Africa/Casablanca",
        "subject": "account",
        "userId": user_id,
        "blogId": blog_id,
    }
    headers = {"X-Mc-Auth": api_source["token"]}
    logging.debug(f"Fetching {metric_name} for blog_id: {blog_id}")
    resp = requests.get(METRICOOL_BASE_URL, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    series = resp.json()["data"][0]["values"]
    parsed = [(parser.isoparse(p["dateTime"]), p.get("value", 0)) for p in series]
    parsed.sort(key=lambda x: x[0])
    return parsed

@retry(wait=wait_random_exponential(min=1, max=10), stop=stop_after_attempt(5),
       retry=retry_if_exception_type(requests.exceptions.RequestException))
def fetch_top_posts(api_source, user_id, blog_id, from_iso, to_iso, limit=10):
    """
    Fetch top Pinterest posts for one account.
    NOW SORTED BY outboundClicks (DESC) as requested.
    """
    params = {
        "from": from_iso,
        "to": to_iso,
        "timezone": "Africa/Casablanca",
        "userId": user_id,
        "blogId": blog_id,
    }
    headers = {"X-Mc-Auth": api_source["token"]}
    logging.debug(f"Fetching top posts for blog_id: {blog_id}")
    resp = requests.get(METRICOOL_POSTS_URL, params=params, headers=headers, timeout=30)
    resp.raise_for_status()
    posts = resp.json().get("data", [])
    # CHANGED: sort by outboundClicks instead of impressions
    top = sorted(posts, key=lambda p: p.get("outboundClicks", 0), reverse=True)[:limit]
    out = []
    for p in top:
        created = parser.isoparse(p.get("createdAt"))
        out.append({
            "imageUrl": p.get("imageUrl"),
            "title": p.get("title", "") or "Untitled",
            "impressions": p.get("impressions", 0),
            "outboundClicks": p.get("outboundClicks", 0),
            "saves": p.get("saves", 0),
            "date_str": created.strftime("%b %d, %Y"),
            "time_str": created.strftime("%I:%M %p"),
        })
    return out

# Parallel fetch of accounts across sources
def _all_accounts_list():
    """
    Return a flat list of all accounts across all sources, with fields:
    {"source_id": ..., "user_id": ..., "blog_id": ..., "name": ...}.
    """
    all_accts = []
    with ThreadPoolExecutor(max_workers=len(api_sources) or 1) as executor:
        future_to_source = {executor.submit(fetch_accounts, src): src for src in api_sources}
        for future in as_completed(future_to_source):
            src = future_to_source[future]
            try:
                accounts = future.result()
                for acct in accounts:
                    acct_copy = acct.copy()
                    acct_copy["source_id"] = src["id"]
                    all_accts.append(acct_copy)
            except Exception as e:
                logging.error(f"Failed to fetch accounts for source {src['id']}: {e}")
    return all_accts

def _default_accounts():
    """Return only accounts contained in DEFAULT_BLOG_IDS."""
    if not DEFAULT_BLOG_IDS:
        return []
    all_accts = _all_accounts_list()
    return [a for a in all_accts if a["blog_id"] in DEFAULT_BLOG_IDS]

def _load_badges() -> dict:
    """Return {blog_id: badge_key}. Empty dict if file missing/bad."""
    try:
        return json.loads(BADGE_FILE.read_text())
    except Exception:
        return {}

def _save_badges(mapping: dict) -> None:
    BADGE_FILE.write_text(json.dumps(mapping, indent=2))

EXPORT_DIR = Path("TOPPOST")
EXPORT_DIR.mkdir(exist_ok=True)

# Badges
BADGES = {
    "not_monetized": {"label": "Not monetized", "bs": "danger", "hex": "#dc3545"},
    "ezoic_approved": {"label": "Ezoic approved", "bs": "success", "hex": "#28a745"},
    "sent_to_ezoic": {"label": "Sent to Ezoic", "bs": "warning", "hex": "#ffc107"},
}
BADGE_FILE = Path("badges.json")

def export_default_top_posts_for_range(from_iso, to_iso, limit=20):
    """
    Writes <EXPORT_DIR>/<sanitised-account-name>.xlsx and returns list of Paths.
    """
    if not DEFAULT_BLOG_IDS:
        logging.warning("DEFAULT_BLOG_IDS is empty – nothing to export.")
        return []
    written_files = []
    default_accounts = _default_accounts()
    if not default_accounts:
        logging.info("No default accounts found – nothing to export.")
        return []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {}
        for acct in default_accounts:
            src = next((s for s in api_sources if s["id"] == acct["source_id"]), None)
            if not src:
                logging.error(f"No api_source found for {acct['name']} ({acct['blog_id']}) – skipping.")
                continue
            futures[executor.submit(
                fetch_top_posts, src,
                acct["user_id"], acct["blog_id"],
                from_iso, to_iso, limit
            )] = acct

        for future in as_completed(futures):
            acct = futures[future]
            try:
                posts = future.result()
                if not posts:
                    logging.info(f"No posts for {acct['name']} in that range.")
                    continue
                df = pd.DataFrame(posts)
                safe_name = re.sub(r"[^A-Za-z0-9_\-]+", "_", acct["name"]) or acct["blog_id"]
                file_path = EXPORT_DIR / f"{safe_name}.xlsx"
                if file_path.exists():
                    file_path.unlink()
                with pd.ExcelWriter(file_path, engine="xlsxwriter", mode="w") as writer:
                    df.to_excel(writer, sheet_name="Top posts", index=False)
                written_files.append(file_path)
                logging.info(f"Wrote {file_path}")
            except Exception as e:
                logging.error(f"Failed to export top posts for {acct['name']}: {e}")
    return written_files

@app.route("/export_default")
def export_default():
    """
    Export one XLSX per default account into TOPPOST/ then redirect back.
    Accepts ?from, ?to, ?limit
    """
    q_from = request.args.get("from")
    q_to = request.args.get("to")
    try:
        if q_from and q_to:
            from_dt = TZ.localize(datetime.strptime(q_from, "%Y-%m-%d")).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            to_dt = TZ.localize(datetime.strptime(q_to, "%Y-%m-%d")).replace(
                hour=23, minute=59, second=59, microsecond=0
            )
            if from_dt > to_dt:
                raise ValueError("from > to")
        else:
            now = datetime.now(TZ)
            from_dt = (now - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
            to_dt = now
    except Exception:
        now = datetime.now(TZ)
        from_dt = (now - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
        to_dt = now

    from_iso = from_dt.isoformat(timespec="seconds")
    to_iso = to_dt.isoformat(timespec="seconds")
    limit = request.args.get("limit", type=int) or 5
    limit = max(1, limit)

    paths = export_default_top_posts_for_range(from_iso, to_iso, limit)

    if not paths:
        flash("No accounts had top-posts for that period – nothing exported.", "danger")
    else:
        flash(f"Exported the top {limit} post(s) for {len(paths)} account(s) → “{EXPORT_DIR.resolve()}”.", "success")

    return redirect(url_for(
        "index",
        **{
            "from": from_dt.strftime("%Y-%m-%d"),
            "to": to_dt.strftime("%Y-%m-%d"),
        }
    ))

@app.route("/set_badge", methods=["POST"])
def set_badge():
    blog_id = request.form.get("blog_id")
    badge_id = request.form.get("badge")
    if blog_id and badge_id in BADGES:
        badges = _load_badges()
        badges[blog_id] = badge_id
        _save_badges(badges)
        flash("Badge updated ✔︎", "success")
    return redirect(request.referrer or url_for("index"))

# ——————————————————————————————————
# Main dashboard endpoint
# ——————————————————————————————————
@app.route("/")
def index():
    from_iso, to_iso, from_str, to_str = _range_from_request()
    selected_blog_ids = request.args.getlist("accounts")
    badges_map = _load_badges()

    # Get all accounts
    all_accounts_raw = _all_accounts_list()
    all_accounts_filtered = [
        acct for acct in all_accounts_raw
        if not selected_blog_ids or acct["blog_id"] in selected_blog_ids
    ]

    account_reports_map = {}
    # Fetch metrics & posts concurrently
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {}
        for acct in all_accounts_filtered:
            src = next((s for s in api_sources if s["id"] == acct["source_id"]), None)
            if not src:
                logging.error(f"No api_source found for {acct['name']} (ID: {acct['blog_id']})")
                continue
            user_id = acct["user_id"]
            blog_id = acct["blog_id"]
            futures[executor.submit(fetch_metric, src, user_id, blog_id, "IMPRESSION", from_iso, to_iso)] = (
                "imps", blog_id, acct, src)
            futures[executor.submit(fetch_metric, src, user_id, blog_id, "OUTBOUND_CLICK", from_iso, to_iso)] = (
                "clicks", blog_id, acct, src)
            futures[executor.submit(fetch_top_posts, src, user_id, blog_id, from_iso, to_iso)] = (
                "posts", blog_id, acct, src)

        for acct in all_accounts_filtered:
            account_reports_map[acct["blog_id"]] = {
                "name": acct["name"],
                "source_id": acct["source_id"],
                "imps_series": [],
                "click_series": [],
                "top_posts": [],
            }

        for future in as_completed(futures):
            task_type, blog_id, acct, src = futures[future]
            try:
                result = future.result()
                if task_type == "imps":
                    account_reports_map[blog_id]["imps_series"] = result
                elif task_type == "clicks":
                    account_reports_map[blog_id]["click_series"] = result
                elif task_type == "posts":
                    account_reports_map[blog_id]["top_posts"] = result
            except Exception as e:
                logging.error(f"Error fetching {task_type} for account {acct['name']} ({blog_id}): {e}")

    all_reports = []
    source_groups = {src["id"]: {"source": src, "accounts": []} for src in api_sources}

    for blog_id, data in account_reports_map.items():
        acct_name = data["name"]
        src_id = data["source_id"]
        imps_series = data["imps_series"]
        click_series = data["click_series"]
        top_posts = data["top_posts"]

        # merge series
        dates, imps_vals, click_vals = [], [], []
        i = j = 0
        while i < len(imps_series) or j < len(click_series):
            if j == len(click_series) or (i < len(imps_series) and imps_series[i][0] < click_series[j][0]):
                dt, v = imps_series[i]
                i += 1
                dates.append(dt.date().isoformat())
                imps_vals.append(v)
                click_vals.append(0)
            elif i == len(imps_series) or (j < len(click_series) and click_series[j][0] < imps_series[i][0]):
                dt, v = click_series[j]
                j += 1
                dates.append(dt.date().isoformat())
                imps_vals.append(0)
                click_vals.append(v)
            else:
                dt = imps_series[i][0]
                v1 = imps_series[i][1]
                v2 = click_series[j][1]
                dates.append(dt.date().isoformat())
                imps_vals.append(v1)
                click_vals.append(v2)
                i += 1
                j += 1

        total_imps = int(sum(imps_vals))
        total_clicks = int(sum(click_vals))
        ctr_percent = (total_clicks / total_imps * 100) if total_imps else 0.0
        half_index = len(imps_vals) // 2 or 1
        trend_imps = (
            "up" if sum(imps_vals[half_index:]) > sum(imps_vals[:half_index])
            else ("down" if sum(imps_vals[half_index:]) < sum(imps_vals[:half_index]) else "neutral")
        )
        trend_clicks = (
            "up" if sum(click_vals[half_index:]) > sum(click_vals[:half_index])
            else ("down" if sum(click_vals[half_index:]) < sum(click_vals[:half_index]) else "neutral")
        )

        account_report = {
            "name": acct_name,
            "dates": dates,
            "imps": imps_vals,
            "clicks": click_vals,
            "total_imps": total_imps,
            "total_clicks": total_clicks,
            "ctr": round(ctr_percent, 2),
            "trend_imps": trend_imps,
            "trend_clicks": trend_clicks,
            "top_posts": top_posts,
            "blog_id": blog_id,
        }
        source_groups[src_id]["accounts"].append(account_report)

    # NEW: sort accounts inside each source by total_clicks desc
    for gid, group in source_groups.items():
        group["accounts"].sort(key=lambda a: a["total_clicks"], reverse=True)

    # keep only sources that have accounts
    for src in api_sources:
        if source_groups[src['id']]["accounts"]:
            all_reports.append(source_groups[src['id']])

    # (optional) could cache, but fine to call again
    all_accounts_for_dropdown = _all_accounts_list()

    template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no" />
      <title>Pinterest Analytics Dashboard</title>
      <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"/>
      <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css" rel="stylesheet"/>
      <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
      <script src="https://cdn.jsdelivr.net/npm/moment@2.29.1/moment.min.js"></script>
      <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-moment"></script>
      <link href="https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css" rel="stylesheet"/>
      <script src="https://cdn.jsdelivr.net/npm/flatpickr"></script>
      <style>
        :root {
          --border-color: rgba(0,0,0,.08);
          --light-gray: #f0f2f5;
          --dark-gray: #333333;
          --medium-gray: #767676;
          --hover-bg: rgba(0,0,0,.02);
          --card-shadow: 0 4px 20px rgba(0,0,0,.08);
          --transition: all 0.3s ease-in-out;
        }
        body { background:#f9fafb; font-family:-apple-system, BlinkMacSystemFont,'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans','Helvetica Neue',sans-serif; color:var(--dark-gray); line-height:1.6; }
        .navbar { background:#fff; box-shadow:0 2px 15px rgba(0,0,0,.05); padding:.8rem 1rem; position:sticky; top:0; z-index:1000; }
        .badge.bg-danger  { background:#e74c3c; }
        .badge.bg-success { background:#27ae60; }
        .badge.bg-warning { background:#f1c40f; color:#000; }
        .navbar-brand { font-weight:700; color:var(--dark-gray); display:flex; align-items:center; font-size:1.25rem; }
        .navbar-brand i { font-size:1.4rem; margin-right:.5rem; color:#e60023; }
        .page-header { padding:2rem 0 1rem; }
        .page-title { font-weight:700; font-size:1.4rem; margin-bottom:.5rem; color:var(--dark-gray); }
        .page-subtitle { color:var(--medium-gray); font-size:.9rem; }
        .date-range-form { display:flex; align-items:center; background:#fff; border-radius:10px; padding:.35rem .75rem; box-shadow:0 2px 8px rgba(0,0,0,.04); border:1px solid var(--border-color); transition:var(--transition); }
        .date-range-form:hover { box-shadow:0 4px 12px rgba(0,0,0,.08); }
        .date-input { background:transparent; border:none; color:var(--dark-gray); font-size:.9rem; cursor:pointer; padding:.4rem .6rem; width:120px; transition:var(--transition); }
        .date-input:focus, .date-input:hover { outline:none; background:var(--light-gray); border-radius:6px; }
        .date-separator { margin:0 .5rem; color:var(--medium-gray); }
        .apply-btn { background-color:#e60023; border:none; color:white; padding:.4rem 1rem; border-radius:8px; font-size:.85rem; font-weight:600; cursor:pointer; transition:var(--transition); box-shadow:0 2px 5px rgba(0,0,0,.1); }
        .apply-btn:hover { opacity:.9; transform:translateY(-1px); box-shadow:0 4px 8px rgba(0,0,0,.15); }
        .project-select { padding:.4rem .8rem; border-radius:8px; background-color:var(--light-gray); border:1px solid var(--border-color); color:var(--dark-gray); font-size:.85rem; }
        .account-card { background:#fff; border:0; border-radius:16px; box-shadow:var(--card-shadow); overflow:hidden; margin-bottom:2rem; transition:var(--transition); }
        .account-card:hover { box-shadow:0 0 0 3px rgba(0,0,0,.12); transform:translateY(-2px); }
        .account-header { padding:1.25rem 1.5rem; border-bottom:1px solid var(--border-color); display:flex; align-items:center; justify-content:space-between; background:#fff; }
        .account-name { font-weight:700; font-size:1.15rem; margin:0; color:var(--dark-gray); display:flex; align-items:center; }
        .account-name i { margin-right:.5rem; font-size:1rem; color:var(--primary-color); }
        .account-body { padding:1.5rem; }
        .stat-box { flex:1; min-width:120px; background:#fff; border:1px solid var(--border-color); border-radius:12px; padding:1.25rem; text-align:center; transition:var(--transition); }
        .stat-box:hover { transform:translateY(-3px); box-shadow:0 6px 15px rgba(0,0,0,.08); }
        .stat-title { font-size:.9rem; color:var(--medium-gray); margin-bottom:.5rem; }
        .stat-value { font-size:1.8rem; font-weight:700; margin-bottom:.3rem; }
        .impressions-value { color:#0076d3; }
        .clicks-value { color:#118060; }
        .ctr-value { color:var(--primary-color); }
        .trend-indicator { display:flex; align-items:center; justify-content:center; font-size:.85rem; font-weight:600; }
        .trend-indicator i { margin-right:.3rem; }
        .trend-up { color:#118060; }
        .trend-down { color:var(--primary-color); }
        .trend-neutral { color:var(--medium-gray); }
        .chart-container { height:300px; margin:1.5rem 0; padding:1rem; background:#fff; border-radius:12px; border:1px solid var(--border-color); }
        .circle-toggle { inline-size:64px; block-size:64px; border-radius:50%; --btn-bg:var(--primary-color,#e60023); --btn-bg-hi:#ff4568; --btn-ring: color-mix(in srgb, var(--btn-bg) 60%, #ffffff); background: radial-gradient(circle at 30% 30%, var(--btn-bg-hi), var(--btn-bg)); border:4px solid var(--btn-ring); color:#fff; font-size:1.4rem; display:grid; place-content:center; box-shadow:0 4px 10px rgba(0,0,0,.15); transition:transform .25s, box-shadow .25s; cursor:pointer; user-select:none; }
        .circle-toggle:hover { transform:translateY(-3px); }
        .circle-toggle:active { transform:translateY(0); box-shadow:0 2px 6px rgba(0,0,0,.2); }
        .circle-toggle.collapsed i { transition: transform .25s; }
        .circle-toggle:not(.collapsed) i { transform: rotate(180deg); }
        .posts-grid { display:flex; flex-wrap:wrap; gap:1rem; }
        .post-card { background:#fff; border:1px solid var(--border-color); border-radius:12px; box-shadow:0 2px 8px rgba(0,0,0,.04); overflow:hidden; transition:var(--transition); display:flex; align-items:center; width:100%; }
        .post-card:hover { box-shadow:0 6px 15px rgba(0,0,0,.08); transform:translateY(-2px); }
        .post-img { flex:0 0 80px; height:80px; object-fit:cover; }
        .post-details { flex:1; padding:.75rem 1rem; display:flex; flex-direction:column; justify-content:space-between; }
        .post-title { font-size:1rem; font-weight:600; color:var(--dark-gray); margin-bottom:.25rem; }
        .post-date { font-size:.8rem; color:var(--medium-gray); }
        .post-metrics { display:flex; justify-content:flex-start; gap:1.5rem; margin-top:.5rem; }
        .post-metrics .metric { display:flex; align-items:center; font-size:.85rem; color:var(--medium-gray); }
        .post-metrics .metric i { margin-right:.3rem; }
        .metric-impressions i { color:#0076d3; }
        .metric-clicks i { color:#118060; }
        .metric-saves i { color:var(--primary-color); }
        @media (max-width: 768px) {
          .stats-row { flex-direction:column; }
          .stat-box { margin-bottom:1rem; width:100%; }
          .date-range-form { flex-wrap:wrap; }
          .post-card { flex-direction:column; align-items:flex-start; }
          .post-img { width:100%; height:160px; }
          .post-details { padding:.75rem; }
        }
        .account-card.approved { background:#e9f7ef; border:2px solid #28a745; box-shadow:0 0 0 2px #28a745 !important; }
        .account-card.approved:hover { box-shadow:0 0 0 3px #28a745 !important; }
        .account-card.approved .account-header { background:#28a745; color:#fff; }
        .account-card.approved .account-name, .account-card.approved .account-name i { color:#fff; }
        .account-card.approved .stat-title, .account-card.approved .post-date, .account-card.approved .post-metrics .metric { color:#0b3d1f; }
        .account-card.approved .impressions-value, .account-card.approved .clicks-value, .account-card.approved .ctr-value { color:#0b3d1f; }
        .account-card.sent { background:#fff8e1; border:2px solid #ffc107; box-shadow:0 0 0 2px #ffc107 !important; }
        .account-card.sent:hover { box-shadow:0 0 0 3px #ffc107 !important; }
        .account-card.sent .account-header { background:#ffc107; color:#000; }
        .account-card.sent .account-name, .account-card.sent .account-name i { color:#000; }
        .account-card.sent .stat-title, .account-card.sent .post-date, .account-card.sent .post-metrics .metric { color:#6b5b00; }
        .account-card.sent .impressions-value, .account-card.sent .clicks-value, .account-card.sent .ctr-value { color:#6b5b00; }
      </style>
    </head>
    <body>
      <nav class="navbar">
        <div class="container">
          <a class="navbar-brand" href="/">
            <i class="fab fa-pinterest"></i>
            Pinterest Analytics Dashboard
          </a>
        </div>
      </nav>

      <div class="container">
        <div class="page-header">
          <h1 class="page-title">Pinterest Analytics Dashboard</h1>
          <p class="page-subtitle">View and analyze performance metrics across multiple Pinterest sources.</p>
        </div>

        {% with msgs = get_flashed_messages(with_categories=true) %}
          {% if msgs %}
            {% for cat, msg in msgs %}
              <div class="alert alert-{{ 'success' if cat == 'success' else 'danger' }} text-center" role="alert">
                {{ msg }}
              </div>
            {% endfor %}
          {% endif %}
        {% endwith %}

        <div class="d-flex align-items-center flex-wrap mb-4">
          <form action="/" method="get" class="date-range-form">
            <div class="date-range-picker">
              <input type="text" name="from" id="from-date" class="date-input" value="{{ from_str }}" placeholder="From Date"/>
            </div>
            <span class="date-separator">to</span>
            <div class="date-range-picker">
              <input type="text" name="to" id="to-date" class="date-input" value="{{ to_str }}" placeholder="To Date"/>
            </div>

            <button type="submit" class="apply-btn">Apply</button>

            <input type="number" name="limit" value="5" min="1" class="form-control form-control-sm ms-2" style="width:70px;" title="Number of top posts to export">

            <button type="submit" class="btn btn-outline-secondary ms-2" formaction="{{ url_for('export_default') }}" formmethod="get">
              <i class="fas fa-download me-1"></i> Export Top Posts
            </button>
          </form>
        </div>

        {% for src_group in all_reports %}
          <h2 class="mb-3" style="color: {{ src_group.source.color }};">
            <i class="fab fa-{{ src_group.source.icon }}"></i>
            {{ src_group.source.name }}
          </h2>

          <div class="row">
            {% for account in src_group.accounts %}
              <div class="col-lg-6">
                {% set b       = badges_map.get(account.blog_id) %}
                {% set shadowc = BADGES[b].hex if b else 'rgba(0,0,0,.12)' %}
                {% set is_approved = (b == 'ezoic_approved') %}
                {% set is_sent = (b == 'sent_to_ezoic') %}

                <div class="account-card {% if is_approved %}approved{% endif %} {% if is_sent %}sent{% endif %}"
                     style="--primary-color: {{ src_group.source.color }}; --card-shadow:0 0 0 2px {{ shadowc }}; --card-shadow-hover:0 0 0 3px {{ shadowc }};">
                  <div class="account-header">
                    <h2 class="account-name">
                      <i class="fab fa-pinterest"></i> {{ account.name }}
                    </h2>
                    {% set b = badges_map.get(account.blog_id) %}
                    {% if b %}
                      <span class="badge bg-{{ BADGES[b].bs }} ms-2">{{ BADGES[b].label }}</span>
                    {% endif %}
                    <form action="{{ url_for('set_badge') }}" method="post" class="ms-auto">
                      <input type="hidden" name="blog_id" value="{{ account.blog_id }}">
                      <select name="badge" class="form-select form-select-sm" onchange="this.form.submit()">
                        <option value="">– select status –</option>
                        {% for key, meta in BADGES.items() %}
                          <option value="{{ key }}" {% if b == key %}selected{% endif %}>{{ meta.label }}</option>
                        {% endfor %}
                      </select>
                    </form>
                  </div>

                  <div class="account-body">
                    <div class="d-flex gap-3 stats-row">
                      <div class="stat-box">
                        <div class="stat-title">Impressions</div>
                        <div class="stat-value impressions-value">{{ "{:,}".format(account.total_imps) }}</div>
                        <div class="trend-indicator trend-{{ account.trend_imps }}">
                          {% if account.trend_imps == "up" %}
                            <i class="fas fa-arrow-up"></i> Increasing
                          {% elif account.trend_imps == "down" %}
                            <i class="fas fa-arrow-down"></i> Decreasing
                          {% else %}
                            <i class="fas fa-minus"></i> Stable
                          {% endif %}
                        </div>
                      </div>
                      <div class="stat-box">
                        <div class="stat-title">Clicks</div>
                        <div class="stat-value clicks-value">{{ "{:,}".format(account.total_clicks) }}</div>
                        <div class="trend-indicator trend-{{ account.trend_clicks }}">
                          {% if account.trend_clicks == "up" %}
                            <i class="fas fa-arrow-up"></i> Increasing
                          {% elif account.trend_clicks == "down" %}
                            <i class="fas fa-arrow-down"></i> Decreasing
                          {% else %}
                            <i class="fas fa-minus"></i> Stable
                          {% endif %}
                        </div>
                      </div>
                      <div class="stat-box">
                        <div class="stat-title">CTR (%)</div>
                        <div class="stat-value ctr-value">{{ "%.2f"|format(account.ctr) }}%</div>
                      </div>
                    </div>

                    <div class="chart-container">
                      <canvas id="chart-{{ src_group.source.id }}-{{ loop.index }}"></canvas>
                    </div>

                    <button class="circle-toggle collapsed" type="button"
                            data-bs-toggle="collapse"
                            data-bs-target="#posts-{{ src_group.source.id }}-{{ loop.index }}"
                            aria-expanded="false"
                            aria-controls="posts-{{ src_group.source.id }}-{{ loop.index }}">
                      <i class="fas fa-chevron-down"></i>
                    </button>

                    <div class="collapse" id="posts-{{ src_group.source.id }}-{{ loop.index }}">
                      <h3 class="mt-4 mb-3" style="font-size:1.1rem;font-weight:600;color:var(--dark-gray);">
                        <i class="fas fa-trophy me-2" style="color:var(--primary-color);"></i>
                        Top Performing Posts
                      </h3>

                      <div class="posts-grid">
                        {% for post in account.top_posts %}
                          <div class="post-card col-12">
                            <img src="{{ post.imageUrl }}" class="post-img" alt="Thumbnail" />
                            <div class="post-details">
                              <div>
                                <div class="post-title">{{ post.title }}</div>
                                <div class="post-date">{{ post.date_str }} • {{ post.time_str }}</div>
                              </div>
                              <div class="post-metrics">
                                <div class="metric metric-impressions">
                                  <i class="fas fa-eye"></i> {{ "{:,}".format(post.impressions) }}
                                </div>
                                <div class="metric metric-clicks">
                                  <i class="fas fa-arrow-up"></i> {{ "{:,}".format(post.outboundClicks) }}
                                </div>
                                <div class="metric metric-saves">
                                  <i class="fas fa-bookmark"></i> {{ "{:,}".format(post.saves) }}
                                </div>
                              </div>
                            </div>
                          </div>
                        {% endfor %}
                      </div>
                    </div>

                  </div>
                </div>
              </div>
            {% endfor %}
          </div>
        {% endfor %}
      </div>

      <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>

      <script>
        flatpickr("#from-date", { dateFormat: "Y-m-d", maxDate: "today" });
        flatpickr("#to-date",   { dateFormat: "Y-m-d", maxDate: "today" });

        document.addEventListener("DOMContentLoaded", function () {
          {% for src_group in all_reports %}
            {% for account in src_group.accounts %}
              if (document.getElementById("chart-{{ src_group.source.id }}-{{ loop.index }}")) {
                const ctx = document.getElementById("chart-{{ src_group.source.id }}-{{ loop.index }}").getContext("2d");
                new Chart(ctx, {
                  type: "line",
                  data: {
                    labels: {{ account.dates | tojson }},
                    datasets: [
                      {
                        label: "Impressions",
                        data: {{ account.imps | tojson }},
                        borderColor: "{{ src_group.source.color }}",
                        backgroundColor: "rgba(230,0,35,0.1)",
                        fill: true,
                        tension: 0.3,
                        pointRadius: 2,
                        yAxisID: "y",
                      },
                      {
                        label: "Outbound Clicks",
                        data: {{ account.clicks | tojson }},
                        borderColor: "#118060",
                        borderWidth: 1,
                        fill: false,
                        tension: 0.3,
                        pointRadius: 2,
                        yAxisID: "y1",
                      },
                    ],
                  },
                  options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                      x: { type: "time", time: { unit: "day" }, title: { display: true, text: "Date" } },
                      y: { type: "linear", beginAtZero: true, title: { display: true, text: "Impressions" }, ticks: { callback: v => v.toLocaleString() } },
                      y1:{ type: "linear", beginAtZero: true, position: "right", title: { display: true, text: "Outbound Clicks" }, grid: { drawOnChartArea: false }, ticks: { callback: v => v.toLocaleString() } },
                    },
                    plugins: { legend: { position: "top" }, tooltip: { mode: "index", intersect: false } },
                  },
                });
              }
            {% endfor %}
          {% endfor %}
        });
      </script>
    </body>
    </html>
    """
    return render_template_string(
        template,
        from_str=from_str,
        to_str=to_str,
        all_reports=all_reports,
        all_accounts=all_accounts_for_dropdown,
        request=request,
        badges_map=badges_map,
        BADGES=BADGES,
        url_for=url_for
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
