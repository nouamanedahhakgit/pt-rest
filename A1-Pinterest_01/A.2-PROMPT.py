import pandas as pd
import re
import os
import sys
import unicodedata
import openai

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
import openai_chat_compat  # noqa: E402

openai_chat_compat.install()

import a1_config  # noqa: E402

_KEYS = a1_config.load_keys()
_SETTINGS = a1_config.load_settings()
a1_config.set_openai_key_from_keys(_KEYS)
PP = a1_config.load_prompts("a2_prompt")
MODEL = _SETTINGS.get("a2_prompt_model") or a1_config.get_openai_model(_SETTINGS, _KEYS)

def _chat(messages, max_tokens=None, temperature=None):
    if max_tokens is None:
        max_tokens = int(PP.get("chat_max_tokens_default", 600))
    if temperature is None:
        temperature = float(PP.get("chat_temperature_default", 0.6))
    return openai.ChatCompletion.create(
        model=MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

# ================================
# Helpers
# ================================
DISCORD_MAX_SAFE = 1800  # هامش تحت 2000
SAFE_MAX_TOKENS = 400

def _normalize_unicode(txt: str) -> str:
    if not isinstance(txt, str):
        return txt
    # توحيد الحروف والاقتباسات والشرطات الطويلة + إزالة محارف غير مرئية
    txt = unicodedata.normalize("NFKC", txt)
    txt = txt.replace("\u200b", "").replace("\u200c", "").replace("\u2060", "")
    return txt

def clean_text(text):
    if not isinstance(text, str):
        return text
    text = _normalize_unicode(text)
    # حذف محارف قد تسبب فورمات في المنصات
    for c in ['"', '*', '#']:
        text = text.replace(c, '')
    return text

def strip_prompt_prefix(text: str) -> str:
    if not isinstance(text, str):
        return text
    t = text.strip()
    # إزالة code fences والبادئات الشائعة
    t = re.sub(r"^\s*```(?:\w+)?\s*|\s*```\s*$", "", t)
    t = re.sub(r"^\s*(/|\\)?\s*imagine\s*prompt\s*[:\-]*\s*", "", t, flags=re.I)
    t = re.sub(r"^\s*prompt\s*[:\-]*\s*", "", t, flags=re.I)
    t = re.sub(r"^\s*mj\s*v?\d+\s*[:\-]*\s*", "", t, flags=re.I)
    t = re.sub(r"^\s*--?v\s*\d+(?:\.\d+)?\s*", "", t, flags=re.I)
    t = re.sub(r"^\s*[/\\#>*\-:|.,;~]+\s*", "", t)
    return t.strip().strip('"\''"“”‘’").strip()

def ensure_v6_1_only(prompt: str) -> str:
    """Keep only --v 6.1 and strip other flags like --ar, --stylize, etc."""
    if not isinstance(prompt, str):
        return prompt
    prompt = re.sub(r"--?ar\s*\d+\s*:\s*\d+\b", "", prompt, flags=re.I)
    prompt = re.sub(r"--?chaos\s*\d+\b", "", prompt, flags=re.I)
    prompt = re.sub(r"--?stylize?\s*\d+\b", "", prompt, flags=re.I)
    prompt = re.sub(r"--?sref\s+\S+", "", prompt, flags=re.I)
    prompt = re.sub(r"--?seed\s*\d+\b", "", prompt, flags=re.I)
    prompt = re.sub(r"(?:^|\s)--?v\s*\d+(?:\.\d+)?\b", " ", prompt, flags=re.I).strip()
    prompt = re.sub(r"\s{2,}", " ", prompt).strip(" ,")
    return (prompt + " --v 6.1").strip()

def sanitize_for_discord(prompt: str) -> str:
    """تنظيف المنشنات/الروابط/الفورمات والحد من الطول."""
    if not isinstance(prompt, str):
        return prompt
    p = _normalize_unicode(prompt)
    # حيد الروابط
    p = re.sub(r"https?://\S+", "", p)
    # فكّ المِنشنات
    p = p.replace("@", "(at)")
    p = re.sub(r"<@!?&?#\d+>", "", p)    # <@123>, <@!123>, <#123>, <@&123>
    # حذف ماركداون/سبويلر/كود
    p = p.replace("||", "")
    p = p.replace("```", "")
    p = p.replace("`", "")
    p = p.replace("*", "")
    p = p.replace("_", "")
    p = p.replace("~", "")
    # بداية الأسطر بعلامة quote
    p = re.sub(r"(?m)^\s*>\s*", "", p)
    # ما يبداش بـ / باش ما يتحسبش أمر
    p = p.lstrip("/\\>.:|- ")
    # دمج مسافات
    p = re.sub(r"\s{2,}", " ", p).strip()
    # حد الطول
    if len(p) > DISCORD_MAX_SAFE:
        p = p[:DISCORD_MAX_SAFE].rstrip()
    return p

def dedupe_exact_csv(csv_text: str, max_items: int = 25) -> str:
    """Remove exact duplicates only (case-insensitive) and cap list length."""
    items = [x.strip() for x in re.split(r",|;|\n", csv_text or "") if x.strip()]
    seen = set()
    out = []
    for it in items:
        key = it.lower()
        if key not in seen:
            seen.add(key)
            out.append(it)
        if len(out) >= max_items:
            break
    return ", ".join(out)

def _collapse_commas(txt: str) -> str:
    """تنظيف الفواصل المزدوجة والمسافات الزائدة."""
    if not isinstance(txt, str):
        return txt
    t = re.sub(r"\s*,\s*", ", ", txt)   # normalize comma spacing
    t = re.sub(r",\s*,+", ", ", t)      # collapse double commas
    t = re.sub(r"\s{2,}", " ", t).strip(" ,")
    return t

# ================================
# Compliance Layer — keep prompts policy-safe (conservative)
# ================================
_SENSITIVE_PATTERNS = list(PP.get("sensitive_patterns") or [])

def _soft_replacements_list():
    out = []
    for item in PP.get("soft_replacements") or []:
        if isinstance(item, dict) and "pattern" in item and "replace" in item:
            out.append((item["pattern"], item["replace"]))
    return out


def _allowed_food_style_fallback() -> str:
    return a1_config.require_prompt_string(PP, "allowed_food_style_fallback", bundle="a2_prompt")


def _food_only_guard() -> str:
    return a1_config.require_prompt_string(PP, "food_only_guard", bundle="a2_prompt")

def filter_sensitive(text: str) -> str:
    """إزالة/استبدال كلمات قد تسبب رفض (محافظ)."""
    t = " " + (text or "") + " "
    for pat in _SENSITIVE_PATTERNS:
        t = re.sub(pat, " ", t, flags=re.I)
    for pat, repl in _soft_replacements_list():
        t = re.sub(pat, repl, t, flags=re.I)
    # طرد يونيكود مشاغب ودمج المسافات
    t = re.sub(r"[\u202a-\u202e\u2000-\u200f\u2066-\u2069]", " ", t)
    t = re.sub(r"\s{2,}", " ", t).strip()
    return t

def enforce_food_only(text: str) -> str:
    """نضمن أن المشهد ‘أكلة فقط’ بلا أشخاص/نص/لوغوهات."""
    base = (text or "").strip().rstrip(",.")
    base = filter_sensitive(base)
    base = _collapse_commas(base)
    if len(base) < 20:
        base = _allowed_food_style_fallback()
    guard = _food_only_guard()
    out = f"{base}, {guard}"
    return _collapse_commas(out)

def _finalize_prompt(txt: str) -> str:
    """الترتيب الصحيح: تنظيف → حراسة → تنسيق → إضافة --v 6.1 → Sanitize."""
    p = strip_prompt_prefix(txt or "")
    p = clean_text(p)
    p = enforce_food_only(p)   # كل المحتوى أولاً
    p = _collapse_commas(p)
    p = ensure_v6_1_only(p)    # ثم نضيف --v 6.1 في الأخير
    p = sanitize_for_discord(p)
    return p

# ================================
# Prompt (final plated dish) — ultra close-up, white bowl/plate
# ================================
def generate_recipe(recipe_text: str) -> str:
    sys_msg = a1_config.require_prompt_string(PP, "main_dish_system", bundle="a2_prompt")
    u_pref = a1_config.require_prompt_string(PP, "main_dish_user_prefix", bundle="a2_prompt")
    resp = _chat(
        [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": f"{u_pref}{recipe_text}"},
        ],
        max_tokens=int(PP.get("safe_max_tokens", SAFE_MAX_TOKENS)),
    )
    raw = resp.choices[0].message["content"].strip()
    return _finalize_prompt(raw)

# ================================
# Prompt Image Ingredients — NOT 100% white background
# ================================
def _extract_ingredient_list(recipe_text: str) -> str:
    """Get a UNIQUE CSV of ingredient names (model asked to avoid duplicates)."""
    resp = _chat(
        [
            {"role": "system", "content": a1_config.require_prompt_string(PP, "ingredient_extract_system", bundle="a2_prompt")},
            {"role": "user", "content": recipe_text},
        ],
        max_tokens=int(PP.get("ingredient_extract_max_tokens", 220)),
    )

    ing = resp.choices[0].message["content"].strip()
    ing = strip_prompt_prefix(ing)
    # normalize CSV formatting فقط
    ing = re.sub(r"[\n\r]+", ", ", ing)
    ing = re.sub(r"\s*,\s*", ", ", ing)
    ing = re.sub(r"\s{2,}", " ", ing).strip(" ,")
    # no duplicates + cap
    ing = dedupe_exact_csv(ing, max_items=25)
    return ing

def _compose_ingredients_prompt_from_list(ingredients_csv: str) -> str:
    tpl = a1_config.require_prompt_string(PP, "ingredient_scene_template", bundle="a2_prompt")
    return a1_config.format_prompt_template(
        tpl, bundle="a2_prompt", ingredients_csv=ingredients_csv
    )

def generate_ingredients_prompt(recipe_text: str) -> str:
    ing_csv = _extract_ingredient_list(recipe_text)
    final_prompt = _compose_ingredients_prompt_from_list(ing_csv)
    # نفس الترتيب: كلشي قبل --v 6.1
    return _finalize_prompt(final_prompt)

# ================================
# Excel processing — progressive save (with dtype fix)
# ================================
def process_recipes(input_file_path, output_file_path):
    df = a1_config.read_excel_with_retry(input_file_path)

    # تأكد من الأعمدة وأنواعها
    for col in ["Prompt", "Prompt Image Ingredients"]:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].astype("object")

    if "Recipe" in df.columns:
        df["Recipe"] = df["Recipe"].astype("object")

    for i, row in df.iterrows():
        recipe = str(row.get("Recipe", "") or "")

        # Generate Prompt (final dish) if missing
        current_prompt = row.get("Prompt", "")
        if (pd.isna(current_prompt) or not str(current_prompt).strip()):
            try:
                gen = generate_recipe(recipe)
                df.at[i, "Prompt"] = str(gen or "")
            except Exception:
                # ما تعرقلش بقية الصفوف
                pass

        # Generate Prompt Image Ingredients if missing
        current_ing = row.get("Prompt Image Ingredients", "")
        if (pd.isna(current_ing) or not str(current_ing).strip()):
            try:
                gen_ing = generate_ingredients_prompt(recipe)
                df.at[i, "Prompt Image Ingredients"] = str(gen_ing or "")
            except Exception:
                pass

        # ✅ Progressive write after EACH row
        a1_config.to_excel_with_retry(df, output_file_path, index=False)

# ================================
# Run
# ================================
if __name__ == "__main__":
    all_out = a1_config.all_output_join("Recipes.xlsx")
    process_recipes(str(all_out), str(all_out))
