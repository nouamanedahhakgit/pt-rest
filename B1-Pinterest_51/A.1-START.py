import os
import re
import json
import sys
import pandas as pd
import openai

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
import openai_chat_compat  # noqa: E402

openai_chat_compat.install()

# ================================
# Language control (set your output language here)
# Examples: "English", "Français", "Español", "العربية", "Deutsch", "Português", ...
# ================================
ARTICLE_LANGUAGE = "English"


def _set_openai_key(api_key: str):
    key = os.getenv("OPENAI_API_KEY", api_key or "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set.")
    openai.api_key = key
    return key

# ================================
# Helpers
# ================================
def clean_text(text, unwanted_chars):
    if not isinstance(text, str):
        return ""
    for char in unwanted_chars:
        text = text.replace(char, '')
    return text

# إزالة الإيموجي من العناوين
_EMOJI_RE = re.compile(
    "["                     
    "\U0001F600-\U0001F64F" # emoticons
    "\U0001F300-\U0001F5FF" # symbols & pictographs
    "\U0001F680-\U0001F6FF" # transport & map symbols
    "\U0001F1E0-\U0001F1FF" # flags
    "\U00002700-\U000027BF" # dingbats
    "\U0001F900-\U0001F9FF" # supplemental symbols
    "\U00002600-\U000026FF" # misc symbols
    "\U00002B00-\U00002BFF" # arrows etc.
    "]+",
    flags=re.UNICODE
)
def strip_emojis(s: str) -> str:
    if not isinstance(s, str):
        return ""
    return _EMOJI_RE.sub("", s).strip()

# كسور يونيكود
ASCII_TO_UNICODE_FRACTIONS = {
    "1/2": "½","1/4": "¼","3/4": "¾","1/3": "⅓","2/3": "⅔",
    "1/8": "⅛","3/8": "⅜","5/8": "⅝","7/8": "⅞",
}
def to_pretty_fractions(text: str) -> str:
    if not isinstance(text, str):
        return text
    # عوّض الأطول ثم الأقصر
    for k, v in sorted(ASCII_TO_UNICODE_FRACTIONS.items(), key=lambda x: -len(x[0])):
        text = re.sub(rf"(?<!\d){re.escape(k)}(?!\d)", v, text)
    return text

def postprocess_json(obj: dict) -> dict:
    """تنقية JSON النهائي: اسم بلا إيموجي، كسور يونيكود، أرقام كسلاسل، تنسيق كلمات مفتاحية."""
    if not isinstance(obj, dict):
        return {}

    # الاسم بلا إيموجي
    if "name" in obj and isinstance(obj["name"], str):
        obj["name"] = strip_emojis(obj["name"])

    # الحقول الرقمية كسلاسل
    for key in ["servings", "prep_time", "cook_time", "total_time", "calories"]:
        val = obj.get(key, "")
        obj[key] = "" if val is None else (str(val) if not isinstance(val, str) else val)

    # الكسور في المقادير/التعليمات/الملخص/الملاحظات
    if isinstance(obj.get("ingredients"), list):
        for ing in obj["ingredients"]:
            if isinstance(ing, dict):
                for subk in ["amount", "unit", "name"]:
                    if subk in ing and isinstance(ing[subk], str):
                        ing[subk] = to_pretty_fractions(ing[subk])

    if isinstance(obj.get("instructions"), list):
        obj["instructions"] = [
            to_pretty_fractions(x) if isinstance(x, str) else x
            for x in obj["instructions"]
        ]

    for k in ["summary", "notes", "course", "cuisine"]:
        if isinstance(obj.get(k), str):
            obj[k] = to_pretty_fractions(obj[k])

    # keywords لائحة
    if "keywords" in obj:
        if isinstance(obj["keywords"], str):
            parts = re.split(r"[,\|;]", obj["keywords"])
            obj["keywords"] = [p.strip() for p in parts if p.strip()]
        elif not isinstance(obj["keywords"], list):
            obj["keywords"] = []

    # لازم المفاتيح كلها تكون موجودة
    defaults = {
        "name": "", "summary": "", "servings": "", "prep_time": "", "cook_time": "",
        "total_time": "", "calories": "", "course": "", "cuisine": "",
        "keywords": [], "notes": "", "ingredients": [], "instructions": []
    }
    for k, v in defaults.items():
        if k not in obj:
            obj[k] = v

    return obj

# ================================
# 1) Rewrite Recipe (كما هو عندك)
# ================================
def generate_recipe(recipe_text, api_key):
    _set_openai_key(api_key)
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    f"You will ALWAYS write your output in {ARTICLE_LANGUAGE}.\n"
                    "As a creative chef, rewrite unique and delicious cooking recipes based on the given recipe.\n\n"
                    "# Steps\n"
                    "1. Interpret the Title\n"
                    "2. Select Ingredients\n"
                    "3. Develop Cooking Instructions\n"
                    "4. Consider Presentation\n"
                    "5. Adjust for Unique Flavors\n\n"
                    "# Output Format\n"
                    "Recipe Title\nIngredients: [...]\nInstructions: [...]\n"
                    "- Optional: Presentation Tips\n\n"
                    "# Notes\n"
                    "- No alcohol."
                )
            },
            {
                "role": "user",
                "content": (
                    f"Please rewrite the following recipe in {ARTICLE_LANGUAGE}, improving clarity and details "
                    f"but preserving the original structure:\n\n{recipe_text}"
                )
            }
        ],
        max_tokens=3000,
        temperature=0.6
    )
    raw_recipe = response.choices[0].message['content'].strip()
    return clean_text(raw_recipe, ['"', '*', '#', '<', '>'])

# ================================
# 2) JSON Maker (نفس المنطق ديال JSON اللي بغيت)
#    يدعم EN/DE/ES/PT-BR كنصّ إدخال للوصفة
# ================================
def call_openai_build_json(recipe_text: str, clean_title: str, api_key: str) -> dict:
    """
    يرجّع STRICT JSON بالمفاتيح:
      name, summary, servings, prep_time, cook_time, total_time, calories,
      course, cuisine, keywords, notes, ingredients[{amount,unit,name}], instructions[str]
    """
    _set_openai_key(api_key)

    system_msg = (
        "You are a culinary data formatter. "
        "From a given recipe text, output a STRICT JSON object with the required schema. "
        "Output JSON only (no markdown, no comments). "
        "Support recipe inputs in English, German, Spanish, or Brazilian Portuguese."
    )

    user_prompt = f"""
Recipe Title (clean, no emojis): {clean_title}

Recipe Text (may be EN/DE/ES/PT-BR):
\"\"\"{recipe_text}\"\"\"

Return ONLY a STRICT JSON object with exactly these keys:
{{
  "name": "string (clean, no emojis, short and clear)",
  "summary": "1-2 sentences summary of the dish",
  "servings": "digits only",
  "prep_time": "digits only minutes",
  "cook_time": "digits only minutes",
  "total_time": "digits only minutes",
  "calories": "digits only per serving",
  "course": "Main Course or Side Dish or Dessert or Breakfast or Snack or Appetizer or Soup or Salad or Drink",
  "cuisine": "e.g., Italian, American, German, Spanish, Brazilian, Mexican, Asian",
  "keywords": ["3-8 short keywords"],
  "notes": "short helpful note",
  "ingredients": [
    {{"amount": "string (use unicode fractions like ½ ¼ ¾ ⅓ ⅔ ⅛ ⅜ ⅝ ⅞ when needed)", "unit": "string or empty", "name": "ingredient name"}}
  ],
  "instructions": [
    "step-by-step instructions, concise sentences (6-10 steps)"
  ]
}}

Rules:
- Use unicode fractions (½ ¼ ¾ ⅓ ⅔ ⅛ ⅜ ⅝ ⅞), not ascii like 1/2.
- Keep times and numbers as plain digit strings.
- Fill ALL fields even if missing by inferring sensible values.
- Output must be VALID JSON ONLY (no code fences).
""".strip()

    resp = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.2,
        max_tokens=1200
    )
    content = resp.choices[0].message["content"].strip()

    # إزالة أي code fences محتملة
    if content.startswith("```"):
        content = content.strip("`")
        content = re.sub(r"^json", "", content, flags=re.I).strip()

    data = {}
    try:
        data = json.loads(content)
    except Exception:
        # محاولة استخراج JSON من النص
        m = re.search(r"\{.*\}\s*$", content, flags=re.S)
        if m:
            data = json.loads(m.group(0))
        else:
            data = {}

    return postprocess_json(data)

def ensure_columns_exist(df, cols):
    """Create empty string columns for any missing column names in cols."""
    for c in cols:
        if c not in df.columns:
            df[c] = ""
            print(f"[INFO] Column '{c}' not found in input; creating empty column.")

def process_all(input_recipe_path, output_file_path, api_key):
    # Load input
    df = pd.read_excel(input_recipe_path)

    # Sanity check
    if 'Recipe' not in df.columns:
        raise ValueError("Input file must contain a 'Recipe' column.")

    # ========== 1) Rewrite recipes (كما هو) ==========
    print("Rewriting recipes...")
    df['Recipe'] = df['Recipe'].apply(lambda r: generate_recipe(r, api_key))

    # ========== 2) Build Json Recipe (جديد) ==========
    # اختيار عنوان نظيف لكل سطر
    def _pick_title(row) -> str:
        for k in ["recipe_title_pin", "Title", "title", "name", "Recipe Title"]:
            if k in row and isinstance(row[k], str) and row[k].strip():
                return row[k].strip()
        return "Recipe"

    if "Json Recipe" not in df.columns:
        df["Json Recipe"] = ""

    print("Building Json Recipe...")
    for i, row in df.iterrows():
        recipe_text = str(row.get("Recipe", "") or "").strip()
        clean_title = strip_emojis(_pick_title(row))
        try:
            if recipe_text:
                j = call_openai_build_json(recipe_text, clean_title, api_key)
            else:
                # fallback بسيط
                j = {
                    "name": clean_title,
                    "summary": "",
                    "servings": "4",
                    "prep_time": "10",
                    "cook_time": "15",
                    "total_time": "25",
                    "calories": "400",
                    "course": "Main Course",
                    "cuisine": "",
                    "keywords": [],
                    "notes": "",
                    "ingredients": [],
                    "instructions": []
                }
        except Exception as e:
            print(f"[WARN] Row {i+1}: JSON build failed -> {e}")
            j = {
                "name": clean_title,
                "summary": "",
                "servings": "4",
                "prep_time": "10",
                "cook_time": "15",
                "total_time": "25",
                "calories": "400",
                "course": "Main Course",
                "cuisine": "",
                "keywords": [],
                "notes": "",
                "ingredients": [],
                "instructions": []
            }
        df.at[i, "Json Recipe"] = json.dumps(j, ensure_ascii=False, indent=2)

    # ===== Columns we want to pass-through as-is =====
    original_image_cols = ['main_image', 'image_1', 'image_2', 'image_3', 'image_4', 'statu', 'error']
    ingredient_image_cols = ['main_image_ingredients', 'image_ing_1', 'image_ing_2', 'image_ing_3', 'image_ing_4', 'statu_ing', 'error_ing']
    meta_cols = ['Title', 'Prompt']  # keep as-is if present

    # Make sure all requested columns exist (create empty if missing)
    ensure_output = meta_cols + original_image_cols + ingredient_image_cols + ['Recipe', 'Json Recipe']
    ensure_columns_exist(df, ensure_output)

    # Order/output (أضفنا Json Recipe بعد Recipe)
    columns_to_keep = meta_cols + ['Recipe', 'Json Recipe'] + original_image_cols + ingredient_image_cols

    # Only keep those (and in this order)
    df_out = df[columns_to_keep]

    # Ensure output dir exists
    out_dir = os.path.dirname(output_file_path)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir)
        print(f"Created directory: {out_dir}")
    else:
        print(f"Directory already exists: {out_dir}")

    # Save
    df_out.to_excel(output_file_path, index=False)
    print(f"[OK] Rewritten recipes + JSON saved to {output_file_path}")
    print(f"[INFO] Rows processed: {len(df_out)}")

if __name__ == "__main__":
    api_key = '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'

    input_file_path = '../ALL/A1-Pinterest_01-out/images.xlsx'
    output_file_path = '../ALL/B1-Pinterest_51-out/images.xlsx'

    process_all(input_file_path, output_file_path, api_key)
