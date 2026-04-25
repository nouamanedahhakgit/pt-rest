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
import boto3
from botocore.config import Config
from urllib.parse import quote

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
import a1_config  # noqa: E402

_K8 = a1_config.load_keys()
_S8 = a1_config.load_settings()
_PP8 = a1_config.load_prompts("a8_pin_bulk")

# ----------------------------
# Configuration Section (R2: config/keys.json)
# ----------------------------

CLOUDFLARE_ACCOUNT_ID = str(_K8.get("r2_account_id", ""))
R2_ACCESS_KEY_ID = str(_K8.get("r2_access_key_id", ""))
R2_SECRET_ACCESS_KEY = str(_K8.get("r2_secret_access_key", ""))
BUCKET_NAME = str(_K8.get("r2_bucket", ""))
R2_PUBLIC_BUCKET_URL = str(_K8.get("r2_public_base_url", ""))

R2_ENDPOINT_URL = f"https://{CLOUDFLARE_ACCOUNT_ID}.r2.cloudflarestorage.com"

BOTO_CONF = Config(
    connect_timeout=10,
    read_timeout=30,
    retries={"max_attempts": 5, "mode": "standard"},
    max_pool_connections=20
)

r2 = boto3.client(
    service_name='s3',
    endpoint_url=R2_ENDPOINT_URL,
    aws_access_key_id=R2_ACCESS_KEY_ID,
    aws_secret_access_key=R2_SECRET_ACCESS_KEY,
    region_name="auto",
    config=BOTO_CONF
)

def _r2_put_bytes(data: bytes, key_prefix: str = "pinterest_images") -> str:
    """
    رفع bytes إلى Cloudflare R2 مع retries بسيطة،
    وترجيع رابط عمومي من R2_PUBLIC_BUCKET_URL.
    """
    global r2

    fname = f"{uuid.uuid4().hex[:11]}.jpg"
    key = f"{key_prefix}/{fname}".lstrip("/")

    attempts = 5
    for attempt in range(1, attempts + 1):
        try:
            r2.put_object(
                Bucket=BUCKET_NAME,
                Key=key,
                Body=data,
                ContentType="image/jpeg",
                ContentDisposition="inline"
            )
            return f"{R2_PUBLIC_BUCKET_URL}/{quote(key)}"
        except Exception as e:
            print(f"      ↻ R2 upload retry {attempt}/{attempts} after error: {e}")
            # إعادة تهيئة العميل فالمحاولة الثالثة بحال سكريبت 2
            if attempt == 3:
                try:
                    r2 = boto3.client(
                        service_name='s3',
                        endpoint_url=R2_ENDPOINT_URL,
                        aws_access_key_id=R2_ACCESS_KEY_ID,
                        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
                        region_name="auto",
                        config=BOTO_CONF
                    )
                    print("      ↻ R2 client re-initialized.")
                except Exception as e2:
                    print(f"      ❗ R2 client re-init failed: {e2}")
            if attempt < attempts:
                import time
                time.sleep(1.2 * attempt)

    raise RuntimeError("R2 put_object failed after multiple retries.")

OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or _K8.get("openai_api_key") or "").strip()
openai.api_key = OPENAI_API_KEY

import openai_chat_compat  # noqa: E402

openai_chat_compat.install()

# Pinterest boards: config/settings.json -> pinterest_boards
PINTEREST_BOARDS = list(
    _S8.get("pinterest_boards")
    or [
        "Party Snacks & Finger Foods",
        "Irresistible Desserts & Sweets",
        "Cakes, Cookies & Treats",
        "Healthy Dinner Inspiration",
        "Family Dinner Ideas",
        "Easy Recipes",
        "Recipes to Make",
        "Quick & Easy Dinner Recipes",
        "Easy & Delicious Appetizers",
        "Summer Drinks Inspiration",
        "Smoothies, Juices & Mocktails",
        "Refreshing Drinks & Beverages",
        "Food cravings",
    ]
)

# ==== المسارات (مطابقة للكود 1 فقط) ====
INPUT_FILE = os.path.join(_REPO_ROOT, "ALL", "A1-Pinterest_01-out", "images.xlsx")
OUTPUT_DIRECTORY = os.path.join(_REPO_ROOT, "ALL", "A1-Pinterest_01-out")
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
        prompt = (
            pdef.get("user_intro", "")
            + ", ".join(boards)
            + pdef.get("user_mid", ".\n\nAnalyze the following article and categorize it into one of these Pinterest boards.\n\n")
            + f"Article: {article}"
            + pdef.get("user_suffix", "\n\nCategory:")
        )
        resp = openai.ChatCompletion.create(
            model=a1_config.get_openai_model(_S8, _K8),
            messages=[
                {"role": "system", "content": pdef.get("system", "You classify recipe/food texts into exactly ONE board from the list.")},
                {"role": "user", "content": prompt}
            ],
            max_tokens=int(pdef.get("max_tokens", 50)),
            temperature=float(pdef.get("temperature", 0))
        )
        category = resp.choices[0].message["content"].strip()
        if category in boards:
            return category
        return "Recipes to Make"
    except Exception as e:
        print(f"Error categorizing article: {e}")
        return "Recipes to Make"


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
