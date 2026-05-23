"""
A.9-CF UPLOAD.py

Render the project's selected static-site theme into a build folder and deploy it
to Cloudflare Pages. Each run = a new Pages deployment (= a new "version" that
can be promoted from the dashboard via the Versions panel in app.py).

Deploy mechanism: wrangler CLI (`npx wrangler pages deploy <build_dir>
--project-name=<name>`). Wrangler is installed on demand via npx if not present.

Inputs (resolved through a1_config + sites.json + shared_keys.json):
    - theme_slug                       : sites.json row → required, else ABORT
    - cloudflare_project_name          : sites.json row → required
    - cloudflare_api_token             : sites.json row (override) → shared_keys.json (fallback) → ABORT
    - cloudflare_account_id            : sites.json row (override) → shared_keys.json (fallback) → ABORT

Data exposed to Jinja templates (per theme):
    site = { title, description, year, built_at, version }
    articles[] = { slug, title, excerpt, featured_image, pinterest_image,
                   category, url, html_body, meta_description }
    article = one entry in articles (for article.html)
    categories[] = distinct, ordered list of category names
"""
from __future__ import annotations

import base64
import datetime as _dt
import html
import json
import logging
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

# --- repo root + a1_config ---
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import a1_config  # noqa: E402
import pandas as pd  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
log = logging.getLogger("cf-upload")

THEMES_DIR = os.path.join(_REPO_ROOT, "themes")
BUILD_ROOT = os.path.join(_REPO_ROOT, "ALL", "_cf_builds")


# -------------------- config helpers --------------------
def _load_json_file(path: str) -> dict:
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _shared_keys() -> dict:
    return _load_json_file(os.path.join(_REPO_ROOT, "config", "shared_keys.json"))


def _sites_doc() -> dict:
    return _load_json_file(os.path.join(_REPO_ROOT, "config", "sites.json"))


def _resolve_site_row() -> Optional[dict]:
    """Find the sites.json row matching PINTEREST_SITE_ID (set by app.py per-project run)."""
    sid = (os.environ.get("PINTEREST_SITE_ID") or "").strip()
    doc = _sites_doc()
    sites = doc.get("sites") if isinstance(doc, dict) else None
    if not isinstance(sites, list):
        return None
    if sid:
        for s in sites:
            if isinstance(s, dict) and str(s.get("id", "")).strip() == sid:
                return s
    # Fallback: first site (single-project install)
    for s in sites:
        if isinstance(s, dict):
            return s
    return None


# -------------------- theme rendering --------------------
def _slugify(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-") or "untitled"


def _markdown_to_html(text: str) -> str:
    """
    Minimal markdown → HTML conversion. Mirrors A.7-WP UPLOAD.py's process_article
    behavior closely enough for parity. Avoids a heavy dependency.
    """
    if text is None:
        return ""
    out: List[str] = []
    in_list = False

    for raw in str(text).split("\n"):
        line = raw.rstrip()
        if not line.strip():
            if in_list:
                out.append("</ul>")
                in_list = False
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            if in_list:
                out.append("</ul>")
                in_list = False
            level = len(m.group(1))
            content = html.escape(m.group(2).strip())
            out.append(f"<h{level}>{content}</h{level}>")
            continue

        m = re.match(r"^\s*[-*+]\s+(.+)$", line)
        if m:
            if not in_list:
                out.append("<ul>")
                in_list = True
            inner = html.escape(m.group(1).strip())
            inner = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", inner)
            out.append(f"<li>{inner}</li>")
            continue

        if in_list:
            out.append("</ul>")
            in_list = False
        escaped = html.escape(line.strip())
        escaped = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", escaped)
        out.append(f"<p>{escaped}</p>")

    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def _excerpt_from_article(article_text: str, max_len: int = 200) -> str:
    text = re.sub(r"^#{1,6}\s+.*$", "", str(article_text or ""), flags=re.MULTILINE)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        text = text[: max_len - 1].rsplit(" ", 1)[0] + "…"
    return text


def _public_image_path(value: str, project_out_dir: str, build_dir: str) -> str:
    """
    If value is a URL → keep as-is.
    Else → copy the local file into build/static/img/ and return /static/img/<name>.
    """
    if not value:
        return ""
    s = str(value).strip()
    if not s:
        return ""
    if s.startswith(("http://", "https://", "//", "data:")):
        return s
    abs_candidates = [
        s,
        os.path.join(project_out_dir, s),
        os.path.join(project_out_dir, "output_images", s),
        os.path.join(project_out_dir, "templates-html", s),
    ]
    src = next((p for p in abs_candidates if os.path.isfile(p)), None)
    if not src:
        return ""
    target_dir = os.path.join(build_dir, "static", "img")
    os.makedirs(target_dir, exist_ok=True)
    dst_name = os.path.basename(src)
    dst = os.path.join(target_dir, dst_name)
    if not os.path.exists(dst):
        shutil.copy2(src, dst)
    return f"/static/img/{dst_name}"


def _extract_recipe_parts(recipe_text: str) -> tuple:
    """
    Parse the `Recipe` column into (ingredients[], instructions[]).
    Mirrors A.7-WP UPLOAD.py's extract_recipe_details() heuristic.
    """
    if not recipe_text:
        return [], []
    txt = str(recipe_text).strip()
    if not txt:
        return [], []
    lines = [l.strip() for l in txt.splitlines()]
    current = None
    ingredients: List[str] = []
    instructions: List[str] = []
    for raw in lines:
        if not raw:
            continue
        if re.match(r"^(#{1,6}\s*)?(zutaten|ingredients|ingr[ée]dients|ingredientes|المكونات)\s*:?$", raw, re.I):
            current = "ing"
            continue
        if re.match(r"^(#{1,6}\s*)?(zubereitung|anleitung|instructions|pr[ée]paration|directions|method|طريقة التحضير)\s*:?$", raw, re.I):
            current = "ins"
            continue
        line = re.sub(r"^\s*[-*•]\s*", "", raw)
        line = re.sub(r"^\s*\d+\s*[\.\)\-]\s*", "", line)
        line = line.strip()
        if not line:
            continue
        if current == "ing":
            ingredients.append(line)
        elif current == "ins":
            instructions.append(line)
        else:
            if re.search(r"\b(g|kg|ml|l|tl|el|tsp|tbsp|cup|cups|oz|lb|lbs|stück|scheiben|prise)\b", line.lower()):
                ingredients.append(line)
    return ingredients, instructions


def _build_category_resolver(site_row: dict):
    """
    Build a function (raw_value)->display_name that maps the spreadsheet
    `categories` cell to a human-readable name. The cell is often:
      - a number (e.g. "3") that corresponds to settings.category_id_mapping["…"] == 3
      - a name already (e.g. "Low Carb Dinner Recipes")
      - a comma-separated list — first item wins
    Returns a callable so the mapping is computed once per project.
    """
    id_to_name: Dict[str, str] = {}
    settings = site_row.get("settings") if isinstance(site_row.get("settings"), dict) else {}
    mapping = settings.get("category_id_mapping") if isinstance(settings, dict) else None
    if isinstance(mapping, dict):
        for name, cid in mapping.items():
            try:
                id_to_name[str(int(cid))] = str(name).strip()
            except (TypeError, ValueError):
                if cid not in (None, ""):
                    id_to_name[str(cid).strip()] = str(name).strip()

    def resolve(raw: Any) -> str:
        s = ("" if raw is None else str(raw)).strip()
        if not s or s.lower() == "nan":
            return ""
        # Comma/semicolon separated → first item.
        first = re.split(r"[,;]", s, 1)[0].strip()
        if not first:
            return ""
        # If it looks like a number (possibly trailing .0 from pandas float coercion), map by ID.
        m = re.match(r"^-?\d+(?:\.0+)?$", first)
        if m:
            int_key = str(int(float(first)))
            if int_key in id_to_name:
                return id_to_name[int_key]
            # No mapping → leave the raw number; caller can decide
            return int_key
        return first

    return resolve


def _build_articles_data(df: pd.DataFrame, project_out_dir: str, build_dir: str, site_row: dict) -> List[Dict[str, Any]]:
    resolve_cat = _build_category_resolver(site_row)
    articles: List[Dict[str, Any]] = []
    used_slugs: Dict[str, int] = {}
    for idx, row in df.iterrows():
        title = str(row.get("Title", "") or "").strip()
        if not title:
            continue
        body_md = str(row.get("article", "") or "")
        if not body_md.strip():
            continue
        slug = _slugify(title)
        if slug in used_slugs:
            used_slugs[slug] += 1
            slug = f"{slug}-{used_slugs[slug]}"
        else:
            used_slugs[slug] = 1
        featured = _public_image_path(str(row.get("image_1", "") or ""), project_out_dir, build_dir)
        pin_img = _public_image_path(str(row.get("pinterest_image", "") or ""), project_out_dir, build_dir)
        category = resolve_cat(row.get("categories"))
        recipe_raw = str(row.get("Recipe", "") or "")
        ingredients, instructions = _extract_recipe_parts(recipe_raw)
        articles.append(
            {
                "slug": slug,
                "title": title,
                "excerpt": _excerpt_from_article(body_md),
                "featured_image": featured,
                "pinterest_image": pin_img,
                "category": category,
                "url": f"/article/{slug}/",
                "html_body": _markdown_to_html(body_md),
                "meta_description": str(row.get("rank_math_description", "") or row.get("pinterest_description", "") or "").strip(),
                "ingredients": ingredients,
                "instructions": instructions,
            }
        )
    return articles


def _pick_related(articles: List[Dict[str, Any]], current: Dict[str, Any], n: int = 3) -> List[Dict[str, Any]]:
    """3 related articles: same category first, then fill with others."""
    cat = (current.get("category") or "").strip().lower()
    slug = current.get("slug")
    same_cat = [a for a in articles if a["slug"] != slug and (a.get("category") or "").strip().lower() == cat and cat]
    if len(same_cat) >= n:
        return same_cat[:n]
    others = [a for a in articles if a["slug"] != slug and a not in same_cat]
    return (same_cat + others)[:n]


def _jinja_env(theme_dir: str):
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    env = Environment(
        loader=FileSystemLoader(theme_dir),
        autoescape=select_autoescape(["html", "xml"]),
        keep_trailing_newline=True,
    )
    env.filters["slug"] = _slugify
    return env


def _copy_theme_static(theme_dir: str, build_dir: str) -> None:
    src = os.path.join(theme_dir, "static")
    if not os.path.isdir(src):
        return
    dst = os.path.join(build_dir, "static")
    os.makedirs(dst, exist_ok=True)
    for entry in os.listdir(src):
        sp = os.path.join(src, entry)
        dp = os.path.join(dst, entry)
        if os.path.isdir(sp):
            if os.path.exists(dp):
                shutil.rmtree(dp)
            shutil.copytree(sp, dp)
        else:
            shutil.copy2(sp, dp)


def _resolve_default_author(theme_dir: str, site_row: dict) -> dict:
    """
    Merge default_author from theme.json with any override under site_row['settings']['author'].
    Returns a dict with at least: name, slug, title, bio, image_url.
    """
    meta_path = os.path.join(theme_dir, "theme.json")
    base: Dict[str, Any] = {}
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            theme_meta = json.load(f)
        if isinstance(theme_meta, dict) and isinstance(theme_meta.get("default_author"), dict):
            base = dict(theme_meta["default_author"])
    except (json.JSONDecodeError, OSError):
        pass

    overrides = {}
    settings = site_row.get("settings")
    if isinstance(settings, dict) and isinstance(settings.get("author"), dict):
        overrides = settings["author"]
    if isinstance(site_row.get("author"), dict):
        overrides = {**overrides, **site_row["author"]}

    merged = {**base, **{k: v for k, v in overrides.items() if v not in (None, "")}}
    if not merged.get("name"):
        merged["name"] = site_row.get("display_name") or site_row.get("id") or "The Chef"
    if not merged.get("slug"):
        merged["slug"] = _slugify(merged["name"])
    merged.setdefault("title", "Recipe Creator")
    merged.setdefault("bio", "")
    merged.setdefault("image_url", "")
    return merged


def render_theme(
    theme_slug: str,
    site_row: dict,
    project_out_dir: str,
    build_dir: str,
    version: str,
) -> int:
    theme_dir = os.path.join(THEMES_DIR, theme_slug)
    if not os.path.isdir(theme_dir):
        raise RuntimeError(f"Theme folder not found: {theme_dir}")
    if not os.path.isfile(os.path.join(theme_dir, "theme.json")):
        raise RuntimeError(f"theme.json missing in {theme_dir}")

    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
    os.makedirs(build_dir, exist_ok=True)
    _copy_theme_static(theme_dir, build_dir)

    recipes_path = os.path.join(project_out_dir, "Recipes.xlsx")
    if not os.path.isfile(recipes_path):
        raise RuntimeError(f"Recipes.xlsx not found in {project_out_dir}")

    df = pd.read_excel(recipes_path)
    log.info(f"Loaded {len(df)} rows from {recipes_path}")
    articles = _build_articles_data(df, project_out_dir, build_dir, site_row)
    log.info(f"Rendering {len(articles)} articles")

    categories: List[str] = []
    seen: set = set()
    for a in articles:
        c = (a.get("category") or "").strip()
        if c and c not in seen:
            seen.add(c)
            categories.append(c)

    now = _dt.datetime.now(_dt.timezone.utc)
    _settings = site_row.get("settings") if isinstance(site_row.get("settings"), dict) else {}
    # Title precedence: settings.site_name > row.site_name > display_name > id
    _site_title = (
        str(_settings.get("site_name") or "").strip()
        or str(site_row.get("site_name") or "").strip()
        or str(site_row.get("display_name") or "").strip()
        or str(site_row.get("id") or "").strip()
        or "Site"
    )
    _tagline = (
        str(_settings.get("site_tagline") or "").strip()
        or str(site_row.get("site_tagline") or "").strip()
        or "Easy & Delicious Recipes"
    )
    _desc = (
        str(_settings.get("site_description") or "").strip()
        or str(site_row.get("site_description") or "").strip()
        or f"Recipes for {_site_title}".strip()
    )
    site_ctx = {
        "title": _site_title,
        "tagline": _tagline,
        "description": _desc,
        "year": now.year,
        "built_at": now.strftime("%Y-%m-%d %H:%M UTC"),
        "version": version,
    }

    default_author = _resolve_default_author(theme_dir, site_row)

    env = _jinja_env(theme_dir)

    common_ctx = {
        "site": site_ctx,
        "categories": categories,
        "default_author": default_author,
    }

    # ---- Home ----
    index_tpl = env.get_template("index.html")
    with open(os.path.join(build_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_tpl.render(articles=articles, **common_ctx))

    # ---- Per-article ----
    article_tpl = env.get_template("article.html")
    art_root = os.path.join(build_dir, "article")
    os.makedirs(art_root, exist_ok=True)
    for a in articles:
        adir = os.path.join(art_root, a["slug"])
        os.makedirs(adir, exist_ok=True)
        related = _pick_related(articles, a, n=3)
        html_out = article_tpl.render(article=a, related=related, **common_ctx)
        with open(os.path.join(adir, "index.html"), "w", encoding="utf-8") as f:
            f.write(html_out)

    # ---- All recipes ----
    try:
        recipes_tpl = env.get_template("recipes.html")
    except Exception:
        recipes_tpl = None
    if recipes_tpl is not None:
        recipes_dir = os.path.join(build_dir, "recipes")
        os.makedirs(recipes_dir, exist_ok=True)
        with open(os.path.join(recipes_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(recipes_tpl.render(articles=articles, **common_ctx))

    # ---- Per-category ----
    try:
        category_tpl = env.get_template("category.html")
    except Exception:
        category_tpl = None
    if category_tpl is not None and categories:
        cat_root = os.path.join(build_dir, "category")
        os.makedirs(cat_root, exist_ok=True)
        for c in categories:
            cdir = os.path.join(cat_root, _slugify(c))
            os.makedirs(cdir, exist_ok=True)
            cat_articles = [a for a in articles if (a.get("category") or "").strip() == c]
            with open(os.path.join(cdir, "index.html"), "w", encoding="utf-8") as f:
                f.write(
                    category_tpl.render(
                        category=c,
                        recipes=cat_articles,
                        **common_ctx,
                    )
                )

    # ---- Author page ----
    try:
        author_tpl = env.get_template("author.html")
    except Exception:
        author_tpl = None
    if author_tpl is not None:
        author_dir = os.path.join(build_dir, "author", default_author["slug"])
        os.makedirs(author_dir, exist_ok=True)
        # In this data model every article is by the default author.
        with open(os.path.join(author_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(
                author_tpl.render(
                    author=default_author,
                    recipes=articles,
                    **common_ctx,
                )
            )

    return len(articles)


# -------------------- Cloudflare deploy --------------------
def _cf_api_request(method: str, path: str, token: str, json_body: Optional[dict] = None) -> tuple:
    """Minimal Cloudflare REST call. Returns (status_code, parsed_json_or_text)."""
    import requests as _requests
    url = "https://api.cloudflare.com/client/v4" + path
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if json_body is not None:
        headers["Content-Type"] = "application/json"
    try:
        r = _requests.request(method, url, headers=headers, json=json_body, timeout=30)
    except Exception as e:
        return 0, {"error": f"network: {e}"}
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"raw": r.text}


def _ensure_cf_pages_project(project_name: str, token: str, account_id: str) -> None:
    """
    Ensure the Cloudflare Pages project exists. If it does, no-op. If it
    doesn't, create it (Direct Upload, production_branch=main).
    Avoids wrangler's interactive 'Create this project?' prompt that breaks
    when running headless from app.py.
    """
    status, body = _cf_api_request(
        "GET",
        f"/accounts/{account_id}/pages/projects/{project_name}",
        token,
    )
    if status == 200 and isinstance(body, dict) and body.get("success"):
        log.info(f"✓ Pages project '{project_name}' already exists.")
        return
    if status == 404 or (
        isinstance(body, dict) and any(
            (isinstance(e, dict) and e.get("code") in (8000007, 8000008))
            for e in (body.get("errors") or [])
        )
    ):
        log.info(f"→ Pages project '{project_name}' not found. Creating it…")
        cs, cb = _cf_api_request(
            "POST",
            f"/accounts/{account_id}/pages/projects",
            token,
            json_body={"name": project_name, "production_branch": "main"},
        )
        if cs >= 400 or not isinstance(cb, dict) or not cb.get("success"):
            errs = []
            if isinstance(cb, dict):
                errs = [str((e or {}).get("message") or e) for e in (cb.get("errors") or [])]
            raise RuntimeError(
                f"Could not create Pages project '{project_name}' (HTTP {cs}): "
                + ("; ".join(errs) if errs else str(cb))
            )
        log.info(f"✓ Created Pages project '{project_name}'.")
        return
    # Other error (auth, network, etc.)
    errs = []
    if isinstance(body, dict):
        errs = [str((e or {}).get("message") or e) for e in (body.get("errors") or [])]
    raise RuntimeError(
        f"Could not verify Pages project '{project_name}' (HTTP {status}): "
        + ("; ".join(errs) if errs else str(body))
    )


def _run_wrangler_deploy(build_dir: str, project_name: str, token: str, account_id: str) -> dict:
    """
    Deploy via wrangler. Returns {"url": "...", "id": "..."} on success.
    """
    # 1) Make sure the Pages project exists before wrangler runs — wrangler in
    #    a non-interactive shell will hard-fail if it has to prompt to create it.
    _ensure_cf_pages_project(project_name, token, account_id)

    # 2) Build env. Wrangler 3 also reads CI=true to suppress prompts.
    env = os.environ.copy()
    env["CLOUDFLARE_API_TOKEN"] = token
    env["CLOUDFLARE_ACCOUNT_ID"] = account_id
    env["CI"] = "true"
    env["WRANGLER_SEND_METRICS"] = "false"

    # 3) Pin wrangler to a version compatible with the local Node.
    # Wrangler 4.x requires Node >= 22; wrangler 3.x supports Node >= 18.
    # Override via env WRANGLER_PIN (e.g. "wrangler@latest" or "wrangler@4").
    wrangler_pin = (os.environ.get("WRANGLER_PIN") or "wrangler@3").strip() or "wrangler@3"
    cmd = [
        "npx",
        "--yes",
        wrangler_pin,
        "pages",
        "deploy",
        build_dir,
        f"--project-name={project_name}",
        "--branch=main",
        "--commit-dirty=true",
    ]
    log.info("Running: " + " ".join(cmd))
    try:
        proc = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            cwd=_REPO_ROOT,
            shell=(os.name == "nt"),
        )
    except FileNotFoundError as e:
        raise RuntimeError(
            "npx not found. Install Node.js (which ships with npx) from https://nodejs.org/ "
            "to enable Cloudflare Pages deploys."
        ) from e

    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    log.info(out)
    if proc.returncode != 0:
        raise RuntimeError(f"wrangler failed (exit {proc.returncode}). Tail:\n{out[-1200:]}")

    # Wrangler typically prints multiple .pages.dev URLs:
    #   - the unique deployment URL  https://<hash>.<project>.pages.dev
    #   - the alias/branch URL       https://<branch>.<project>.pages.dev
    # Capture all of them, then pick the unique-deployment one first.
    all_urls = list(dict.fromkeys(re.findall(r"https?://[^\s\)\"\']+\.pages\.dev[^\s\)\"\']*", out)))
    dep_url = ""
    alias_url = ""
    for u in all_urls:
        host = u.split("//", 1)[-1].split("/", 1)[0]
        sub = host.split(".pages.dev", 1)[0]
        # Unique deployment hosts use a hex hash (>=6 hex chars) as the first label.
        if not dep_url and re.fullmatch(r"[0-9a-f]{6,}", sub.split(".", 1)[0] or ""):
            dep_url = u
        elif not alias_url:
            alias_url = u
    if not dep_url and all_urls:
        dep_url = all_urls[0]
    id_match = re.search(r"Deployment ID:\s*([A-Za-z0-9-]+)", out)
    dep_id = id_match.group(1) if id_match else ""
    return {"url": dep_url, "alias_url": alias_url, "all_urls": all_urls, "id": dep_id, "stdout": out}


# -------------------- main --------------------
def main() -> int:
    site = _resolve_site_row()
    if not site:
        log.error("Cannot find a site row in config/sites.json. Aborting.")
        return 1

    theme_slug = (site.get("theme_slug") or "").strip()
    if not theme_slug:
        log.error(
            "No theme selected for this project. Pick one in the dashboard "
            "(Theme dropdown on the project card) and click Save."
        )
        return 2

    cf_project_name = (site.get("cloudflare_project_name") or "").strip()
    if not cf_project_name:
        # Fallback to the theme's default cf_project_name
        meta = _load_json_file(os.path.join(THEMES_DIR, theme_slug, "theme.json"))
        cf_project_name = (meta.get("cf_project_name") or "").strip()
    if not cf_project_name:
        log.error(
            "No Cloudflare Pages project name set. Add cloudflare_project_name to the "
            "project row in config/sites.json (or to themes/<slug>/theme.json)."
        )
        return 3

    shared = _shared_keys()
    cf_token = (site.get("cloudflare_api_token") or "").strip() or (shared.get("cloudflare_api_token") or "").strip()
    cf_account = (site.get("cloudflare_account_id") or "").strip() or (shared.get("cloudflare_account_id") or "").strip()
    if not cf_token:
        log.error(
            "No Cloudflare API token. Set 'cloudflare_api_token' in config/shared_keys.json "
            "(or override per-project in sites.json)."
        )
        return 4
    if not cf_account:
        log.error(
            "No Cloudflare account_id. Set 'cloudflare_account_id' in config/shared_keys.json "
            "(or override per-project in sites.json)."
        )
        return 5

    out_dir = (site.get("out_dir") or "").strip()
    if not out_dir:
        sid = str(site.get("id") or "").strip()
        out_dir = f"{sid}-out" if sid else ""
    if not out_dir:
        log.error("Project out_dir is empty.")
        return 6
    project_out_dir = os.path.join(_REPO_ROOT, "ALL", out_dir)
    if not os.path.isdir(project_out_dir):
        log.error(f"Project output dir does not exist: {project_out_dir}")
        return 7

    version_label = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    build_dir = os.path.join(BUILD_ROOT, str(site.get("id") or "site"), version_label)
    os.makedirs(BUILD_ROOT, exist_ok=True)

    log.info(f"Theme           : {theme_slug}")
    log.info(f"CF project      : {cf_project_name}")
    log.info(f"Source dir      : {project_out_dir}")
    log.info(f"Build dir       : {build_dir}")
    log.info(f"Version label   : {version_label}")

    try:
        n_articles = render_theme(theme_slug, site, project_out_dir, build_dir, version_label)
    except Exception as e:
        log.exception(f"Render failed: {e}")
        return 10

    log.info(f"✓ Rendered {n_articles} articles into {build_dir}")
    log.info("→ Deploying to Cloudflare Pages via wrangler …")

    try:
        result = _run_wrangler_deploy(build_dir, cf_project_name, cf_token, cf_account)
    except Exception as e:
        log.exception(f"Deploy failed: {e}")
        return 11

    dep_url = result.get("url") or ""
    alias_url = result.get("alias_url") or ""
    all_urls = result.get("all_urls") or []

    log.info("==================== DEPLOYMENT URLS ====================")
    if dep_url:
        log.info(f"🔗 Deployment URL : {dep_url}")
    if alias_url:
        log.info(f"🔗 Alias URL      : {alias_url}")
    if not dep_url and not alias_url and all_urls:
        for u in all_urls:
            log.info(f"🔗 URL            : {u}")
    if not dep_url and not alias_url and not all_urls:
        log.warning("Deploy completed but no .pages.dev URL was captured from wrangler output.")
        log.warning("Check Cloudflare dashboard → Pages → project for the live URL.")
    if result.get("id"):
        log.info(f"   Deployment ID  : {result['id']}")
    log.info("=========================================================")

    log.info(f"🎉 CF UPLOAD finished for project {site.get('display_name') or site.get('id')} (theme={theme_slug}, version={version_label}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
