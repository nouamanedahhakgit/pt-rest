import openai
import pandas as pd
import os
import re
import sys
import unicodedata
import json

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
import openai_chat_compat  # noqa: E402

openai_chat_compat.install()

import a1_config  # noqa: E402

_S4 = a1_config.load_settings()
_K4 = a1_config.load_keys()
a1_config.set_openai_key_from_keys(_K4)
_MODEL_A4 = a1_config.get_openai_model(_S4, _K4)
_PP4 = a1_config.load_prompts("a4_articles")

# ===== Language and article (from config/settings.json) =====
ARTICLE_LANGUAGE = str(_S4.get("article_language", "English"))
# Per-site under ALL/{out_dir}/ (see config/sites.json + PINTEREST_SITE_ID)
RECIPE_EXCEL = a1_config.all_output_join("Recipes.xlsx")
OUTLINE_EXCEL = a1_config.all_output_join("outline_parts.xlsx")

RECIPE_SHEET_NAME = str(_S4.get("a4_recipe_sheet", "Sheet1"))
RECIPE_COLUMN_LABEL = str(_S4.get("a4_recipe_column", "Recipe"))

TOTAL_WORDS = int(_S4.get("a4_total_words", 3000))
MAX_TOKENS_PER_PART = int(_S4.get("a4_max_tokens_per_part", 3000))

# ================================
# NEW: Recipe Card extraction (source of truth)
# ================================
CARD_KEYS = ["Prep Time", "Cook Time", "Total Time", "Course", "Cuisine", "Servings", "Calories"]

def extract_recipe_card_fields(recipe_text: str) -> dict:
    """
    كيستخرج القيم من Recipe text من سطور:
    Prep Time: ...
    Cook Time: ...
    Total Time: ...
    Course: ...
    Cuisine: ...
    Servings: ...
    Calories: ...
    """
    if not isinstance(recipe_text, str):
        recipe_text = ""
    out = {k: "" for k in CARD_KEYS}
    for k in CARD_KEYS:
        m = re.search(rf"(?im)^\s*{re.escape(k)}\s*:\s*(.+)\s*$", recipe_text)
        if m:
            out[k] = m.group(1).strip()
    return out

def build_card_context_block(card: dict) -> str:
    """
    بلوك نصي كنمرّروه ل OpenAI باش يلتزم به حرفيا.
    إذا القيمة فارغة كنخليها N/A.
    """
    def v(key):
        val = (card.get(key) or "").strip()
        return val if val else "N/A"

    return (
        "RECIPE CARD (MUST USE EXACT VALUES):\n"
        f"Prep Time: {v('Prep Time')}\n"
        f"Cook Time: {v('Cook Time')}\n"
        f"Total Time: {v('Total Time')}\n"
        f"Course: {v('Course')}\n"
        f"Cuisine: {v('Cuisine')}\n"
        f"Servings: {v('Servings')}\n"
        f"Calories: {v('Calories')}\n"
    )

def build_recipe_overview_lines(card: dict) -> str:
    """
    Recipe Overview bullets ثابتين وبنفس الترتيب.
    إذا N/A => Not specified in the recipe
    """
    def v(key):
        val = (card.get(key) or "").strip()
        return val if val and val.upper() != "N/A" else "Not specified in the recipe"

    return (
        f"- Prep Time: {v('Prep Time')}\n"
        f"- Cook Time: {v('Cook Time')}\n"
        f"- Total Time: {v('Total Time')}\n"
        f"- Course: {v('Course')}\n"
        f"- Cuisine: {v('Cuisine')}\n"
        f"- Servings: {v('Servings')}\n"
        f"- Calories: {v('Calories')}\n"
    )

# ================================
# Language-aware terms
# ================================

def _strip_accents(s: str) -> str:
    if not isinstance(s, str):
        return ""
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def _normalize_key(s: str) -> str:
    s2 = _strip_accents((s or "").lower().strip())
    s2 = re.sub(r'^[#\s]+', '', s2)
    s2 = re.sub(r'[:：]+$', '', s2).strip()
    return s2

_LANG_INGREDIENTS = {
    "English":      {"label": "Ingredients",  "aliases": {"ingredients", "ingredient", "what you need", "you will need", "what you'll need", "shopping list", "grocery list"}},
    "Deutsch":      {"label": "Zutaten",      "aliases": {"zutaten", "einkaufsliste"}},
    "Español":      {"label": "Ingredientes", "aliases": {"ingredientes", "lista de la compra", "lista de compra"}},
    "Français":     {"label": "Ingrédients",  "aliases": {"ingredients", "ingrédients", "liste de courses"}},
    "Português":    {"label": "Ingredientes", "aliases": {"ingredientes", "lista de compras"}},
    "العربية":       {"label": "المكوّنات",     "aliases": {"المكونات", "المكوّنات", "قائمة المشتريات"}},
}

def _get_ing_terms(lang: str):
    base = _LANG_INGREDIENTS.get(lang, _LANG_INGREDIENTS["English"])
    aliases = set(base["aliases"]) | _LANG_INGREDIENTS["English"]["aliases"] | {base["label"], "Ingredients"}
    aliases_norm = {_normalize_key(a) for a in aliases}
    return base["label"], aliases_norm

INGREDIENTS_LABEL, _ING_HEADERS = _get_ing_terms(ARTICLE_LANGUAGE)

# ================================
# Regex: Headings / HR / Cleaning
# ================================

SETEXT_H1 = re.compile(r'^(?P<text>[^\n]+)\n=+\s*$', re.MULTILINE)
ATX_HEADING = re.compile(r'^(?P<hashes>#{1,6})\s*(?P<text>.+?)\s*#*\s*$', re.MULTILINE)
HR_LINE = re.compile(r'^\s*(?:[-_*]\s*){3,}\s*$')
HEADING_LEVEL_RE = re.compile(r'^(#{1,6})\s+\S')

def strip_horizontal_rules(text: str) -> str:
    if not isinstance(text, str):
        return text or ""
    lines = (text or "").splitlines()
    kept = [ln for ln in lines if not HR_LINE.match(ln)]
    out = "\n".join(kept)
    out = re.sub(r'\n{3,}', '\n\n', out)
    out = out.strip()
    return (out + "\n") if out else ""

def remove_emojis(text: str) -> str:
    emoji_pattern = re.compile(
        "[" u"\U0001F600-\U0001F64F"
        u"\U0001F300-\U0001F5FF"
        u"\U0001F680-\U0001F6FF"
        u"\U0001F1E0-\U0001F1FF"
        u"\U00002500-\U00002BEF"
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251" "]+", flags=re.UNICODE)
    return emoji_pattern.sub(r'', text or "")

def get_heading_level(line: str) -> int:
    m = HEADING_LEVEL_RE.match(line or "")
    return len(m.group(1)) if m else 0

# ================================
# Strict heading normalization (outline-driven) + orphan H3 inference
# ================================

_LEADING_NUM = re.compile(r'^\s*(?:\d+|[A-Za-z]|[ivxlcdmIVXLCDM]+)\s*[\.\)\-:]\s*')

def _strip_leading_numbering(s: str) -> str:
    return _LEADING_NUM.sub('', (s or '').strip()).strip()

def parse_outline_heading_map(outline: str):
    """
    Map: normalized heading text -> level (2 or 3)
    """
    hmap = {}
    for raw in (outline or "").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        m = re.match(r'^(#{2,3})\s+(.*)$', raw)
        if not m:
            continue
        lvl = len(m.group(1))
        if lvl < 2:
            continue
        if lvl > 3:
            lvl = 3
        txt = _strip_leading_numbering(m.group(2))
        key = _normalize_key(txt)
        if key:
            hmap[key] = lvl
    return hmap

_STOP = set("""
a an the of and or to for in on with from by at as is are be this that those these your my our their its it's
how why what when where tips guide step steps method methods notes faq faqs overview introduction conclusion
""".split())

def _tokens(s: str):
    s = _normalize_key(re.sub(r'[^A-Za-z0-9\s]', ' ', s or ''))
    return [w for w in s.split() if w and w not in _STOP]

def _jaccard(a, b):
    A, B = set(_tokens(a)), set(_tokens(b))
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)

def looks_like_subheading(line: str) -> bool:
    """
    Heuristic to detect orphan subheadings written as plain text
    """
    if not line:
        return False
    s = line.strip()
    if not s:
        return False
    if s.startswith(('#','- ','* ','>')):
        return False
    if s.endswith(('.', '?', '!')):
        return False
    if len(s) < 8 or len(s) > 120:
        return False
    words = [w for w in re.findall(r'\w+', s)]
    if len(words) < 2 or len(words) > 12:
        return False
    return True

def normalize_headings_strict(markdown: str, heading_map: dict, enforce_only_h2_h3=True) -> str:
    if not isinstance(markdown, str):
        return markdown or ""

    text = SETEXT_H1.sub(lambda m: f"# {m.group('text').strip()}", markdown or "")
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    out = []
    seen_h1 = False

    for raw in lines:
        if not raw.strip():
            out.append(raw)
            continue

        m = re.match(r'^(#{1,6})\s+(.*)$', raw)
        if m:
            level = len(m.group(1))
            content = _strip_leading_numbering(re.sub(r'\s*#+\s*$', '', m.group(2)).strip())
            key = _normalize_key(content)
            if key in heading_map:
                level = heading_map[key]
            if level == 1:
                if seen_h1:
                    level = 2
                else:
                    seen_h1 = True
            if level >= 2 and enforce_only_h2_h3:
                level = 3 if level > 3 else level
            out.append(f"{'#' * level} {content}".rstrip())
        else:
            content = raw.strip()
            key = _normalize_key(_strip_leading_numbering(content))
            if key in heading_map and content:
                lvl = heading_map[key]
                if lvl == 1:
                    lvl = 2 if seen_h1 else 1
                    seen_h1 = True
                if lvl >= 2 and enforce_only_h2_h3:
                    lvl = 3 if lvl > 3 else lvl
                out.append(f"{'#' * lvl} {_strip_leading_numbering(content)}")
            else:
                out.append(raw)

    # Safety pass: demote extra H1
    lines2 = out
    out = []
    seen_h1 = False
    for ln in lines2:
        m = re.match(r'^(#{1,6})\s+(.*)$', ln)
        if m and len(m.group(1)) == 1:
            if seen_h1:
                out.append(f"## {m.group(2).strip()}")
            else:
                out.append(ln)
                seen_h1 = True
        else:
            out.append(ln)

    return re.sub(r'\n{3,}', '\n\n', "\n".join(out)).strip() + "\n"

def promote_orphan_subheads(text: str, heading_map: dict) -> str:
    if not isinstance(text, str):
        return text or ""
    lines = text.splitlines()
    out = []
    inside_h2 = False

    h3_labels = [k for k, v in heading_map.items() if v == 3]

    for i, ln in enumerate(lines):
        stripped = ln.strip()

        if re.match(r'^\s*##\s+\S', ln):
            inside_h2 = True
            out.append(ln)
            continue
        if re.match(r'^\s*#\s+\S', ln) and not re.match(r'^\s*###\s+\S', ln):
            inside_h2 = False
            out.append(ln)
            continue

        if inside_h2 and looks_like_subheading(stripped) and not stripped.startswith('#'):
            out.append(f"### {stripped}")
        else:
            m = re.match(r'^\s*#{4,}\s+(.*)$', ln)
            if m:
                out.append(f"### {m.group(1).strip()}")
            else:
                out.append(ln)

    return re.sub(r'\n{3,}', '\n\n', "\n".join(out)).strip() + "\n"

# ================================
# H2 helpers + Image placement (after Section 3 ends)
# ================================

def _is_h2(line: str) -> bool:
    return bool(re.match(r'^\s*##\s+\S', line or ""))

def _is_ing_h2(line: str) -> bool:
    m = re.match(r'^\s*##\s+(.+)$', line or "")
    if not m:
        return False
    raw = m.group(1)
    cleaned = re.sub(r'^\d+[\.\):\-]\s*', '', raw)
    key = _normalize_key(cleaned)
    return (key in _ING_HEADERS) or ("ingredients" in key)

def insert_image_after_section3(text: str, placeholder="{{image_ing_1}}") -> str:
    if not text or not isinstance(text, str):
        return text or ""
    text = re.sub(rf'\n*\s*{re.escape(placeholder)}\s*\n*', '\n', text)
    lines = text.splitlines()
    n = len(lines)
    h2_indices = [i for i, ln in enumerate(lines) if _is_h2(ln)]
    if len(h2_indices) < 3:
        out = "\n".join(lines)
        out = re.sub(r'\n{3,}', '\n\n', out)
        return out.strip() + "\n"
    third_h2_start = h2_indices[2]
    fourth_h2_start = None
    for idx in h2_indices:
        if idx > third_h2_start:
            fourth_h2_start = idx
            break
    section3_end = fourth_h2_start if fourth_h2_start is not None else n
    new_lines = lines[:section3_end] + ["", placeholder, ""] + lines[section3_end:]
    out = "\n".join(new_lines)
    out = re.sub(r'\n{3,}', '\n\n', out)
    return out.strip() + "\n"

def _enforce_image_spacing(text: str, placeholder="{{image_ing_1}}") -> str:
    text = re.sub(r'\n*\s*' + re.escape(placeholder) + r'\s*\n*', f'\n\n{placeholder}\n\n', text or "")
    text = re.sub(r'\n{3,}', '\n\n', text)
    return (text.strip() + "\n") if text else ""

# ================================
# Core Functions (prompts: clear H1 + non-numbered headings)
# ================================

def _ensure_columns_and_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    if 'Statut Article' not in df.columns:
        df['Statut Article'] = pd.Series([None]*len(df), dtype='object')
    else:
        df['Statut Article'] = df['Statut Article'].astype('object')

    if 'article' not in df.columns:
        df['article'] = pd.Series([None]*len(df), dtype='object')
    else:
        df['article'] = df['article'].astype('object')

    if 'article_title' not in df.columns:
        df['article_title'] = pd.Series([None]*len(df), dtype='object')
    else:
        df['article_title'] = df['article_title'].astype('object')

    if 'id_article' not in df.columns:
        df['id_article'] = pd.Series([pd.NA]*len(df), dtype='Int64')
    else:
        try:
            df['id_article'] = df['id_article'].astype('Int64')
        except Exception:
            df['id_article'] = pd.to_numeric(df['id_article'], errors='coerce').astype('Int64')

    return df

def read_recipes_from_excel(file_path: str, sheet_name: str) -> pd.DataFrame:
    df = pd.read_excel(file_path, sheet_name=sheet_name)
    if RECIPE_COLUMN_LABEL not in df.columns:
        raise ValueError(f"Column '{RECIPE_COLUMN_LABEL}' not found in sheet '{sheet_name}'.")
    df = _ensure_columns_and_dtypes(df)
    return df

def extract_title(recipe: str) -> str:
    delimiters = ['Ingredients', 'Instructions', 'Prep_Time', 'Total_Time', 'Servings']
    for delimiter in delimiters:
        if delimiter in recipe:
            return recipe.split(delimiter)[0].strip('_').strip()
    return recipe.split('\n')[0].strip()

def create_outline(recipe: str, card_context: str) -> str:
    o = _PP4.get("outline") or {}
    prompt = (o.get("user") or "").format(
        total_words=TOTAL_WORDS,
        article_language=ARTICLE_LANGUAGE,
        ingredients_label=INGREDIENTS_LABEL,
        card_context=card_context,
        recipe=recipe,
    )
    system_msg = (o.get("system") or "").format(article_language=ARTICLE_LANGUAGE)
    response = openai.ChatCompletion.create(
        model=_MODEL_A4,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt}
        ],
        max_tokens=int(o.get("max_tokens", 1000)),
    )
    return response['choices'][0]['message']['content'].strip()

def split_outline(outline: str) -> tuple:
    lines = [l.strip() for l in (outline or "").splitlines() if l.strip()]
    mid = len(lines) // 2 if len(lines) > 1 else 1
    return "\n".join(lines[:mid]), "\n".join(lines[mid:])

def generate_article_part1(outline_part: str, recipe_text: str, card_context: str, overview_lines: str) -> str:
    p1 = _PP4.get("part1") or {}
    prompt = (p1.get("user") or "").format(
        article_language=ARTICLE_LANGUAGE,
        ingredients_label=INGREDIENTS_LABEL,
        overview_lines=overview_lines,
        card_context=card_context,
        recipe_text=recipe_text,
        outline_part=outline_part,
    )
    system_msg = (p1.get("system") or "").format(article_language=ARTICLE_LANGUAGE)
    response = openai.ChatCompletion.create(
        model=_MODEL_A4,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt}
        ],
        max_tokens=MAX_TOKENS_PER_PART,
    )
    return response['choices'][0]['message']['content'].strip()

def generate_article_part2(outline_part: str, recipe_text: str, card_context: str) -> str:
    p2 = _PP4.get("part2") or {}
    prompt = (p2.get("user") or "").format(
        article_language=ARTICLE_LANGUAGE,
        card_context=card_context,
        recipe_text=recipe_text,
        outline_part=outline_part,
    )
    system_msg = (p2.get("system") or "").format(article_language=ARTICLE_LANGUAGE)
    response = openai.ChatCompletion.create(
        model=_MODEL_A4,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt}
        ],
        max_tokens=MAX_TOKENS_PER_PART,
    )
    return response['choices'][0]['message']['content'].strip()

def merge_articles(part1: str, part2: str) -> str:
    return f"{part1}\n\n{part2}"

# ================================
# Title extraction (ONLY from first H1 '# Title')
# ================================

def extract_article_title_from_part1(part1_text: str) -> str:
    txt = part1_text or ""
    if not isinstance(txt, str):
        return ""
    txt = txt.replace("\r\n", "\n").replace("\r", "\n")
    txt = re.sub(r"[\u200B-\u200D\uFEFF]", "", txt)
    m = re.search(r"(?m)^\s*#\s+(.+?)\s*$", txt)
    if not m:
        return ""
    title = m.group(1).strip()
    title = remove_emojis(title)
    title = re.sub(r"\s*#+\s*$", "", title).strip()
    return title

# ================================
# Main
# ================================

def _ensure_save_dirs_and_write(path: str, content: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def main():
    if not openai.api_key:
        raise RuntimeError("Missing OPENAI_API_KEY. Set it as environment variable.")

    df = read_recipes_from_excel(RECIPE_EXCEL, RECIPE_SHEET_NAME)
    print(f"Found {len(df)} rows.")

    for idx, row in df.iterrows():
        recipe = str(row[RECIPE_COLUMN_LABEL]).strip()
        recipe_hint = extract_title(recipe)
        print(f"\n=== Recipe {idx+1}: {recipe_hint} ===")

        if str(row.get("Statut Article", "")).upper() == "DONE ARTICLE":
            print("SKIPPED: already done")
            continue

        # ✅ NEW: extract recipe card + inject into prompts
        card = extract_recipe_card_fields(recipe)
        card_context = build_card_context_block(card)
        overview_lines = build_recipe_overview_lines(card)

        # 1) Outline
        outline = create_outline(recipe, card_context)
        part1_outline, part2_outline = split_outline(outline)
        heading_map = parse_outline_heading_map(outline)

        # 2) Part1
        part1 = generate_article_part1(part1_outline, recipe, card_context, overview_lines)
        part1 = normalize_headings_strict(part1, heading_map, enforce_only_h2_h3=True)
        part1 = promote_orphan_subheads(part1, heading_map)
        part1 = strip_horizontal_rules(part1)

        # Insert image AFTER Ingredients (section 3)
        part1 = insert_image_after_section3(part1, placeholder="{{image_ing_1}}")

        # 3) Part2
        part2 = generate_article_part2(part2_outline, recipe, card_context)
        part2 = normalize_headings_strict(part2, heading_map, enforce_only_h2_h3=True)
        part2 = promote_orphan_subheads(part2, heading_map)
        part2 = strip_horizontal_rules(part2)

        # 4) Merge + Final cleanup
        final_article = merge_articles(part1, part2)
        final_article = normalize_headings_strict(final_article, heading_map, enforce_only_h2_h3=True)
        final_article = promote_orphan_subheads(final_article, heading_map)
        final_article = strip_horizontal_rules(final_article)

        # Ensure spacing around images
        final_article = _enforce_image_spacing(final_article, "{{image_ing_1}}")
        final_article = re.sub(r'\n{3,}', '\n\n', final_article).strip() + "\n"

        # 5) Title extraction
        art_title = extract_article_title_from_part1(part1)

        # 6) Save / update row
        df.at[idx, 'article'] = final_article
        df.at[idx, 'Statut Article'] = "DONE ARTICLE"
        df.at[idx, 'id_article'] = int(idx + 1)
        df.at[idx, 'article_title'] = art_title

        # Save to Excel continuously
        df.to_excel(RECIPE_EXCEL, index=False)

        # Save .txt
        safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in (recipe_hint or "")).replace(" ", "_")[:100]
        filename = f"../art/{safe_name or f'article_{idx+1}'}_article.txt"
        _ensure_save_dirs_and_write(filename, final_article)

        print(f"SAVED: {filename}")
        print(f"Title: {art_title}")

    print("All articles processed.")

if __name__ == "__main__":
    main()
