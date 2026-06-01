import pandas as pd
import os
import re
import sys
from datetime import datetime, timedelta
import random
import openai

# إضافات خاصة بـ Cloudflare R2
import requests
import uuid
from urllib.parse import quote

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
import a1_config  # noqa: E402

# ----------------------------
# R2 — disposable temp bucket (auto-deleted by Cloudflare lifecycle)
# ----------------------------
_K8 = a1_config.load_keys()
_S8 = a1_config.load_settings()
_PP8 = a1_config.load_prompts("a8_pin_bulk")


def _disposable_r2_runtime(force: bool = False) -> dict:
    keys = a1_config.load_keys()
    cfg = a1_config.get_r2_disposable_config(keys)
    return {
        "cfg": cfg,
        "client": a1_config.make_r2_client(keys, disposable=True),
    }


def _r2_put_bytes(data: bytes, key_prefix: str = "pinterest_images") -> str:
    """Upload pin JPEG to shared disposable R2 (auto-cleared after lifecycle days)."""
    rt = _disposable_r2_runtime()
    cfg = rt["cfg"]
    client = rt["client"]
    bucket = cfg["bucket"]
    public_base = cfg["public_base_url"]

    site = a1_config.get_active_site()
    site_tag = str((site or {}).get("id") or "site").strip().lower()
    fname = f"{uuid.uuid4().hex[:11]}.jpg"
    key = f"{site_tag}/{key_prefix}/{fname}".lstrip("/")

    attempts = 5
    for attempt in range(1, attempts + 1):
        try:
            client.put_object(
                Bucket=bucket,
                Key=key,
                Body=data,
                ContentType="image/jpeg",
                ContentDisposition="inline",
            )
            return f"{public_base}/{quote(key)}"
        except Exception as e:
            print(f"      ↻ R2 disposable upload retry {attempt}/{attempts} after error: {e}")
            if attempt == 3:
                try:
                    rt = _disposable_r2_runtime(force=True)
                    client = rt["client"]
                    cfg = rt["cfg"]
                    bucket = cfg["bucket"]
                    public_base = cfg["public_base_url"]
                    print("      ↻ R2 disposable client re-initialized.")
                except Exception as e2:
                    print(f"      ❗ R2 disposable client re-init failed: {e2}")
            if attempt < attempts:
                import time
                time.sleep(1.2 * attempt)

    raise RuntimeError("R2 put_object failed after multiple retries.")

OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or _K8.get("openai_api_key") or "").strip()
openai.api_key = OPENAI_API_KEY

import openai_chat_compat  # noqa: E402

openai_chat_compat.install()

# Pinterest boards: config/settings.json -> pinterest_boards
PINTEREST_BOARDS = list(_S8.get("pinterest_boards") or [])
if not PINTEREST_BOARDS:
    raise RuntimeError(
        "Missing pinterest_boards in settings (config/shared_settings.json, project settings, or site row)."
    )

# ==== المسارات (مطابقة للكود 1 فقط) ====
INPUT_FILE = a1_config.all_output_join("Recipes.xlsx")
OUTPUT_DIRECTORY = a1_config.all_output_dir()
OUTPUT_FILE = 'Pin_01.xlsx'


# ========================================

# ============================
# Helpers
# ============================
def is_url(path_str: str) -> bool:
    return isinstance(path_str, str) and re.match(r'^https?://', path_str.strip()) is not None


def normalize_local_path(path_str: str) -> str:
    if not isinstance(path_str, str):
        return path_str
    path_str = path_str.replace('\\', '/').strip()
    return os.path.normpath(path_str)


def resolve_image_path(raw_path: str, excel_dir: str) -> str | None:
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None
    if is_url(raw_path):
        return raw_path.strip()

    candidate = normalize_local_path(raw_path)
    if os.path.exists(candidate):
        return candidate
    p2 = os.path.join(excel_dir, candidate)
    if os.path.exists(p2):
        return p2
    p3 = os.path.join(excel_dir, 'output_images', os.path.basename(candidate))
    if os.path.exists(p3):
        return p3
    return None


# ====== هنا بدّلنا Cloudinary بـ R2 لكن خَلّينا نفس اسم الدالة ======
def upload_to_cloudinary(image_path: str) -> str | None:
    """
    في الأصل كانت كترفع لـ Cloudinary.
    الآن كترفع لـ Cloudflare R2 لكن بنفس الإسم باش ما نبدلوش باقي الكود.
    """
    try:
        # صورة من URL
        if is_url(image_path):
            resp = requests.get(image_path, timeout=60)
            resp.raise_for_status()
            data = resp.content
            return _r2_put_bytes(data, key_prefix="pinterest_remote")

        # صورة من المسار المحلي
        if image_path and os.path.exists(image_path):
            with open(image_path, "rb") as f:
                data = f.read()
            return _r2_put_bytes(data, key_prefix="pinterest_local")

        print(f"Image not found on disk: {image_path}")
        return None
    except Exception as e:
        print(f"Error uploading to R2 [{image_path}]: {e}")
        return None


def get_tomorrow_date() -> str:
    tomorrow = datetime.today() + timedelta(days=1)
    # نص بصيغة YYYY-MM-DD
    return tomorrow.strftime('%Y-%m-%d')


def generate_sequential_times(num_posts: int) -> list[str]:
    """
    تبدأ 07:00:00 وكل وقت بعد اللي قبله بـ 70–130 دقيقة.
    كترجع نصوص HH:MM:SS
    """
    times = []
    if num_posts <= 0:
        return times

    current_time = datetime(1900, 1, 1, 7, 0, 0)  # 07:00
    times.append(current_time.strftime('%H:%M:%S'))
    for _ in range(1, num_posts):
        offset_minutes = random.randint(70, 130)
        current_time += timedelta(minutes=offset_minutes)
        times.append(current_time.strftime('%H:%M:%S'))
    return times


def categorize_article(article: str, api_key: str, boards: list[str]) -> str:
    try:
        pdef = _PP8.get("categorize_boards") or {}
        system, prompt = a1_config.format_a8_categorize_boards(article, boards, prompts=_PP8)
        resp = openai.ChatCompletion.create(
            model=a1_config.get_openai_model(_S8, _K8),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt}
            ],
            max_tokens=int(pdef.get("max_tokens", 50)),
            temperature=float(pdef.get("temperature", 0))
        )
        category = resp.choices[0].message["content"].strip()
        if category in boards:
            return category
        return boards[0] if boards else "Recipes to Make"
    except Exception as e:
        print(f"Error categorizing article: {e}")
        return boards[0] if boards else "Recipes to Make"


# ============================
# Main
# ============================
def main():
    # 1) قراءة الملف
    try:
        df = pd.read_excel(INPUT_FILE)
    except Exception as e:
        print(f"Error reading {INPUT_FILE}: {e}")
        return

    excel_dir = os.path.dirname(os.path.abspath(INPUT_FILE))

    # 2) إعادة تسمية الأعمدة
    column_mapping = {
        'post_url': 'Pinterest Pin Link',
        'pinterest_image': 'Picture Url 1',
        'pinterest_description': 'Text',
        'pinterest_title': 'Pinterest Pin Title'
    }
    df.rename(columns=column_mapping, inplace=True)

    # 3) تجهيز/رفع الصور
    missing_count = 0

    def process_image_cell(cell):
        nonlocal missing_count
        if pd.isna(cell):
            return None
        p = resolve_image_path(str(cell), excel_dir)
        if p is None:
            missing_count += 1
            print(f"Image not found: {cell}")
            return None
        return upload_to_cloudinary(p)

    if 'Picture Url 1' not in df.columns:
        df['Picture Url 1'] = None
    else:
        df['Picture Url 1'] = df['Picture Url 1'].apply(process_image_cell)

    # 4) أعمدة إضافية + تنسيق التاريخ والوقت كنصوص
    df['Brand name'] = 'recipechefyara'
    df['Pinterest'] = True

    # تاريخ الغد كنص
    df['Date'] = get_tomorrow_date()

    # أوقات متسلسلة كنصوص HH:MM:SS
    df['Time'] = generate_sequential_times(len(df))

    # فرض التنسيق كنصوص بالضبط: YYYY-MM-DD و HH:MM:SS
    df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d')
    df['Time'] = pd.to_datetime(df['Time'], format='%H:%M:%S').dt.strftime('%H:%M:%S')

    # عمود مجمّع اختياري إذا بغيتيه فعمود واحد
    df['DateTime'] = df['Date'] + ' ' + df['Time']  # مثال: 2000-12-25 14:30:00

    # 5) قص النص
    if 'Text' in df.columns:
        df['Text'] = df['Text'].apply(lambda x: x[:490] if isinstance(x, str) else x)
    else:
        df['Text'] = None

    # 6) تصنيف البورد
    if not OPENAI_API_KEY or OPENAI_API_KEY == "YOUR_OPENAI_KEY_HERE":
        print("Warning: OpenAI API key not set. 'Pinterest Board' will default to 'Recipes to Make'.")
        df['Pinterest Board'] = df['Text'].apply(lambda x: "Recipes to Make")
    else:
        df['Pinterest Board'] = df['Text'].apply(
            lambda x: categorize_article(x, OPENAI_API_KEY, PINTEREST_BOARDS) if isinstance(x,
                                                                                            str) and x.strip() else "Recipes to Make"
        )

    # 7) ترتيب أعمدة الإخراج
    output_columns = [
        'Pinterest Pin Link',
        'Picture Url 1',
        'Text',
        'Pinterest Pin Title',
        'Brand name',
        'Pinterest Board',
        'Pinterest',
        'Date',  # YYYY-MM-DD
        'Time',  # HH:MM:SS
        'DateTime'  # YYYY-MM-DD HH:MM:SS (اختياري)
    ]
    for col in output_columns:
        if col not in df.columns:
            df[col] = None
    df_out = df[output_columns]

    # 8) الحفظ
    os.makedirs(OUTPUT_DIRECTORY, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIRECTORY, OUTPUT_FILE)
    try:
        df_out.to_excel(out_path, index=False)
        print(
            f"Done. Saved to {out_path}\n"
            f"- Images missing (not uploaded): {missing_count}\n"
            f"- Rows: {len(df_out)}"
        )
    except Exception as e:
        print(f"Error saving to {out_path}: {e}")


if __name__ == "__main__":
    main()
