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
CATEGORY_ID_MAPPING = dict(_S5.get("category_id_mapping") or {
    "drinks": 1,
    "dessert": 7,
    "appetizers": 5,
    "dinner": 4
})

# ================================
# Helpers
# ================================
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
    system = (sec.get("system") or "").format(article_language=ARTICLE_LANGUAGE)
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
    system = (sec.get("system") or "").format(article_language=ARTICLE_LANGUAGE)
    user = (sec.get("user") or "").format(article_language=ARTICLE_LANGUAGE, recipe=Recipe)
    response = openai.ChatCompletion.create(
        model=a1_config.get_openai_model(_S5, _K5),
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=int(sec.get("max_tokens", 120))
    )
    return response.choices[0].message['content'].strip()

def generate_pinterest_keywords(Recipe, api_key):
    openai.api_key = api_key
    sec = _PP5.get("pinterest_keywords") or {}
    system = (sec.get("system") or "").format(article_language=ARTICLE_LANGUAGE)
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
    system = (sec.get("system") or "").format(article_language=ARTICLE_LANGUAGE)
    user = (sec.get("user") or "").format(
        article_language=ARTICLE_LANGUAGE, title=title, keywords=kw_text
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
    system = (sec.get("system") or "").format(article_language=ARTICLE_LANGUAGE)
    response = openai.ChatCompletion.create(
        model=a1_config.get_openai_model(_S5, _K5),
        messages=[{"role": "system", "content": system}, {"role": "user", "content": f"{Recipe}"}],
        max_tokens=int(sec.get("max_tokens", 300))
    )
    return response.choices[0].message['content'].strip()

def generate_meta_description(Recipe, api_key):
    openai.api_key = api_key
    sec = _PP5.get("meta_description") or {}
    system = (sec.get("system") or "").format(article_language=ARTICLE_LANGUAGE)
    response = openai.ChatCompletion.create(
        model=a1_config.get_openai_model(_S5, _K5),
        messages=[{"role": "system", "content": system}, {"role": "user", "content": f"{Recipe}"}],
        max_tokens=int(sec.get("max_tokens", 300))
    )
    return response.choices[0].message['content'].strip()

def generate_keyphrase_synonyms(focuskw, api_key):
    openai.api_key = api_key
    sec = _PP5.get("keyphrase_synonyms") or {}
    system = (sec.get("system") or "").format(article_language=ARTICLE_LANGUAGE)
    user = (sec.get("user") or "").format(focuskw=focuskw)
    response = openai.ChatCompletion.create(
        model=a1_config.get_openai_model(_S5, _K5),
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=int(sec.get("max_tokens", 300))
    )
    synonyms = response.choices[0].message['content'].strip()
    return ', '.join([syn.strip() for syn in synonyms.split(',')])


def categorize_Recipe(Recipe, api_key):
    """
    Classify a recipe into one of four categories based ONLY on the title.
    Semantic-aware, uses culinary context, does NOT rely only on keywords.
    """
    openai.api_key = api_key
    categories = ["drinks", "dessert", "appetizers", "dinner"]
    catp = _PP5.get("categorize") or {}
    system_prompt = (catp.get("system") or "").strip()
    user_prompt = (catp.get("user") or "Recipe title: {recipe}").format(recipe=Recipe)
    response = openai.ChatCompletion.create(
        model=a1_config.get_openai_model(_S5, _K5),
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        max_tokens=int(catp.get("max_tokens", 5)),
        temperature=float(catp.get("temperature", 0))
    )

    category = response.choices[0].message['content'].strip().lower()

    # =============================
    # Safe fallback
    # =============================
    if category in categories:
        return category
    if "drink" in category or "smoothie" in category:
        return "drinks"
    if "cake" in category or "sweet" in category:
        return "dessert"
    if "snack" in category or "starter" in category:
        return "appetizers"
    return "dinner"




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

    mask = base_mask & df['category'].apply(is_empty)
    if mask.any():
        df.loc[mask, 'category'] = df.loc[mask, 'Recipe'].apply(
            lambda r: categorize_Recipe(r, api_key)
        )

    mask = base_mask & df['categories'].apply(is_empty)
    if mask.any():
        df.loc[mask, 'categories'] = df.loc[mask, 'category'].map(CATEGORY_ID_MAPPING)

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
    print("✅ Done: processed only empty rows and left filled rows untouched.")