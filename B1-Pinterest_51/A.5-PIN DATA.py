import os
import sys
import pandas as pd
import openai
import re
import textwrap

# ================================
# Config
# ================================
OPENAI_API_KEY = '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'  # ← بدّلها إذا بغيت

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
import openai_chat_compat  # noqa: E402

openai_chat_compat.install()

# اختر اللغة اللي بغيتي تخرج بها النتائج (مثال: "English" / "Français" / "Español" / "العربية" ...)
ARTICLE_LANGUAGE = "English"

CATEGORY_ID_MAPPING = {
    "drinks": 1,
    "dessert": 7,
    "appetizers": 5,
    "dinner": 4
}

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
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    f"Write a short, catchy, and attractive recipe title in {ARTICLE_LANGUAGE}. "
                    "Output ONLY the title text with no quotes, emojis, hashtags, numbering, or extra lines. "
                    "Aim for a compact length (ideally 4–7 words), natural and appetizing. "
                    "No clickbait, no all-caps, keep proper capitalization."
                )
            },
            {"role": "user", "content": Recipe}
        ],
        # ما كاين حتى حدّ أقصى صارم؛ غير خليه كافي باش ما يقطعش
        max_tokens=80,
        temperature=0.7
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
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    f"You create Pinterest Pin titles in {ARTICLE_LANGUAGE}. "
                    "Output ONLY the title text with no quotes, emojis, hashtags, or extra lines. "
                    "Keep it under 100 characters, clear, engaging, and naturally include common Pinterest search keywords. "
                    "Avoid hype, clickbait, or salesy wording."
                )
            },
            {
                "role": "user",
                "content": (
                    f'Create a clear and engaging Pinterest Pin title for this Recipe (write in {ARTICLE_LANGUAGE}):\n\n{Recipe}'
                )
            }
        ],
        max_tokens=120
    )
    return response.choices[0].message['content'].strip()

def generate_pinterest_keywords(Recipe, api_key):
    openai.api_key = api_key
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    f"Analyze the provided Recipe and extract 6 relevant keywords for Pinterest in {ARTICLE_LANGUAGE}. "
                    "Provide a comma-separated list of keywords without any additional text, emojis, or hashtags."
                )
            },
            {"role": "user", "content": f"{Recipe}"}
        ],
        max_tokens=60
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
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    f"You write Pinterest-friendly descriptions in {ARTICLE_LANGUAGE}. "
                    "Output only 2–3 sentences. "
                    "Tone: clear, natural, engaging; keyword-rich without stuffing. "
                    "Avoid hype/sales-driven phrases, hashtags, emojis, and special formatting."
                )
            },
            {
                "role": "user",
                "content": (
                    "Using the following title and keywords, create a Pinterest-friendly description. "
                    f"Write in {ARTICLE_LANGUAGE}.\n\n"
                    f"• Title: {title}\n"
                    f"• Keywords: {kw_text}\n\n"
                    "Compose 2–3 sentences that blend the keywords smoothly and evoke seasonal or emotional appeal."
                )
            }
        ],
        max_tokens=180
    )
    description = response.choices[0].message['content'].strip()
    description = re.sub(r'#\w+', '', description).strip()
    return description

def generate_focus_keyphrase(Recipe, api_key):
    openai.api_key = api_key
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    f"Analyze the provided Recipe and generate the most repeated focus keyphrase in {ARTICLE_LANGUAGE} "
                    "that best represents the main topic. The keyphrase should be concise, relevant, and SEO-optimized. "
                    "Give me the result directly without any introductions or explanations."
                )
            },
            {"role": "user", "content": f"{Recipe}"}
        ],
        max_tokens=300
    )
    return response.choices[0].message['content'].strip()

def generate_meta_description(Recipe, api_key):
    openai.api_key = api_key
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    f"Create an SEO meta description in {ARTICLE_LANGUAGE}. "
                    "Target ~120 characters (max 140). "
                    "Include the focus keyphrase naturally. "
                    "Give me the result directly without any introductions or explanations."
                )
            },
            {"role": "user", "content": f"{Recipe}"}
        ],
        max_tokens=300
    )
    return response.choices[0].message['content'].strip()

def generate_keyphrase_synonyms(focuskw, api_key):
    openai.api_key = api_key
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    f"Provide synonyms for the given focus keyphrase in {ARTICLE_LANGUAGE} to enhance SEO. "
                    "Give me the result directly without any introductions or explanations, "
                    "don't use bullet points, don't use numbers."
                )
            },
            {"role": "user", "content": f"3 Synonyms for the focus keyphrase: {focuskw}"}
        ],
        max_tokens=300
    )
    synonyms = response.choices[0].message['content'].strip()
    return ', '.join([syn.strip() for syn in synonyms.split(',')])


def categorize_Recipe(Recipe, api_key):
    openai.api_key = api_key
    categories = ["drinks", "dessert", "appetizers", "dinner"]

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a professional food classification assistant.\n"
                    "Your ONLY job is to classify recipes into EXACTLY ONE of these categories:\n\n"
                    "• drinks → beverages like smoothies, juices, iced drinks, lattes, teas, coffees, cocktails, mocktails, milkshakes.\n"
                    "• dessert → sweet treats like cakes, cookies, brownies, puddings, muffins, ice cream, pies, tarts.\n"
                    "• appetizers → snacks, starters, finger food, dips, simple sides that are NOT main meals.\n"
                    "• dinner → savory main dishes like pasta, curry, stew, casseroles, one-pot meals, soups eaten as a main dish.\n\n"
                    "IMPORTANT RULES:\n"
                    "1. If the recipe is mainly a liquid and consumed as a beverage → classify as drinks.\n"
                    "2. If the recipe is sweet and eaten as a treat → classify as dessert.\n"
                    "3. If the recipe is a small bite, snack, dip, or starter → classify as appetizers.\n"
                    "4. If it's a savory cooked main dish → classify as dinner.\n"
                    "5. If unclear, choose the MOST LIKELY category.\n\n"
                    "OUTPUT FORMAT:\n"
                    "Respond with ONLY ONE WORD ONLY from this list:\n"
                    "drinks, dessert, appetizers, dinner\n"
                    "→ No explanation, no punctuation, no extra text."
                )
            },
            {
                "role": "user",
                "content": (
                    "Classify the following recipe:\n\n"
                    f"{Recipe}\n\n"
                    "Respond with ONE WORD ONLY: drinks, dessert, appetizers, dinner."
                )
            }
        ],
        max_tokens=5,
        temperature=0
    )

    # ناخدو النتيجة
    category = response.choices[0].message['content'].strip().lower()

    # نتأكد أنها واحدة من لائحة المسموح به
    if category in categories:
        return category

    # fallback بسيط
    if "drink" in category or "beverage" in category:
        return "drinks"
    if "sweet" in category:
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
    '_yoast_wpseo_focuskw',
    '_yoast_wpseo_metadesc',
    '_yoast_wpseo_keywordsynonyms',
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

    # باقي الأعمدة (Yoast SEO وغيرها)
    mask = base_mask & df['_yoast_wpseo_focuskw'].apply(is_empty)
    if mask.any():
        df.loc[mask, '_yoast_wpseo_focuskw'] = df.loc[mask, 'Recipe'].apply(
            lambda r: generate_focus_keyphrase(r, api_key)
        )

    mask = base_mask & df['_yoast_wpseo_metadesc'].apply(is_empty)
    if mask.any():
        df.loc[mask, '_yoast_wpseo_metadesc'] = df.loc[mask, 'Recipe'].apply(
            lambda r: clean_text(generate_meta_description(r, api_key))
        )

    mask = base_mask & df['_yoast_wpseo_keywordsynonyms'].apply(is_empty)
    if mask.any():
        fk_mask = base_mask & df['_yoast_wpseo_focuskw'].apply(is_empty)
        if fk_mask.any():
            df.loc[fk_mask, '_yoast_wpseo_focuskw'] = df.loc[fk_mask, 'Recipe'].apply(
                lambda r: generate_focus_keyphrase(r, api_key)
            )
        mask = base_mask & df['_yoast_wpseo_keywordsynonyms'].apply(is_empty)
        df.loc[mask, '_yoast_wpseo_keywordsynonyms'] = df.loc[mask, '_yoast_wpseo_focuskw'].apply(
            lambda kw: clean_text(generate_keyphrase_synonyms(kw, api_key)) if not is_empty(kw) else ""
        )

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
                'pinterest_keywords', '_yoast_wpseo_metadesc']:
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
    input_file_path = '../ALL/B1-Pinterest_51-out/images.xlsx'
    output_file_path = '../ALL/B1-Pinterest_51-out/images.xlsx'
    process_Recipes(input_file_path, output_file_path, OPENAI_API_KEY)
    print("✅ Done: processed only empty rows and left filled rows untouched.")