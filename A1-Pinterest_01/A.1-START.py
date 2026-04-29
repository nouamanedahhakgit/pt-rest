#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
from collections import defaultdict
from datetime import datetime
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
    if "Generated At" not in df.columns:
        df["Generated At"] = ""

    def _norm_title(v) -> str:
        if pd.isna(v):
            return ""
        s = str(v).strip()
        if s.lower() in {"", "nan", "none"}:
            return ""
        return s

    title_mask = df["Title"].apply(lambda v: bool(_norm_title(v)))
    title_positions = [int(i) for i, ok in title_mask.items() if bool(ok)]
    total_rows = len(title_positions)
    generated_count = 0
    verified_count = 0
    failed_count = 0
    print(f"[INFO] Input columns: {', '.join([str(c) for c in df.columns])}")
    print(f"[INFO] Total titles: {total_rows}")

    row_processed_ok = {}
    for i in title_positions:
        row = df.iloc[i]
        row_num = i + 1
        title = _norm_title(row.get("Title", ""))
        existing = str(row.get("Recipe", "") or "").strip()
        stamp_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row_processed_ok[i] = False

        try:
            if not existing:
                df.at[i, "Recipe"] = generate_recipe_from_title(title)
                df.at[i, "Generated At"] = stamp_now
                generated_count += 1
                print(f"[OK] Recipe {generated_count}/{total_rows} generated (row {row_num})")
            else:
                # حتى إلا كان معمّر: نضمن labels + calories
                cleaned = clean_text(existing)
                cleaned = ensure_required_fields_with_na(cleaned)

                cal_val = extract_calories_line(cleaned)
                if (not has_label(cleaned, "Calories:")) or (cal_val.strip().lower() == "n/a") or (cal_val.strip() == ""):
                    cleaned = repair_recipe_to_force_calories(cleaned)

                df.at[i, "Recipe"] = cleaned
                if not str(row.get("Generated At", "") or "").strip():
                    df.at[i, "Generated At"] = stamp_now
                verified_count += 1
                print(f"[OK] Row {row_num}/{total_rows}: already exists -> verified/repair")
            row_processed_ok[i] = True
        except Exception as e:
            df.at[i, "Recipe"] = ""
            df.at[i, "Generated At"] = ""
            failed_count += 1
            print(f"[WARN] Row {row_num}/{total_rows}: failed -> {e}")

    run_df = df.loc[title_positions, ["Title", "Recipe", "Generated At"]].copy()
    run_df["Title"] = run_df["Title"].apply(_norm_title)
    run_df = run_df[run_df["Title"] != ""].copy()
    run_df = run_df.drop_duplicates(subset=["Title"], keep="last")

    out_dir = os.path.dirname(output_file_path)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    if os.path.isfile(output_file_path):
        try:
            existing_df = pd.read_excel(output_file_path)
        except Exception:
            existing_df = pd.DataFrame(columns=["Title", "Recipe", "Generated At"])
    else:
        existing_df = pd.DataFrame(columns=["Title", "Recipe", "Generated At"])

    for col in ["Title", "Recipe", "Generated At"]:
        if col not in existing_df.columns:
            existing_df[col] = ""
    existing_df = existing_df[["Title", "Recipe", "Generated At"]].copy()
    existing_df["Title"] = existing_df["Title"].apply(_norm_title)
    existing_df = existing_df[existing_df["Title"] != ""].copy()
    existing_df = existing_df.drop_duplicates(subset=["Title"], keep="last")

    out_df = pd.concat([existing_df, run_df], ignore_index=True)
    out_df = out_df.drop_duplicates(subset=["Title"], keep="last")
    out_df.to_excel(output_file_path, index=False)
    print(f"[DONE] Saved -> {output_file_path}")
    print(f"[INFO] Output columns: {', '.join([str(c) for c in out_df.columns])}")
    print(f"[INFO] Rows: {len(out_df)}")
    print(
        f"[INFO] Summary: generated={generated_count}, "
        f"verified_existing={verified_count}, failed={failed_count}, total={total_rows}"
    )

    def _recipe_ok(pos: int) -> bool:
        if "Recipe" not in df.columns:
            return bool(row_processed_ok.get(pos))
        has_recipe = bool(str(df.iloc[pos].get("Recipe", "") or "").strip())
        return has_recipe or bool(row_processed_ok.get(pos))

    try:
        if "source_file" in df.columns and "source_row" in df.columns:
            per: dict = defaultdict(dict)
            for pos in title_positions:
                sf = str(df.iloc[pos].get("source_file", "") or "").strip()
                raw_sr = df.iloc[pos].get("source_row", 0)
                try:
                    sr = int(float(raw_sr))
                except (TypeError, ValueError):
                    sr = 0
                if not sf or sr < 2:
                    continue
                per[sf][sr] = _recipe_ok(pos)
            for fn, rowmap in per.items():
                fp = a1_config.REPO_ROOT / "STARTS" / fn
                try:
                    a1_config.apply_usage_to_start_workbook(str(fp), dict(rowmap))
                except Exception as fe:
                    print(f"[WARN] STARTS usage sync ({fn}): {fe}", flush=True)
        else:
            row_usage_map = {}
            for pos in title_positions:
                row_usage_map[pos + 2] = _recipe_ok(pos)
            a1_config.apply_usage_to_start_workbook(input_file_path, row_usage_map)
    except Exception as e:
        print(f"[WARN] STARTS .xlsx usage columns sync skipped/failed: {e}", flush=True)


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
