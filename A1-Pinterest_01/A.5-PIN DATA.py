import os
import sys
import pandas as pd
import openai
import re
import textwrap

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
import openai_chat_compat  # noqa: E402

openai_chat_compat.install()

import a1_config  # noqa: E402

_S5 = a1_config.load_settings()
_K5 = a1_config.load_keys()
a1_config.set_openai_key_from_keys(_K5)
OPENAI_API_KEY = (_K5.get("openai_api_key") or os.environ.get("OPENAI_API_KEY", "")).strip()
_PP5 = a1_config.load_prompts("a5_pin_data")

ARTICLE_LANGUAGE = str(_S5.get("article_language", "English"))

_LEGACY_CATEGORY_SHORT_NAMES = frozenset(
    {"drinks", "dessert", "appetizers", "dinner", "breakfast"}
)

# ================================
# Helpers
# ================================
def _category_id_mapping():
    return a1_config.get_category_id_mapping(_S5)


def _category_needs_refresh(category_val, categories_val, mapping):
    """True when category is empty, legacy (dinner/drinks/…), unknown, or ID mismatch."""
    cat = str(category_val or "").strip()
    if is_empty(cat):
        return True
    if cat.lower() in _LEGACY_CATEGORY_SHORT_NAMES:
        return True
    canonical = cat if cat in mapping else next(
        (k for k in mapping if k.lower() == cat.lower()), None
    )
    if not canonical:
        return True
    expected = mapping.get(canonical)
    if expected is None:
        return True
    try:
        current = int(float(categories_val)) if not is_empty(categories_val) else None
    except (ValueError, TypeError):
        current = None
    return current != expected


def _resolve_row_category(category_val, recipe, api_key, mapping):
    names = list(mapping.keys())
    cat = str(category_val or "").strip()
    if cat:
        resolved = a1_config.resolve_category_name(cat, names)
        if resolved in mapping:
            return resolved
    return categorize_Recipe(recipe, api_key)


def _sync_category_columns(df, base_mask, api_key):
    mapping = _category_id_mapping()
    if not mapping:
        return 0
    mask = base_mask & df.apply(
        lambda row: _category_needs_refresh(
            row.get("category"), row.get("categories"), mapping
        ),
        axis=1,
    )
    fixed = int(mask.sum()) if hasattr(mask, "sum") else 0
    if mask.any():
        df.loc[mask, "category"] = df.loc[mask].apply(
            lambda row: _resolve_row_category(
                row.get("category"), row.get("Recipe"), api_key, mapping
            ),
            axis=1,
        )
    sync_mask = base_mask & df["category"].apply(lambda c: not is_empty(c))
    if sync_mask.any():
        df.loc[sync_mask, "categories"] = df.loc[sync_mask, "category"].map(mapping)
    return fixed
def is_empty(val):
    if val is None:
        return True
    if isinstance(val, float) and pd.isna(val):
        return True
    return str(val).strip() == ""

def clean_text(text):
    if text is None:
        return ""
    unwanted_chars = ['"']
    for char in unwanted_chars:
        text = text.replace(char, '')
    return text

def clean_punctuation(text):
    if text is None:
        return ""
    return re.sub(r'[^\w\s]', '', text)

# ================================
# OpenAI generators (language-aware)
# ================================
def generate_recipe_title_pin(Recipe, api_key):
    openai.api_key = api_key
    sec = _PP5.get("recipe_title_pin") or {}
    system = a1_config.format_prompt_template(
        a1_config.require_prompt_string(_PP5, "recipe_title_pin", "system", bundle="a5_pin_data"),
        bundle="a5_pin_data",
        article_language=ARTICLE_LANGUAGE,
    )
    response = openai.ChatCompletion.create(
        model=a1_config.get_openai_model(_S5, _K5),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": Recipe}
        ],
        max_tokens=int(sec.get("max_tokens", 80)),
        temperature=float(sec.get("temperature", 0.7))
    )
    title_pin = response.choices[0].message['content'].strip()
    # رجّع النص كما هو (غير نحيدو الاقتباسات المزدوجة إن وُجدت)
    return clean_text(title_pin)


def generate_pinterest_title(Recipe, api_key):
    """
    Create a clear and engaging Pinterest Pin title for the given Recipe.
    Keep it under 100 characters, include common Pinterest search keywords,
    and make it appeal to users looking for new recipe ideas.
    """
    openai.api_key = api_key
    sec = _PP5.get("pinterest_title") or {}
    system = a1_config.format_prompt_template(
        a1_config.require_prompt_string(_PP5, "pinterest_title", "system", bundle="a5_pin_data"),
        bundle="a5_pin_data",
        article_language=ARTICLE_LANGUAGE,
    )
    user = a1_config.format_prompt_template(
        a1_config.require_prompt_string(_PP5, "pinterest_title", "user", bundle="a5_pin_data"),
        bundle="a5_pin_data",
        article_language=ARTICLE_LANGUAGE,
        recipe=Recipe,
    )
    response = openai.ChatCompletion.create(
        model=a1_config.get_openai_model(_S5, _K5),
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=int(sec.get("max_tokens", 120))
    )
    return response.choices[0].message['content'].strip()

def generate_pinterest_keywords(Recipe, api_key):
    openai.api_key = api_key
    sec = _PP5.get("pinterest_keywords") or {}
    system = a1_config.format_prompt_template(
        a1_config.require_prompt_string(_PP5, "pinterest_keywords", "system", bundle="a5_pin_data"),
        bundle="a5_pin_data",
        article_language=ARTICLE_LANGUAGE,
    )
    response = openai.ChatCompletion.create(
        model=a1_config.get_openai_model(_S5, _K5),
        messages=[{"role": "system", "content": system}, {"role": "user", "content": f"{Recipe}"}],
        max_tokens=int(sec.get("max_tokens", 60))
    )
    return response.choices[0].message['content'].strip()

def generate_pinterest_description(title, keywords, api_key):
    """
    Using the following title and keywords, create a Pinterest-friendly description that is
    clear, keyword-rich, and written in an engaging, natural tone. Avoid hype or sales-driven phrases.
    Compose 2–3 sentences that blend the keywords smoothly and evoke seasonal or emotional appeal.
    """
    openai.api_key = api_key
    kw_text = keywords if keywords else ""
    sec = _PP5.get("pinterest_description") or {}
    system = a1_config.format_prompt_template(
        a1_config.require_prompt_string(_PP5, "pinterest_description", "system", bundle="a5_pin_data"),
        bundle="a5_pin_data",
        article_language=ARTICLE_LANGUAGE,
    )
    user = a1_config.format_prompt_template(
        a1_config.require_prompt_string(_PP5, "pinterest_description", "user", bundle="a5_pin_data"),
        bundle="a5_pin_data",
        article_language=ARTICLE_LANGUAGE,
        title=title,
        keywords=kw_text,
    )
    response = openai.ChatCompletion.create(
        model=a1_config.get_openai_model(_S5, _K5),
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=int(sec.get("max_tokens", 180))
    )
    description = response.choices[0].message['content'].strip()
    description = re.sub(r'#\w+', '', description).strip()
    return description

def generate_focus_keyphrase(Recipe, api_key):
    openai.api_key = api_key
    sec = _PP5.get("focus_keyphrase") or {}
    system = a1_config.format_prompt_template(
        a1_config.require_prompt_string(_PP5, "focus_keyphrase", "system", bundle="a5_pin_data"),
        bundle="a5_pin_data",
        article_language=ARTICLE_LANGUAGE,
    )
    response = openai.ChatCompletion.create(
        model=a1_config.get_openai_model(_S5, _K5),
        messages=[{"role": "system", "content": system}, {"role": "user", "content": f"{Recipe}"}],
        max_tokens=int(sec.get("max_tokens", 300))
    )
    return response.choices[0].message['content'].strip()

def generate_meta_description(Recipe, api_key):
    openai.api_key = api_key
    sec = _PP5.get("meta_description") or {}
    system = a1_config.format_prompt_template(
        a1_config.require_prompt_string(_PP5, "meta_description", "system", bundle="a5_pin_data"),
        bundle="a5_pin_data",
        article_language=ARTICLE_LANGUAGE,
    )
    response = openai.ChatCompletion.create(
        model=a1_config.get_openai_model(_S5, _K5),
        messages=[{"role": "system", "content": system}, {"role": "user", "content": f"{Recipe}"}],
        max_tokens=int(sec.get("max_tokens", 300))
    )
    return response.choices[0].message['content'].strip()

def generate_keyphrase_synonyms(focuskw, api_key):
    openai.api_key = api_key
    sec = _PP5.get("keyphrase_synonyms") or {}
    system = a1_config.format_prompt_template(
        a1_config.require_prompt_string(_PP5, "keyphrase_synonyms", "system", bundle="a5_pin_data"),
        bundle="a5_pin_data",
        article_language=ARTICLE_LANGUAGE,
    )
    user = a1_config.format_prompt_template(
        a1_config.require_prompt_string(_PP5, "keyphrase_synonyms", "user", bundle="a5_pin_data"),
        bundle="a5_pin_data",
        article_language=ARTICLE_LANGUAGE,
        focuskw=focuskw,
    )
    response = openai.ChatCompletion.create(
        model=a1_config.get_openai_model(_S5, _K5),
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=int(sec.get("max_tokens", 300))
    )
    synonyms = response.choices[0].message['content'].strip()
    return ', '.join([syn.strip() for syn in synonyms.split(',')])


def categorize_Recipe(Recipe, api_key):
    """
    Classify a recipe into one WordPress category (CATEGORY_ID_MAPPING key) from the title.
    Prompt text: config/prompts/a5_pin_data.json → categorize (editable on manage_sites).
    """
    openai.api_key = api_key
    category_names = list(_category_id_mapping().keys())
    catp = _PP5.get("categorize") or {}
    system_prompt, user_prompt = a1_config.format_categorize_prompt(
        Recipe, prompts=_PP5, settings=_S5
    )
    response = openai.ChatCompletion.create(
        model=a1_config.get_openai_model(_S5, _K5),
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        max_tokens=int(catp.get("max_tokens", 40)),
        temperature=float(catp.get("temperature", 0))
    )

    category = response.choices[0].message['content'].strip()
    return a1_config.resolve_category_name(category, category_names)




# ================================
# Main processing
# ================================
OUTPUT_COLS = [
    'recipe_title_pin',
    'pinterest_title',
    'pinterest_description',
    'pinterest_keywords',
    'rank_math_focus_keyword',
    'rank_math_description',
    'rank_math_pillar_content',
    'category',
    'categories',
]

def ensure_output_columns(df):
    for col in OUTPUT_COLS:
        if col not in df.columns:
            df[col] = ""

def process_Recipes(input_file_path, output_file_path, api_key):
    df = pd.read_excel(input_file_path)
    ensure_output_columns(df)
    base_mask = df['Recipe'].apply(lambda x: not is_empty(x))

    # 1) recipe_title_pin
    mask = base_mask & df['recipe_title_pin'].apply(is_empty)
    if mask.any():
        df.loc[mask, 'recipe_title_pin'] = df.loc[mask, 'Recipe'].apply(
            lambda r: clean_text(generate_recipe_title_pin(r, api_key))
        )

    # 2) pinterest_title
    mask = base_mask & df['pinterest_title'].apply(is_empty)
    if mask.any():
        df.loc[mask, 'pinterest_title'] = df.loc[mask, 'Recipe'].apply(
            lambda r: clean_text(generate_pinterest_title(r, api_key))
        )

    # 3) pinterest_keywords
    mask = base_mask & df['pinterest_keywords'].apply(is_empty)
    if mask.any():
        df.loc[mask, 'pinterest_keywords'] = df.loc[mask, 'Recipe'].apply(
            lambda r: clean_text(generate_pinterest_keywords(r, api_key))
        )

    # 4) pinterest_description (بدون CTA)
    mask = base_mask & df['pinterest_description'].apply(is_empty)
    if mask.any():
        title_missing_mask = mask & df['pinterest_title'].apply(is_empty)
        if title_missing_mask.any():
            df.loc[title_missing_mask, 'pinterest_title'] = df.loc[title_missing_mask, 'Recipe'].apply(
                lambda r: clean_text(generate_pinterest_title(r, api_key))
            )
        kw_missing_mask = mask & df['pinterest_keywords'].apply(is_empty)
        if kw_missing_mask.any():
            df.loc[kw_missing_mask, 'pinterest_keywords'] = df.loc[kw_missing_mask, 'Recipe'].apply(
                lambda r: clean_text(generate_pinterest_keywords(r, api_key))
            )

        df.loc[mask, 'pinterest_description'] = df.loc[mask].apply(
            lambda row: clean_text(
                generate_pinterest_description(
                    title=row.get('pinterest_title', ''),
                    keywords=row.get('pinterest_keywords', ''),
                    api_key=api_key
                )
            ),
            axis=1
        )

    # Rank Math SEO
    mask = base_mask & df['rank_math_focus_keyword'].apply(is_empty)
    if mask.any():
        df.loc[mask, 'rank_math_focus_keyword'] = df.loc[mask, 'Recipe'].apply(
            lambda r: generate_focus_keyphrase(r, api_key)
        )

    mask = base_mask & df['rank_math_description'].apply(is_empty)
    if mask.any():
        df.loc[mask, 'rank_math_description'] = df.loc[mask, 'Recipe'].apply(
            lambda r: clean_text(generate_meta_description(r, api_key))
        )

    # optional synonyms (ila bghiti)
    mask = base_mask & df['rank_math_pillar_content'].apply(is_empty)
    if mask.any():
        df.loc[mask, 'rank_math_pillar_content'] = "on"

    stale_cats = _sync_category_columns(df, base_mask, api_key)
    if stale_cats:
        print(f"♻️ Refreshed {stale_cats} row(s) with legacy/wrong WordPress category (e.g. dinner → mapping name + ID).")

    # تنظيف نهائي
    for col in ['recipe_title_pin', 'pinterest_title', 'pinterest_description',
                'pinterest_keywords', 'rank_math_description']:
        if col in df.columns:
            df[col] = df[col].apply(clean_text)

    cols = df.columns.tolist()
    if 'recipe_title_pin' in cols and 'pinterest_title' in cols:
        cols.insert(cols.index('pinterest_title'), cols.pop(cols.index('recipe_title_pin')))
        df = df[cols]

    df.to_excel(output_file_path, index=False)

# ================================
# Run
# ================================
if __name__ == "__main__":
    openai.api_key = OPENAI_API_KEY
    _px = a1_config.all_output_join("Recipes.xlsx")
    input_file_path = _px
    output_file_path = _px
    process_Recipes(input_file_path, output_file_path, OPENAI_API_KEY)
    print("✅ Done: filled empty cells; fixed legacy/wrong categories; left other filled rows untouched.")