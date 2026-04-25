#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
import pandas as pd
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
MODEL = a1_config.get_openai_model(_SETTINGS, _KEYS)
_PROMPTS_A1 = a1_config.load_prompts("a1_start")

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

REQUIRED_LABELS = [
    "Prep Time:",
    "Cook Time:",
    "Total Time:",
    "Course:",
    "Cuisine:",
    "Servings:",
    "Calories:",
]

def has_label(text: str, label: str) -> bool:
    return label.lower() in (text or "").lower()

def extract_calories_line(recipe: str) -> str:
    """
    كتحاول تلقى سطر Calories:
    """
    if not recipe:
        return ""
    m = re.search(r"(?im)^\s*calories\s*:\s*(.+)\s*$", recipe)
    return (m.group(1).strip() if m else "")

def ensure_required_fields_with_na(recipe: str) -> str:
    """
    كنكمّلو Labels اللي ناقصين بـ N/A (ماشي Calories)
    Calories ما كنخليوهاش N/A فهاد النسخة حيث بغيتها ضروري.
    """
    recipe = (recipe or "").strip()
    low = recipe.lower()

    missing = []
    for lbl in REQUIRED_LABELS:
        if lbl.lower() not in low:
            missing.append(lbl)

    if not missing:
        return recipe

    # Calories ما خصهاش تكون N/A هنا
    missing_non_cal = [lbl for lbl in missing if lbl != "Calories:"]
    block = "\n".join([f"{lbl} N/A" for lbl in missing_non_cal])

    # إذا كاين شي حاجة نزيدوها
    if block.strip():
        recipe = (recipe + "\n\n" + block).strip()

    return recipe

# ================================
# Repair pass (يكمّل Calories + labels بدون ما يبدّل الوصفة)
# ================================
def repair_recipe_to_force_calories(recipe_text: str) -> str:
    """
    كيرجع نفس الوصفة ولكن كيتأكد Calories موجودة (Estimated) وباقي Labels كاملين.
    ما كيزيدش أقسام أخرى.
    """
    p = _PROMPTS_A1.get("repair_recipe") or {}
    system_msg = p.get("system", "")
    user_msg = (p.get("user_template") or "").format(recipe_text=recipe_text)
    resp = openai.ChatCompletion.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=int(p.get("max_tokens", 800)),
        temperature=float(p.get("temperature", 0.2)),
    )
    return clean_text(resp.choices[0].message["content"])

# ================================
# Generate Recipe from Title (FORCES Calories)
# ================================
def generate_recipe_from_title(title: str) -> str:
    title = str(title or "").strip()

    p = _PROMPTS_A1.get("generate_from_title") or {}
    system_msg = p.get("system", "")
    user_msg = (p.get("user_template") or "").format(title=title)
    resp = openai.ChatCompletion.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=int(p.get("max_tokens", 1200)),
        temperature=float(p.get("temperature", 0.6)),
    )

    recipe = clean_text(resp.choices[0].message["content"])

    # كمّل labels اللي ناقصين بـ N/A (ما عدا Calories)
    recipe = ensure_required_fields_with_na(recipe)

    # Calories خاصها تكون موجودة وبلا N/A
    cal_val = extract_calories_line(recipe)
    if (not has_label(recipe, "Calories:")) or (cal_val.strip().lower() == "n/a") or (cal_val.strip() == ""):
        recipe = repair_recipe_to_force_calories(recipe)

    return recipe

# ================================
# Pipeline: Excel Title -> Recipe
# ================================
def process_titles_to_recipes(input_file_path: str, output_file_path: str):
    df = pd.read_excel(input_file_path)

    if "Title" not in df.columns:
        raise RuntimeError("Column 'Title' is required.")

    if "Recipe" not in df.columns:
        df["Recipe"] = ""

    for i, row in df.iterrows():
        title = str(row.get("Title", "") or "").strip()
        existing = str(row.get("Recipe", "") or "").strip()

        try:
            if not existing:
                df.at[i, "Recipe"] = generate_recipe_from_title(title)
                print(f"[OK] Row {i+1}: generated")
            else:
                # حتى إلا كان معمّر: نضمن labels + calories
                cleaned = clean_text(existing)
                cleaned = ensure_required_fields_with_na(cleaned)

                cal_val = extract_calories_line(cleaned)
                if (not has_label(cleaned, "Calories:")) or (cal_val.strip().lower() == "n/a") or (cal_val.strip() == ""):
                    cleaned = repair_recipe_to_force_calories(cleaned)

                df.at[i, "Recipe"] = cleaned
                print(f"[OK] Row {i+1}: verified/repair")
        except Exception as e:
            df.at[i, "Recipe"] = ""
            print(f"[WARN] Row {i+1}: failed -> {e}")

    out_df = df[["Title", "Recipe"]].copy()

    out_dir = os.path.dirname(output_file_path)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    out_df.to_excel(output_file_path, index=False)
    print(f"[DONE] Saved -> {output_file_path}")
    print(f"[INFO] Rows: {len(out_df)}")

# ================================
# Run
# ================================
if __name__ == "__main__":
    # Paths: titles from STARTS/ (see a1_config.resolve_start_titles_excel); output under ALL/{site out}/
    input_file_path = a1_config.resolve_start_titles_excel()
    output_file_path = a1_config.all_output_join("Recipes.xlsx")
    if not os.path.isfile(input_file_path):
        print(f"[ERROR] Input not found: {input_file_path}", flush=True)
        raise SystemExit(1)
    process_titles_to_recipes(input_file_path, output_file_path)
