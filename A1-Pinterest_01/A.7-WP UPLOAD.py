import pandas as pd
import re
import requests
from requests.auth import HTTPBasicAuth
import os
import sys
import io
import json
from PIL import Image
import logging
from datetime import datetime, timedelta
import random
import time

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
import a1_config  # noqa: E402

_KWP = a1_config.load_keys()
# === WordPress: config/keys.json or env (WP_URL, WP_USER, WP_APP_PASSWORD) ===
WP_URL = (os.environ.get("WP_URL") or _KWP.get("wordpress_url") or "").strip() or "https://example.com"
WP_USER = (os.environ.get("WP_USER") or _KWP.get("wordpress_user") or "").strip() or "admin"
WP_APP_PASSWORD = (os.environ.get("WP_APP_PASSWORD") or _KWP.get("wordpress_app_password") or "").strip()
auth = HTTPBasicAuth(WP_USER, WP_APP_PASSWORD)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

EXCEL_PATH = a1_config.all_output_join("Recipes.xlsx")
df = pd.read_excel(EXCEL_PATH)

# --- Ensure required columns exist ---
required_columns = [
    'article',
    'image_1',
    'pinterest_title',
    'pinterest_description',
    'pinterest_image',
    'rank_math_focus_keyword',
    'rank_math_description',
    'rank_math_pillar_content',
    'categories',
    'Recipe',
    'Title'
]
# Json Recipe is preferred but optional
if 'Json Recipe' not in df.columns:
    df['Json Recipe'] = ''


if 'image_ing_1' not in df.columns:
    df['image_ing_1'] = ''

missing_columns = [col for col in required_columns if col not in df.columns]
if missing_columns:
    logging.error(f"Error: Missing columns in the Excel file: {', '.join(missing_columns)}")
    raise SystemExit(1)

for col in ['status', 'post_url']:
    if col in df.columns:
        df[col] = df[col].astype('string')
    else:
        df[col] = pd.Series([''] * len(df), dtype='string')

TOP_CROP_PIXELS = 100

# === Helpers & Functions ===
def save_progress(row_index: int):
    try:
        df.to_excel(EXCEL_PATH, index=False)
        logging.info(f"Progress saved to Excel after row {row_index}.")
    except Exception as e:
        logging.error(f"Failed to save Excel after row {row_index}: {e}")

def remove_emojis(text):
    if text is None:
        return ''
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"
        u"\U0001F300-\U0001F5FF"
        u"\U0001F680-\U0001F6FF"
        u"\U0001F1E0-\U0001F1FF"
        u"\U00002700-\U000027BF"
        u"\U0001F900-\U0001F9FF"
        u"\U00002600-\U000026FF"
        u"\U00002B00-\U00002BFF"
        "]+", flags=re.UNICODE)
    return emoji_pattern.sub(r'', str(text))

def process_article(article_text):
    lines = str(article_text or '').split('\n')
    processed_lines, paragraph_lines = [], []
    title = ""
    first_paragraph_after_heading = ""
    found_first_heading = False
    collected_first_paragraph = False
    collecting_paragraph = False
    header_pattern = re.compile(r'^(#{1,6})\s+(.*)')

    for idx, line in enumerate(lines):
        line = remove_emojis(line)
        header_match = header_pattern.match(line)
        if header_match:
            hashes, header_text = header_match.groups()
            level = len(hashes)
            if level == 1:
                title = header_text.strip()
            else:
                processed_lines.append(f"<h{level}>{header_text.strip()}</h{level}>")
                if not found_first_heading:
                    found_first_heading = True
                    collecting_paragraph = True
        else:
            line = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', line)
            processed_lines.append(f"<p>{line.strip()}</p>")
            if collecting_paragraph and not collected_first_paragraph:
                if line.strip():
                    paragraph_lines.append(line.strip())
                else:
                    if paragraph_lines:
                        first_paragraph_after_heading = ' '.join(paragraph_lines)
                        collected_first_paragraph = True
                        collecting_paragraph = False
                if idx == len(lines) - 1 and not collected_first_paragraph and paragraph_lines:
                    first_paragraph_after_heading = ' '.join(paragraph_lines)
                    collected_first_paragraph = True
                    collecting_paragraph = False
    content = '\n'.join(processed_lines)
    return remove_emojis(title), remove_emojis(content), remove_emojis(first_paragraph_after_heading)

def extract_recipe_details(recipe_text):
    if not recipe_text:
        return "", ""
    txt = str(recipe_text).strip()
    lines = [l.strip() for l in txt.splitlines()]
    current = None
    ingredients, instructions = [], []
    for raw in lines:
        if not raw:
            continue
        if re.match(r'^(#{1,6}\s*)?(zutaten|ingredients|ingrédients|ingredientes|المكونات)\s*:?', raw, re.I):
            current = 'ing'
            continue
        if re.match(r'^(#{1,6}\s*)?(zubereitung|anleitung|instructions|préparation|طريقة التحضير)\s*:?', raw, re.I):
            current = 'ins'
            continue
        line = re.sub(r'^\s*[-*•]\s*', '', raw)
        line = re.sub(r'^\s*\d+\s*[\.\)\-]\s*', '', line)
        if current == 'ing':
            ingredients.append(line)
        elif current == 'ins':
            instructions.append(line)
        else:
            if re.search(r'\b(g|kg|ml|l|tl|el|tsp|tbsp|stück|scheiben|prise)\b', line.lower()):
                ingredients.append(line)
    return '\n'.join(ingredients), '\n'.join(instructions)

def upload_image_to_wordpress(image_path, image_title, image_alt_text, image_caption, image_description, top_crop_pixels=0):
    if not image_path or str(image_path).strip() == '':
        logging.info("Empty image path provided. Skipping upload.")
        return None, None
    url = f"{WP_URL}/wp-json/wp/v2/media"
    try:
        if str(image_path).startswith(('http://', 'https://')):
            r = requests.get(image_path)
            r.raise_for_status()
            image = Image.open(io.BytesIO(r.content)).convert('RGB')
            original_filename = os.path.basename(str(image_path))
        else:
            image = Image.open(image_path).convert('RGB')
            original_filename = os.path.basename(image_path)
        if top_crop_pixels > 0:
            w, h = image.size
            image = image.crop((0, top_crop_pixels, w, h))
        buf = io.BytesIO()
        image.save(buf, format='WEBP', quality=80)
        webp_data = buf.getvalue()
        filename = f"{os.path.splitext(original_filename)[0]}.webp"
        headers = {'Content-Disposition': f'attachment; filename="{filename}"','Content-Type': 'image/webp'}
        upload_resp = requests.post(url, headers=headers, auth=auth, data=webp_data)
        upload_resp.raise_for_status()
        media_json = upload_resp.json()
        media_id = media_json['id']
        media_url = media_json['source_url']
        logging.info(f"Image '{filename}' uploaded with ID: {media_id}")
        update_url = f"{WP_URL}/wp-json/wp/v2/media/{media_id}"
        meta = {'title': image_title,'alt_text': image_alt_text,'caption': image_caption,'description': image_description}
        requests.post(update_url, headers={'Content-Type': 'application/json'}, auth=auth, json=meta).raise_for_status()
        return media_id, media_url
    except Exception as e:
        logging.error(f"Failed to upload image '{image_path}': {e}")
        return None, None

def construct_dpsp_share_options_json(pinterest_title, pinterest_description, featured_media_id=None, featured_media_url=None, pinterest_media_id=None, pinterest_media_url=None):
    dpsp = {
        "custom_image": {"id": str(featured_media_id) if featured_media_id else "","src": featured_media_url if featured_media_url else ""},
        "custom_title": pinterest_title,
        "custom_description": pinterest_description,
        "custom_image_pinterest": {"id": str(pinterest_media_id) if pinterest_media_id else "","src": pinterest_media_url if pinterest_media_url else ""},
        "custom_title_pinterest": pinterest_title,
        "custom_description_pinterest": pinterest_description,
        "custom_tweet": pinterest_title
    }
    return {'dpsp_share_options_json': json.dumps(dpsp)}

def create_wordpress_post(title, content, featured_media_id=None, meta_fields=None, categories=None, date=None):
    url = f"{WP_URL}/wp-json/wp/v2/posts"
    headers = {'Content-Type': 'application/json'}
    post = {'title': title, 'content': content, 'status': 'publish'}

    if featured_media_id:
        post['featured_media'] = featured_media_id
    if categories:
        post['categories'] = categories
    if meta_fields:
        post['meta'] = meta_fields

    try:
        resp = requests.post(url, headers=headers, auth=auth, json=post, timeout=45)
        resp.raise_for_status()
        post_data = resp.json()
        logging.info(f"Post '{title}' created. ID: {post_data['id']} | URL: {post_data['link']}")
        return post_data
    except Exception as e:
        logging.error(f"Failed to create post '{title}': {e}")
        return None


def update_rank_math_meta(post_id, focus_keyword='', description='', pillar_content='off'):
    focus_keyword = str(focus_keyword or '').strip()
    description = str(description or '').strip()
    pillar_value = 'on' if str(pillar_content or '').strip().lower() in ['1', 'true', 'yes', 'on'] else 'off'

    payload = {
        "objectID": post_id,
        "objectType": "post",
        "meta": {
            "rank_math_focus_keyword": focus_keyword,
            "rank_math_description": description,
            "rank_math_pillar_content": pillar_value
        }
    }

    try:
        r = requests.post(
            f"{WP_URL}/wp-json/rankmath/v1/updateMeta",
            headers={'Content-Type': 'application/json'},
            auth=auth,
            json=payload,
            timeout=45
        )

        logging.info(f"Rank Math update: {r.status_code} | {r.text}")

        return r.status_code in (200, 201)

    except Exception as e:
        logging.error(f"Rank Math update failed: {e}")
        return False

# ===================== NEW: WPRM taxonomies helpers =====================

def _ensure_term(taxonomy: str, name: str):
    """Create/get a term for WPRM taxonomy (wprm_course, wprm_cuisine, wprm_keyword)."""
    if not name or not str(name).strip():
        return None
    name = str(name).strip()
    base = f"{WP_URL}/wp-json/wp/v2/{taxonomy}"

    try:
        r = requests.get(base, params={"search": name, "per_page": 100}, auth=auth, timeout=30)
        r.raise_for_status()
        for it in r.json():
            if it.get("name", "").strip().lower() == name.lower():
                return it.get("id")
        r2 = requests.post(base, headers={"Content-Type": "application/json"}, auth=auth, json={"name": name}, timeout=30)
        r2.raise_for_status()
        return r2.json().get("id")
    except Exception as e:
        logging.warning(f"Term ensure failed for {taxonomy}='{name}': {e}")
        return None

def _assign_terms_to_recipe(recipe_id: int, course: str, cuisine: str, keywords: list):
    if not recipe_id:
        return
    payload = {}
    cid = _ensure_term("wprm_course", course) if course else None
    if cid: payload["wprm_course"] = [cid]
    zid = _ensure_term("wprm_cuisine", cuisine) if cuisine else None
    if zid: payload["wprm_cuisine"] = [zid]
    kids = []
    if isinstance(keywords, list):
        for kw in keywords:
            kid = _ensure_term("wprm_keyword", str(kw))
            if kid: kids.append(kid)
    if kids: payload["wprm_keyword"] = kids
    if not payload: return
    try:
        requests.post(
            f"{WP_URL}/wp-json/wp/v2/wprm_recipe/{recipe_id}",
            headers={"Content-Type": "application/json"},
            auth=auth,
            json=payload,
            timeout=30
        ).raise_for_status()
    except Exception as e:
        logging.warning(f"Failed assigning terms to recipe {recipe_id}: {e}")

# ===================== JSON → WPRM mapping (with robust ingredient strategy) =====================

def _coerce_str(v, default=""):
    if v is None: return default
    return str(v).strip()

def _parse_json_recipe(json_str):
    if not json_str or str(json_str).strip() == "":
        return None
    try:
        return json.loads(json_str)
    except Exception as e:
        logging.warning(f"Invalid JSON in 'Json Recipe': {e}")
        return None

def _items_amount_variant(rj):
    """ingredients using keys: amount/unit/ingredient/notes"""
    items = []
    for ing in (rj.get("ingredients") or []):
        if isinstance(ing, dict):
            items.append({
                "amount": _coerce_str(ing.get("amount")),
                "unit": _coerce_str(ing.get("unit")),
                "ingredient": _coerce_str(ing.get("name")),
                "notes": ""
            })
    return items

def _items_quantity_variant(rj):
    """ingredients using keys: quantity/unit/ingredient/notes"""
    items = []
    for ing in (rj.get("ingredients") or []):
        if isinstance(ing, dict):
            items.append({
                "quantity": _coerce_str(ing.get("amount")),
                "unit": _coerce_str(ing.get("unit")),
                "ingredient": _coerce_str(ing.get("name")),
                "notes": ""
            })
    return items

def _items_raw_variant(rj):
    """ingredients using 'raw' single string ('½ cup sugar')"""
    items = []
    for ing in (rj.get("ingredients") or []):
        if isinstance(ing, dict):
            raw = " ".join([_coerce_str(ing.get("amount")), _coerce_str(ing.get("unit")), _coerce_str(ing.get("name"))]).strip()
            items.append({"raw": re.sub(r"\s+", " ", raw)})
        elif isinstance(ing, str):
            items.append({"raw": ing.strip()})
    return items

def _group_from_items(items, variant="amount"):
    """Wrap items into grouped structure expected by many WPRM installs."""
    group_key = "ingredients"
    if variant == "raw":
        return [{"name": "", "ingredients": items}]
    else:
        return [{"name": "", "ingredients": items}]

def _instructions_group(rj):
    steps = []
    for s in (rj.get("instructions") or []):
        if isinstance(s, str) and s.strip():
            steps.append({"text": s.strip()})
    return [{"name": "", "instructions": steps}]

def _base_recipe_meta(rj, image_id):
    return {
        "name": _coerce_str(rj.get("name")),
        "summary": _coerce_str(rj.get("summary")),
        "servings": _coerce_str(rj.get("servings")),
        "prep_time": _coerce_str(rj.get("prep_time")),
        "cook_time": _coerce_str(rj.get("cook_time")),
        "total_time": _coerce_str(rj.get("total_time")),
        "notes": _coerce_str(rj.get("notes")),
        "image_id": image_id,
        "nutrition": {"calories": _coerce_str(rj.get("calories"))}
    }

def _post_wprm(payload):
    endpoint = f"{WP_URL}/wp-json/wp/v2/wprm_recipe"
    headers_recipe = {'Content-Type': 'application/json'}
    r = requests.post(endpoint, headers=headers_recipe, auth=auth, json=payload, timeout=45)
    r.raise_for_status()
    return r.json()

def _get_recipe(recipe_id: int):
    try:
        r = requests.get(f"{WP_URL}/wp-json/wp/v2/wprm_recipe/{recipe_id}", auth=auth, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

def create_wprm_recipe_from_json(recipe_json: dict, image_id):
    """
    Robust creator:
      1) Try items with 'amount'
      2) If ingredients empty -> update with 'quantity'
      3) If still empty -> update with 'raw'
      Attach course/cuisine/keywords at the end.
    """
    meta = _base_recipe_meta(recipe_json, image_id)

    # --- Attempt A: amount/unit/ingredient/notes ---
    payload_a = {"recipe": dict(meta)}
    payload_a["recipe"]["ingredients"]  = _group_from_items(_items_amount_variant(recipe_json), "amount")
    payload_a["recipe"]["instructions"] = _instructions_group(recipe_json)

    try:
        created = _post_wprm(payload_a)
        rid = created.get("id")
        if not rid:
            logging.warning(f"WPRM create response has no id (A): {created}")
            return created

        # verify ingredients present
        time.sleep(0.7)
        check = _get_recipe(rid) or {}
        ingr_ok = False
        ingr = (check.get("ingredients") or []) if isinstance(check, dict) else []
        if isinstance(ingr, list) and len(ingr) > 0:
            # if first group has items with either 'ingredient' or 'raw'
            grp = ingr[0].get("ingredients") if isinstance(ingr[0], dict) else []
            if grp and isinstance(grp, list) and len(grp) > 0:
                ingr_ok = True

        if not ingr_ok:
            # --- Attempt B: quantity/unit/ingredient/notes (PATCH) ---
            payload_b = {"recipe": {"ingredients": _group_from_items(_items_quantity_variant(recipe_json), "quantity")}}
            requests.post(
                f"{WP_URL}/wp-json/wp/v2/wprm_recipe/{rid}",
                headers={"Content-Type": "application/json"},
                auth=auth,
                json=payload_b,
                timeout=45
            ).raise_for_status()

            time.sleep(0.7)
            check = _get_recipe(rid) or {}
            ingr = (check.get("ingredients") or []) if isinstance(check, dict) else []
            ingr_ok = False
            if isinstance(ingr, list) and len(ingr) > 0:
                grp = ingr[0].get("ingredients") if isinstance(ingr[0], dict) else []
                if grp and isinstance(grp, list) and len(grp) > 0:
                    ingr_ok = True

        if not ingr_ok:
            # --- Attempt C: raw strings (PATCH) ---
            payload_c = {"recipe": {"ingredients": _group_from_items(_items_raw_variant(recipe_json), "raw")}}
            requests.post(
                f"{WP_URL}/wp-json/wp/v2/wprm_recipe/{rid}",
                headers={"Content-Type": "application/json"},
                auth=auth,
                json=payload_c,
                timeout=45
            ).raise_for_status()

        # Attach taxonomies
        _assign_terms_to_recipe(rid, recipe_json.get("course") or "", recipe_json.get("cuisine") or "", recipe_json.get("keywords") or [])
        return created

    except Exception as e:
        logging.error(f"WPRM create from JSON failed: {e}")
        return None

def create_wprm_recipe_fallback(recipe_name, summary, ingredients_text, instructions_text, image_id):
    """Legacy fallback when JSON recipe is unavailable."""
    endpoint = f"{WP_URL}/wp-json/wp/v2/wprm_recipe"
    headers_recipe = {'Content-Type': 'application/json'}
    simple_payload = {
        "recipe": {
            "name": recipe_name,
            "summary": summary,
            "ingredients": [{"name": line.strip()} for line in ingredients_text.split('\n') if line.strip()],
            "instructions": [{"name": step.strip()} for step in instructions_text.split('\n') if step.strip()],
            "image_id": image_id
        }
    }
    try:
        r = requests.post(endpoint, headers=headers_recipe, auth=auth, json=simple_payload)
        if r.status_code in (200, 201):
            return r.json()
        grouped_payload = {
            "recipe": {
                "name": recipe_name,
                "summary": summary,
                "ingredients": [{"name": "","ingredients": [{"raw": line.strip()} for line in ingredients_text.split('\n') if line.strip()]}],
                "instructions": [{"name": "","instructions": [{"text": step.strip()} for step in instructions_text.split('\n') if step.strip()]}],
                "image_id": image_id
            }
        }
        r2 = requests.post(endpoint, headers=headers_recipe, auth=auth, json=grouped_payload)
        r2.raise_for_status()
        return r2.json()
    except Exception as e:
        logging.error(f"WPRM create fallback failed: {e}")
        return None

# === Main Processing ===
for index, row in df.iterrows():
    try:
        if str(row.get('status', '')).strip().lower() == 'publish':
            logging.info(f"Row {index} already published. Skipping.")
            save_progress(index)
            continue

        article_text = row['article']
        image_1 = row['image_1']
        pinterest_title = row['pinterest_title']
        pinterest_description = row['pinterest_description']
        pinterest_image = row['pinterest_image']
        image_ing_1 = row.get('image_ing_1', '')
        recipe_text = row['Recipe']
        recipe_name_excel = row['Title']
        json_recipe_cell = row.get('Json Recipe', '')

        if not str(recipe_text).strip():
            recipe_text = str(row.get('article', '') or '')

        rank_math_focuskw = row.get('rank_math_focus_keyword', '')
        rank_math_metadesc = row.get('rank_math_description', '')
        rank_math_pillar = row.get('rank_math_pillar_content', '')
        categories = row['categories']

        # Build post HTML and get post title
        title, content, first_paragraph_after_heading = process_article(article_text)
        if not title or not content:
            logging.warning(f"Row {index}: Missing title or content. Skipping this row.")
            continue

        # WPRM recipe name = post title (fallback to excel title)
        wprm_recipe_name = title if str(title).strip() else str(recipe_name_excel or '').strip()

        # Upload images
        media_id, media_url = upload_image_to_wordpress(
            image_1, title, first_paragraph_after_heading, first_paragraph_after_heading, first_paragraph_after_heading
        )


        if pd.notna(image_ing_1) and str(image_ing_1).strip():
            image_ing_1_id, image_ing_1_url = upload_image_to_wordpress(
                image_ing_1, title, first_paragraph_after_heading, first_paragraph_after_heading, first_paragraph_after_heading
            )
            if image_ing_1_url:
                content = content.replace('{{image_ing_1}}', f'<img src="{image_ing_1_url}" alt="{first_paragraph_after_heading}" />')

        # Share meta
        share_meta = construct_dpsp_share_options_json(pinterest_title, pinterest_description, media_id, media_url)

        # Categories
        if pd.notna(categories) and str(categories).strip():
            try:
                categories_list = [int(cat.strip()) for cat in str(categories).split(',') if cat.strip().isdigit()]
            except ValueError:
                categories_list = []
        else:
            categories_list = []

        # Create post
        post_data = create_wordpress_post(
            title=title,
            content=content,
            featured_media_id=media_id,
            meta_fields=share_meta,
            categories=categories_list if categories_list else None
        )
        if not post_data:
            continue

        post_url = post_data['link']
        post_id = post_data['id']

        # Update Rank Math SEO after post creation
        update_rank_math_meta(
            post_id=post_id,
            focus_keyword=rank_math_focuskw,
            description=rank_math_metadesc,
            pillar_content=rank_math_pillar
        )

        df.at[index, 'status'] = 'publish'
        df.at[index, 'post_url'] = post_url

        # === Create WPRM recipe using JSON if available ===
        created_recipe = None
        parsed_json_recipe = _parse_json_recipe(json_recipe_cell)

        if parsed_json_recipe:
            parsed_json_recipe['name'] = remove_emojis(wprm_recipe_name) or parsed_json_recipe.get('name', '')
            created_recipe = create_wprm_recipe_from_json(parsed_json_recipe, image_id=media_id)

        if not created_recipe:
            # Fallback to legacy extraction
            ingredients_text, instructions_text = extract_recipe_details(recipe_text)
            if not ingredients_text and not instructions_text:
                art = str(row.get('article', '') or '')
                m_ing = re.search(r'(#+\s*Zutaten.*?)(#+\s*(Zubereitung|Anleitung)|\Z)', art, flags=re.S | re.I)
                if m_ing:
                    ingredients_text = '\n'.join([l.strip('-• ') for l in m_ing.group(1).splitlines() if not l.startswith('#')])
                m_ins = re.search(r'(#+\s*(Zubereitung|Anleitung).*?)((#+\s*\w+)|\Z)', art, flags=re.S | re.I)
                if m_ins:
                    instructions_text = '\n'.join([l.strip('1234567890.-) ') for l in m_ins.group(1).splitlines() if not l.startswith('#')])

            created_recipe = create_wprm_recipe_fallback(
                recipe_name=wprm_recipe_name,
                summary=pinterest_description,
                ingredients_text=ingredients_text,
                instructions_text=instructions_text,
                image_id=media_id
            )

        # Append shortcode to post if recipe created
        if created_recipe and created_recipe.get("id"):
            recipe_id = created_recipe["id"]
            updated_content = post_data['content']['rendered'] + f"\n\n[wprm-recipe id='{recipe_id}']"
            try:
                requests.post(
                    f"{WP_URL}/wp-json/wp/v2/posts/{post_id}",
                    headers={'Content-Type': 'application/json'},
                    auth=auth,
                    json={'content': updated_content}
                ).raise_for_status()
            except Exception as e:
                logging.warning(f"Failed to append WPRM shortcode to post {post_id}: {e}")

        save_progress(index)

    except Exception as e:
        logging.error(f"Unexpected error for row {index}: {e}")
        save_progress(index)
        continue

df.to_excel(EXCEL_PATH, index=False)
logging.info("All done. Final Excel saved.")
