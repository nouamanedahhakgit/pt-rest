#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import importlib.util
import os
import re
import json
import sys
import pandas as pd
import openai

# Project root (PINTEREST) — use for ALL/... paths; do not rely on cwd for "../ALL/...".
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
import openai_chat_compat  # noqa: E402

openai_chat_compat.install()

import a1_config  # noqa: E402

_KEYS = a1_config.load_keys()
_SETTINGS = a1_config.load_settings()
a1_config.set_openai_key_from_keys(_KEYS)
MODEL = a1_config.get_openai_model(_SETTINGS, _KEYS)
_PROMPTS_JSON = a1_config.load_prompts("a2_json")

# ================================
# Helpers
# ================================
def clean_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    for c in ['"', '*', '#', '<', '>']:
        text = text.replace(c, "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

# إزالة الإيموجي من العنوان داخل JSON
_EMOJI_RE = re.compile(
    "["                     # open class
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
    for k, v in sorted(ASCII_TO_UNICODE_FRACTIONS.items(), key=lambda x: -len(x[0])):
        text = re.sub(rf"(?<!\d){re.escape(k)}(?!\d)", v, text)
    return text

def extract_calories_context(recipe_text: str) -> str:
    """
    كيلقط context ديال calories من سطر Calories:
    مثال: "~150 per cookie" => "per cookie"
    """
    if not recipe_text:
        return ""
    m = re.search(r"(?im)^\s*calories\s*:\s*(.+)\s*$", recipe_text)
    if not m:
        return ""
    line = m.group(1).strip().lower()

    # لقّط "per X"
    m2 = re.search(r"\bper\s+([a-zA-Z\- ]+)\b", line)
    if m2:
        unit = m2.group(1).strip()
        unit = re.sub(r"[^a-zA-Z\- ]", "", unit).strip()
        unit = re.sub(r"\s+", " ", unit)
        # نحدّو الطول باش ما يتخربقش
        unit = unit[:40].strip()
        return f"per {unit}"
    return ""

def postprocess_json(obj: dict) -> dict:
    """
    تنقية JSON:
    - name بلا emojis
    - times/calories/servings digits only (strings)
    - fractions unicode
    - ensure required keys exist
    """
    if not isinstance(obj, dict):
        return {}

    # name
    if isinstance(obj.get("name"), str):
        obj["name"] = strip_emojis(obj["name"])

    # digits-only fields as strings
    for key in ["servings", "prep_time", "cook_time", "total_time", "calories"]:
        val = obj.get(key, "")
        if val is None:
            obj[key] = ""
            continue
        if not isinstance(val, str):
            val = str(val)
        # خذ غير الأرقام (مثلا "~150 per cookie" => 150)
        m = re.search(r"(\d+)", val)
        obj[key] = m.group(1) if m else ""

    # ingredients fractions
    if isinstance(obj.get("ingredients"), list):
        for ing in obj["ingredients"]:
            if isinstance(ing, dict):
                for subk in ["amount", "unit", "name"]:
                    if subk in ing and isinstance(ing[subk], str):
                        ing[subk] = to_pretty_fractions(ing[subk])

    # instructions fractions
    if isinstance(obj.get("instructions"), list):
        obj["instructions"] = [
            to_pretty_fractions(x) if isinstance(x, str) else x
            for x in obj["instructions"]
        ]

    # text fields
    for k in ["summary", "notes", "course", "cuisine"]:
        if isinstance(obj.get(k), str):
            obj[k] = to_pretty_fractions(obj[k])

    # keywords normalize
    if "keywords" in obj:
        if isinstance(obj["keywords"], str):
            parts = re.split(r"[,\|;]", obj["keywords"])
            obj["keywords"] = [p.strip() for p in parts if p.strip()]
        elif not isinstance(obj["keywords"], list):
            obj["keywords"] = []

    # Ensure required keys exist
    required_keys = [
        "name","summary","servings","prep_time","cook_time","total_time","calories",
        "course","cuisine","keywords","notes","ingredients","instructions"
    ]
    for k in required_keys:
        if k not in obj:
            obj[k] = [] if k in ["keywords","ingredients","instructions"] else ""

    # Ensure lists types
    for k in ["keywords", "ingredients", "instructions"]:
        if not isinstance(obj.get(k), list):
            obj[k] = []

    return obj

def safe_json_loads(content: str) -> dict:
    """يحاول يقرا JSON حتى إلا كان مكتوب مع نص زايد."""
    if not content:
        return {}
    content = content.strip()

    # remove code fences if exist
    if content.startswith("```"):
        content = content.strip("`")
        content = re.sub(r"^json", "", content, flags=re.I).strip()

    try:
        data = json.loads(content)
        return data if isinstance(data, dict) else {}
    except Exception:
        m = re.search(r"\{.*\}\s*$", content, flags=re.S)
        if m:
            try:
                data = json.loads(m.group(0))
                return data if isinstance(data, dict) else {}
            except Exception:
                return {}
        return {}

# ================================
# OpenAI: Build JSON from Recipe text
# ================================
def call_openai_build_json(recipe_text: str, clean_title: str) -> dict:
    pj = _PROMPTS_JSON
    system_msg = pj.get("system", "")
    user_prompt = (
        pj.get("preamble", "")
        + str(clean_title)
        + pj.get("recipe_wrap_prefix", "")
        + str(recipe_text)
        + pj.get("recipe_wrap_suffix", "")
        + pj.get("json_schema_block", "")
    )
    max_tok = int(_SETTINGS.get("a2_json_max_tokens", 1200))
    temp = float(_SETTINGS.get("a2_json_temperature", 0.2))

    resp = openai.ChatCompletion.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temp,
        max_tokens=max_tok
    )

    content = resp.choices[0].message["content"]
    data = safe_json_loads(content)
    data = postprocess_json(data)

    # ✅ حافظ على context ديال calories فـ notes
    ctx = extract_calories_context(recipe_text)  # مثلا "per cookie"
    if ctx:
        existing_notes = (data.get("notes") or "").strip()
        extra = f"Calories are {ctx}."
        data["notes"] = (existing_notes + (" " if existing_notes else "") + extra).strip()

    return data

# ================================
# Script 2: Read same file + write Json Recipe in same file
# ================================
def add_json_recipe_inplace(recipes_file_path: str, overwrite_existing: bool = False):
    df = a1_config.read_excel_with_retry(recipes_file_path)

    if "Title" not in df.columns:
        raise RuntimeError("Column 'Title' is required.")
    if "Recipe" not in df.columns:
        raise RuntimeError("Column 'Recipe' is required (run Script 1 first).")

    if "Json Recipe" not in df.columns:
        df["Json Recipe"] = ""

    for i, row in df.iterrows():
        title = str(row.get("Title", "") or "").strip()
        recipe_text = str(row.get("Recipe", "") or "").strip()

        if not recipe_text:
            df.at[i, "Json Recipe"] = ""
            print(f"[WARN] Row {i+1}: empty Recipe")
            continue

        already = str(row.get("Json Recipe", "") or "").strip()
        if already and not overwrite_existing:
            print(f"[SKIP] Row {i+1}: Json Recipe already exists")
            continue

        clean_title = strip_emojis(title)

        try:
            data = call_openai_build_json(recipe_text, clean_title)
            df.at[i, "Json Recipe"] = json.dumps(data, ensure_ascii=False, indent=2)
            print(f"[OK] Row {i+1}: JSON done")
        except Exception as e:
            print(f"[WARN] Row {i+1}: JSON failed -> {e}")
            df.at[i, "Json Recipe"] = ""

    # حفظ فنفس الملف
    a1_config.to_excel_with_retry(df, recipes_file_path, index=False)
    print(f"[DONE] Saved (same file): {recipes_file_path}")
    print(f"[INFO] Rows: {len(df)}")

def _recipes_workbook_default() -> str:
    return os.path.join(_REPO_ROOT, "ALL", "A1-Pinterest_01-out", "Recipes.xlsx")


def _ensure_recipes_workbook() -> str:
    """
    If Recipes.xlsx is missing, build it from STARTS/START1.xlsx using the same
    pipeline as A.1-START.py (title → full recipe text).
    """
    path = _recipes_workbook_default()
    if os.path.isfile(path):
        return path

    start1 = os.path.join(_REPO_ROOT, "STARTS", "START1.xlsx")
    if not os.path.isfile(start1):
        print(
            f"[ERROR] Missing both:\n"
            f"  {path}\n"
            f"  and input:\n  {start1}\n"
            "  Add STARTS/START1.xlsx (with a Title column) or run A.1-START.py to create Recipes.xlsx.",
            flush=True,
        )
        sys.exit(1)

    print(
        f"[INFO] Recipes.xlsx not found. Building it from {start1} (same as A.1-START) ...",
        flush=True,
    )
    a1_path = os.path.join(os.path.dirname(__file__), "A.1-START.py")
    spec = importlib.util.spec_from_file_location("a1_start", a1_path)
    if spec is None or spec.loader is None:
        print(f"[ERROR] Could not load: {a1_path}", flush=True)
        sys.exit(1)
    a1 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(a1)  # type: ignore[union-attr]
    a1.process_titles_to_recipes(start1, path)  # type: ignore[attr-defined]

    if not os.path.isfile(path):
        print(f"[ERROR] A.1-START did not create: {path}", flush=True)
        sys.exit(1)
    return path


# ================================
# Run
# ================================
if __name__ == "__main__":
    recipes_file_path = _ensure_recipes_workbook()

    # overwrite_existing=False => كيسkip اللي عندها Json Recipe
    # overwrite_existing=True  => كيعّاود يولّد حتى إلا كانت معمّرة
    add_json_recipe_inplace(recipes_file_path, overwrite_existing=False)
