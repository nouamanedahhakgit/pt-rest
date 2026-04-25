import os
import sys
import time
import json
import warnings

# Boto3 emits a Python 3.9 EOL notice on import; noise in logs only.
warnings.filterwarnings("ignore", message=".*Boto3 will no longer support Python 3.9.*")
import requests
import pandas as pd
from PIL import Image
from io import BytesIO
from urllib.parse import quote
import uuid
import boto3
from botocore.config import Config  # NEW


def _configure_stdio_utf8() -> None:
    """Windows consoles often use cp1252; emoji in log lines then raise UnicodeEncodeError."""
    for stream in (sys.stdout, sys.stderr):
        if stream is None:
            continue
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError, AttributeError, TypeError):
                pass


_configure_stdio_utf8()

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
import a1_config  # noqa: E402

_KEYS_A3 = a1_config.load_keys()
_ST_A3 = a1_config.load_settings()

# =============================
# Config (UseAPI v3) — secrets from config/keys.json or env; see a1_config.load_keys
# =============================
API_TOKEN = str(_KEYS_A3.get("useapi_token") or os.environ.get("USEAPI_NET_API_TOKEN", ""))
MIDJOURNEY_CHANNEL = str(
    _KEYS_A3.get("useapi_midjourney_channel") or os.environ.get("USEAPI_MJ_CHANNEL", "")
)

USEAPI_BASE_URL = "https://api.useapi.net/v3/midjourney"
IMAGINE_ENDPOINT = f"{USEAPI_BASE_URL}/jobs/imagine"      # POST
JOB_STATUS_ENDPOINT = f"{USEAPI_BASE_URL}/jobs"           # GET /{jobid}

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

# =============================
# Cloudflare R2 — from keys.json
# =============================
CLOUDFLARE_ACCOUNT_ID = str(_KEYS_A3.get("r2_account_id", ""))
R2_ACCESS_KEY_ID = str(_KEYS_A3.get("r2_access_key_id", ""))
R2_SECRET_ACCESS_KEY = str(_KEYS_A3.get("r2_secret_access_key", ""))
BUCKET_NAME = str(_KEYS_A3.get("r2_bucket", ""))
R2_PUBLIC_BUCKET_URL = str(_KEYS_A3.get("r2_public_base_url", ""))

R2_ENDPOINT_URL = f"https://{CLOUDFLARE_ACCOUNT_ID}.r2.cloudflarestorage.com"

# Boto3 config: timeouts + retries + pool
BOTO_CONF = Config(
    connect_timeout=10,
    read_timeout=30,
    retries={"max_attempts": 5, "mode": "standard"},
    max_pool_connections=20
)

# S3 client (R2 compatible)
r2 = boto3.client(
    service_name='s3',
    endpoint_url=R2_ENDPOINT_URL,
    aws_access_key_id=R2_ACCESS_KEY_ID,
    aws_secret_access_key=R2_SECRET_ACCESS_KEY,
    region_name="auto",
    config=BOTO_CONF
)

# =============================
# Paths
# =============================
input_excel = os.path.join(_REPO_ROOT, "ALL", "A1-Pinterest_01-out", "Recipes.xlsx")
output_excel = os.path.join(_REPO_ROOT, "ALL", "A1-Pinterest_01-out", "images.xlsx")

# =============================
# Processing & Polling settings
# =============================
BATCH_SIZE = 2                         # نبعث 3 صفوف دفعة وحدة
IMAGINE_STATUS_DELAY_S = 3             # ثواني بين كل دورة فالبولينغ
MAX_JOB_SECONDS = int(os.getenv("MAX_JOB_SECONDS", "1800"))  # 15 دقيقة حد أقصى لكل job

# مهلات بسيطة للكونسول
DELAY_BETWEEN_BATCHES = int(os.getenv("DELAY_BETWEEN_BATCHES", "15"))   # انتظار 15 ثانية بين الدفعات


def _submit_spacing_seconds() -> float:
    """Seconds between each /imagine submit; supports decimals (e.g. 2.5 from settings.json). Never use int() here."""
    raw = os.getenv("USEAPI_SUBMIT_SPACING_S")
    if raw is not None and str(raw).strip() != "":
        try:
            return max(0.1, float(raw))
        except ValueError:
            pass
    try:
        return max(0.1, float(_ST_A3.get("a3_submit_spacing_seconds", 3)))
    except (TypeError, ValueError):
        return 3.0


SUBMIT_SPACING_S = _submit_spacing_seconds()  # فصل زمني بين كل imagine

# إذا UseAPI رجعات proxy_url فضّلها
PREFER_PROXY_URLS = True

# أقل طول مقبول للبرومبت
MIN_PROMPT_LEN = 10

# ===== Anti-Stall Tunables =====
MAX_STALL_CYCLES = int(os.getenv("MAX_STALL_CYCLES", "600"))  # ~40*3s = 120 ث
HEARTBEAT_EVERY_SEC = int(os.getenv("HEARTBEAT_EVERY_SEC", "15"))

# ===== Asset-Driven Completion (NEW) =====
# إذا الصور موجودة فالـpayload كنكمّلو بلا مانبقاو حابسين حتى status=completed
ALLOW_ASSET_DRIVEN_COMPLETION = os.getenv("ALLOW_ASSET_DRIVEN_COMPLETION", "1") != "0"

# =============================
# Helpers
# =============================
def _safe_json(resp: requests.Response):
    try:
        return resp.json()
    except Exception:
        try:
            return json.loads(resp.text)
        except Exception:
            return {}

def _append_ar(prompt: str, ar: str = "1:1") -> str:
    """نضيف --ar 1:1 داخل البرومبت."""
    suffix = f" --ar {ar.strip()}"
    return prompt if suffix in prompt else (prompt + suffix)

def _normalize_prompt(p) -> str:
    if p is None or pd.isna(p):
        s = ""
    else:
        s = str(p)
    s = s.replace("\r", " ").replace("\n", " ").strip()
    s = " ".join(s.split())
    if len(s) >= 2 and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
        s = s[1:-1].strip()
    return s

def download_image(url):
    """Download image from URL and return PIL Image object"""
    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        image = Image.open(BytesIO(response.content))
        image = image.convert("RGB")
        return image
    except Exception as e:
        raise Exception(f"Failed to download image: {e}")

def split_midjourney_grid(image):
    """نقسم جريد 2x2 لأربع صور متساوية (لازم مربعة)."""
    try:
        width, height = image.size
        if width != height:
            raise Exception(f"Expected square image, got {width}x{height}")
        half = width // 2
        images = [
            image.crop((0,        0,        half, half)),      # TL
            image.crop((half,     0,        width, half)),     # TR
            image.crop((0,        half,     half, height)),    # BL
            image.crop((half,     half,     width, height)),   # BR
        ]
        return images
    except Exception as e:
        raise Exception(f"Failed to split image: {e}")

# ===== R2 robust upload with retries & re-init =====
def _r2_put(image: Image.Image, key_prefix: str) -> str:
    """
    رفع صورة إلى R2 مع retries وتفادي التجمّد.
    نستعمل put_object مباشرة (مستقرة مع R2) + إعادة تهيئة العميل عند الحاجة.
    """
    global r2

    fname = f"{uuid.uuid4().hex[:11]}.png"
    key   = f"{key_prefix}/{fname}".lstrip("/")

    # حضّر البوفر مرة وحدة
    buf = BytesIO()
    image.save(buf, format='PNG', optimize=False)
    data = buf.getvalue()  # bytes مباشرة
    del buf

    attempts = 5
    for attempt in range(1, attempts + 1):
        try:
            r2.put_object(
                Bucket=BUCKET_NAME,
                Key=key,
                Body=data,
                ContentType="image/png",
                ContentDisposition="inline"
            )
            return f"{R2_PUBLIC_BUCKET_URL}/{quote(key)}"
        except Exception as e:
            print(f"      ↻ R2 upload retry {attempt}/{attempts} after error: {e}", flush=True)
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
                    print("      ↻ R2 client re-initialized.", flush=True)
                except Exception as e2:
                    print(f"      ❗ R2 client re-init failed: {e2}", flush=True)
            time.sleep(1.2 * attempt)

    raise RuntimeError("R2 put_object failed after multiple retries.")

def _extract_useapi_urls(job_json: dict):
    """
    نستخرج روابط الصور من رد UseAPI:
    - response.attachments[].url (أو proxy_url)
    - response.grid_url
    - image_urls (top-level)
    - response.url
    """
    urls = []
    resp = job_json.get("response") or {}
    if isinstance(resp, dict):
        atts = resp.get("attachments") or []
        if isinstance(atts, list):
            for att in atts:
                if not isinstance(att, dict):
                    continue
                u = None
                if PREFER_PROXY_URLS:
                    u = att.get("proxy_url")
                u = u or att.get("url")
                if isinstance(u, str) and u.startswith("http"):
                    urls.append(u)
        grid = resp.get("grid_url")
        if isinstance(grid, str) and grid.startswith("http"):
            urls.append(grid)
        u = resp.get("url")
        if isinstance(u, str) and u.startswith("http"):
            urls.append(u)

    top = job_json.get("image_urls")
    if isinstance(top, list):
        for u in top:
            if isinstance(u, str) and u.startswith("http"):
                urls.append(u)

    # dedupe
    seen, unique = set(), []
    for u in urls:
        if u not in seen:
            unique.append(u)
            seen.add(u)
    return unique


# =============================
# UseAPI calls
# =============================
def create_imagine_task_useapi(prompt: str):
    """Start a Midjourney job via UseAPI v3. Returns (jobid, error_or_None)"""
    body = {
        "prompt": prompt,
        "channel": MIDJOURNEY_CHANNEL,
        "stream": False
    }
    try:
        resp = requests.post(IMAGINE_ENDPOINT, headers=HEADERS, json=body, timeout=60)
        if resp.status_code == 201:
            data = _safe_json(resp)
            jobid = data.get("jobid") or data.get("job_id") or data.get("id")
            if jobid:
                return jobid, None
            return None, f"imagine 201 but no jobid in payload: {str(data)[:200]}"
        return None, f"imagine HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return None, f"create_imagine_task_useapi error: {e}"

# ===== استعلام الحالة مع retries قصيرة =====
def get_status_once(jobid: str):
    """استعلام واحد غير حاجز (non-blocking) + retries قصيرة."""
    RETRIES = 3
    for attempt in range(1, RETRIES + 1):
        try:
            url = f"{JOB_STATUS_ENDPOINT}/{jobid}"
            resp = requests.get(url, headers={"Authorization": f"Bearer {API_TOKEN}"}, timeout=30)
            if resp.status_code != 200:
                if attempt < RETRIES:
                    time.sleep(1.0)
                    continue
                return "error", f"http {resp.status_code}: {resp.text[:200]}"
            data = _safe_json(resp)
            status = (data.get("status") or "").lower()

            if status in ("completed", "done", "success"):
                return "completed", data
            if status in ("failed", "error", "moderated"):
                return "failed", data
            if status in ("pending", "queued", "running", "in_progress", "processing"):
                return "pending", data

            # حالة غير معروفة → اعتبرها pending لكن بلّغ الاسم
            return "pending", {"_raw": data, "_note": f"unknown_status:{status or 'none'}"}

        except Exception as e:
            if attempt < RETRIES:
                time.sleep(1.0)
                continue
            return "error", str(e)


# =============================
# R2 Uploading (يحافظ على رسائل الكونسول كما هي)
# =============================
def process_midjourney_grid_to_r2(grid_url, prompt_hash, mode_prefix="main"):
    """
    تحميل الجريد، تقطيع 4، رفع الجريد + 4 صور إلى R2.
    يرجّع: (main_image_url, [split_urls], error_or_None)
    """
    try:
        print(f"    📥 Downloading grid image...", flush=True)
        main_image = download_image(grid_url)

        print(f"    ✂️ Splitting image into 4 parts...", flush=True)
        split_images = split_midjourney_grid(main_image)

        print(f"    ☁️ Uploading main image to Cloudflare R2...", flush=True)
        main_key_prefix = f"midjourney_grids/{mode_prefix}/{str(prompt_hash)[:8]}"
        main_r2_url = _r2_put(main_image, main_key_prefix)

        print(f"    ☁️ Uploading {len(split_images)} split images to Cloudflare R2...", flush=True)
        split_urls = []
        split_key_prefix = f"midjourney_splits/{mode_prefix}/{str(prompt_hash)[:8]}"
        for i, img in enumerate(split_images, 1):
            try:
                url = _r2_put(img, split_key_prefix)
                split_urls.append(url)
                print(f"      ✓ Uploaded image {i}/4", flush=True)
            except Exception as e:
                split_urls.append('')
                print(f"      ❌ Failed image {i}/4 upload: {e}", flush=True)

        # إذا شي وحدة فشلات، نرجّع FAILED باش السطر يتعاود لاحقاً، بدون تجمّد
        if any(u == '' for u in split_urls):
            return None, [], "one or more split uploads failed"

        return main_r2_url, split_urls, None

    except Exception as e:
        error_msg = f"process_midjourney_grid error: {e}"
        print(f"    ❌ {error_msg}", flush=True)
        return None, [], error_msg

def _process_status_to_images_like_script1(status_data, mode_prefix, df, row_idx, prompt_hash="useapi"):
    """
    نفس منطق Cloudinary لكن على R2:
      - إذا عندنا grid_url → نرفع الجريد + 4 splits إلى R2
      - إذا UseAPI رجّع 4 صور مباشرة → نرفع الأربع إلى R2 ونستعمل الأولى كـ main
    يكتب فورًا في الـExcel بعد الرفع.
    """
    # نحاول أولاً grid_url
    grid_url = None
    resp = status_data.get("response") or {}
    if isinstance(resp, dict):
        if PREFER_PROXY_URLS:
            grid_url = resp.get("proxy_grid_url") or resp.get("grid_proxy_url")
        grid_url = grid_url or resp.get("grid_url")

    # إذا توفر grid → نخدم بمنطق سكريبت 1 (main=الجريد، + 4 splits)
    if grid_url and isinstance(grid_url, str) and grid_url.startswith("http"):
        main_url, split_urls, err = process_midjourney_grid_to_r2(grid_url, prompt_hash, mode_prefix=mode_prefix)
        if err:
            return {"statu": "FAILED", "error": err}

        if mode_prefix == "main":
            df.at[row_idx, 'main_image'] = str(main_url or "")
            for j in range(1, 5):
                df.at[row_idx, f'image_{j}'] = split_urls[j-1] if j-1 < len(split_urls) else ''
        else:
            df.at[row_idx, 'main_image_ingredients'] = str(main_url or "")
            for j in range(1, 5):
                df.at[row_idx, f'image_ing_{j}'] = split_urls[j-1] if j-1 < len(split_urls) else ''

        df.to_excel(output_excel, index=False)
        return {"statu": "DONE", "error": None}

    # وإلا، نحاول attachments أو image_urls (أربع صور مباشرة)
    urls = _extract_useapi_urls(status_data)
    if len(urls) >= 4:
        try:
            print(f"    ☁️ Uploading 4 images (no grid present) to Cloudflare R2...", flush=True)
            uploaded = []
            split_key_prefix = f"{mode_prefix}_splits/{str(prompt_hash)[:8]}"
            for j in range(4):
                try:
                    img = download_image(urls[j])
                    up = _r2_put(img, split_key_prefix)
                    uploaded.append(up)
                    print(f"      ✓ Uploaded image {j+1}/4", flush=True)
                except Exception as e:
                    uploaded.append('')
                    print(f"      ❌ Failed image {j+1}/4 upload: {e}", flush=True)

            if any(u == '' for u in uploaded):
                return {"statu": "FAILED", "error": "one or more direct uploads failed"}

            # بما أنه ماكاينش grid، نستعمل أول واحدة كـ main
            if mode_prefix == "main":
                df.at[row_idx, 'main_image'] = str(uploaded[0] or "")
                for j in range(1, 5):
                    df.at[row_idx, f'image_{j}'] = uploaded[j-1] if j-1 < len(uploaded) else ''
            else:
                df.at[row_idx, 'main_image_ingredients'] = str(uploaded[0] or "")
                for j in range(1, 5):
                    df.at[row_idx, f'image_ing_{j}'] = uploaded[j-1] if j-1 < len(uploaded) else ''

            df.to_excel(output_excel, index=False)
            return {"statu": "DONE", "error": None}
        except Exception as e:
            return {"statu": "FAILED", "error": f"direct uploads failed: {e}"}

    # إذا عندنا رابط واحد فقط (نفترضه صورة مربعة/جريد) → نفس منطق grid
    if len(urls) == 1:
        main_url, split_urls, err = process_midjourney_grid_to_r2(urls[0], prompt_hash, mode_prefix=mode_prefix)
        if err:
            return {"statu": "FAILED", "error": err}

        if mode_prefix == "main":
            df.at[row_idx, 'main_image'] = str(main_url or "")
            for j in range(1, 5):
                df.at[row_idx, f'image_{j}'] = split_urls[j-1] if j-1 < len(split_urls) else ''
        else:
            df.at[row_idx, 'main_image_ingredients'] = str(main_url or "")
            for j in range(1, 5):
                df.at[row_idx, f'image_ing_{j}'] = split_urls[j-1] if j-1 < len(split_urls) else ''

        df.to_excel(output_excel, index=False)
        return {"statu": "DONE", "error": None}

    return {"statu": "FAILED", "error": "no usable image URLs returned"}


# =============================
# Parallel-by-3 submission & collection
# =============================
def submit_jobs_for_indices(df, indices, mode_prefix):
    """
    يرسل imagine لائحة من الصفوف (بالترتيب) دفعة وحدة (3 مثلاً)،
    مع مهلة بسيطة بين كل إرسال.
    يرجّع dict: idx -> jobid أو error.
    """
    result = {}
    prompt_col = 'Prompt' if mode_prefix == "main" else 'Prompt Image Ingredients'

    for k, idx in enumerate(indices):
        prompt = _normalize_prompt(df.at[idx, prompt_col])
        if len(prompt) < MIN_PROMPT_LEN:
            result[idx] = {"jobid": None, "error": f"prompt_too_short (len={len(prompt)})"}
            continue

        print(f"  • Submitting {mode_prefix} for row {idx + 1} ...", flush=True)
        jobid, err = create_imagine_task_useapi(_append_ar(prompt, "1:1"))
        if jobid:
            print(f"    ➡️ jobid: {jobid}", flush=True)
        else:
            print(f"    ❌ submit error: {err}", flush=True)

        result[idx] = {"jobid": jobid, "error": err}

        # وقت بين كل imagine باش نحترمو UseAPI
        if k < len(indices) - 1:
            time.sleep(SUBMIT_SPACING_S)

    return result


def wait_and_process_all(df, submit_map, mode_prefix):
    """
    كيسنى جميع jobs حتى يكملو (polling دورة بدورة لكل job)،
    ومن بعد كيحوّلهم لصور مرفوعة على R2 ويكتب النتيجة.
    مع Anti-Stall + Heartbeat + Asset-Driven Completion.
    """
    # علِّم الإخفاقات الفورية
    for idx, info in submit_map.items():
        if not info.get("jobid"):
            if mode_prefix == "main":
                df.at[idx, 'statu'] = 'FAILED'
                df.at[idx, 'error'] = str(info.get("error") or "")
            else:
                df.at[idx, 'statu_ing'] = 'FAILED'
                df.at[idx, 'error_ing'] = str(info.get("error") or "")
            df.to_excel(output_excel, index=False)

    # جهّز لائحة المعلّقات
    pending = {idx: info['jobid'] for idx, info in submit_map.items() if info.get('jobid')}
    results = {}
    start_times = {idx: time.time() for idx in pending}

    # مراقبة التقدّم لمنع التجمّد
    last_status = {idx: "init" for idx in pending}
    stall_cycles = {idx: 0 for idx in pending}
    last_heartbeat = time.time()

    if pending:
        print(f"  ⏳ Waiting for {len(pending)} {mode_prefix} job(s) to complete...", flush=True)

    while pending:
        finished = []
        for idx, jobid in list(pending.items()):
            elapsed = time.time() - start_times[idx]
            if elapsed > MAX_JOB_SECONDS:
                results[idx] = (None, f"timeout: exceeded {MAX_JOB_SECONDS}s for job {jobid}")
                finished.append(idx)
                continue

            status, payload = get_status_once(jobid)

            # ===== NEW: إذا الصور حاضرين، نكمّلو بلا مانستناو status يقلب
            if ALLOW_ASSET_DRIVEN_COMPLETION and isinstance(payload, dict):
                try:
                    has_grid = False
                    resp = payload.get("response") or {}
                    if isinstance(resp, dict):
                        g = (resp.get("proxy_grid_url") or resp.get("grid_proxy_url") or resp.get("grid_url") or "")
                        has_grid = isinstance(g, str) and g.startswith("http")

                    urls = _extract_useapi_urls(payload)
                    if has_grid or (isinstance(urls, list) and len(urls) >= 1):
                        print(f"  🔎 assets ready for row {idx+1} (status={status}) → proceeding to process.", flush=True)
                        results[idx] = (payload, None)
                        finished.append(idx)
                        continue
                except Exception:
                    pass  # ما نوقفوش لأخطاء بسيطة هنا

            # متابعة مراقبة التقدّم (anti-stall)
            prev = last_status.get(idx, "init")
            cur = status
            if cur == prev or cur in ("pending",):
                stall_cycles[idx] = stall_cycles.get(idx, 0) + 1
            else:
                stall_cycles[idx] = 0
            last_status[idx] = cur

            if status == "completed":
                results[idx] = (payload, None)
                finished.append(idx)
                continue
            if status in ("failed", "error", "moderated"):
                results[idx] = (None, f"task status {status}: {str(payload)[:200]}")
                finished.append(idx)
                continue

            # كشف التجمّد
            if stall_cycles[idx] >= MAX_STALL_CYCLES:
                results[idx] = (None, f"stalled: no progress after {stall_cycles[idx]} cycles (~{stall_cycles[idx]*IMAGINE_STATUS_DELAY_S}s)")
                finished.append(idx)
                continue

        # احذف اللي تسالاو من pending
        for idx in finished:
            pending.pop(idx, None)

        # Heartbeat أثناء الانتظار
        now = time.time()
        if pending and (now - last_heartbeat) >= HEARTBEAT_EVERY_SEC:
            still = len(pending)
            longest = int(max((now - start_times[i]) for i in pending)) if pending else 0
            print(f"  … still waiting: {still} {mode_prefix} job(s). longest={longest}s", flush=True)
            last_heartbeat = now

        if pending:
            time.sleep(IMAGINE_STATUS_DELAY_S)

    # عالج النتائج بالترتيب
    for idx in sorted(results.keys()):
        status_data, err = results[idx]
        if not status_data:
            if mode_prefix == "main":
                df.at[idx, 'statu'] = 'FAILED'
                df.at[idx, 'error'] = str(err or "")
            else:
                df.at[idx, 'statu_ing'] = 'FAILED'
                df.at[idx, 'error_ing'] = str(err or "")
            df.to_excel(output_excel, index=False)
            continue

        print(f"  • Processing {mode_prefix} images for row {idx + 1} ...", flush=True)
        res = _process_status_to_images_like_script1(status_data, mode_prefix, df, idx, prompt_hash=submit_map[idx].get("jobid", "useapi"))
        if mode_prefix == "main":
            df.at[idx, 'statu'] = res.get('statu', 'FAILED')
            df.at[idx, 'error'] = str(res.get('error') or "")
        else:
            df.at[idx, 'statu_ing'] = res.get('statu', 'FAILED')
            df.at[idx, 'error_ing'] = str(res.get('error') or "")
        df.to_excel(output_excel, index=False)


# =============================
# DataFrame helpers & batching
# =============================
def ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    # أعمدة الإدخال الأساسية
    if 'Prompt' not in df.columns:
        raise ValueError("Input must contain a 'Prompt' column.")
    if 'Prompt Image Ingredients' not in df.columns:
        raise ValueError("Input must contain a 'Prompt Image Ingredients' column in Recipes.xlsx.")

    # أعمدة الإخراج (main)
    out_cols_main = ['main_image'] + [f'image_{i}' for i in range(1, 5)] + ['statu', 'error']
    for col in out_cols_main:
        if col not in df.columns:
            df[col] = ''

    # أعمدة الإخراج (ingredients)
    out_cols_ing = ['main_image_ingredients'] + [f'image_ing_{i}' for i in range(1, 5)] + ['statu_ing', 'error_ing']
    for col in out_cols_ing:
        if col not in df.columns:
            df[col] = ''

    # dtypes
    string_cols = out_cols_main + out_cols_ing + ['Prompt', 'Prompt Image Ingredients']
    for col in string_cols:
        try:
            df[col] = df[col].astype('string')
        except Exception:
            df[col] = df[col].astype('object')

    return df


def process_batches_by_three(df, indices_all):
    """
    خدم بالدفعات: كل دفعة فيها 3 صفوف (أو أقل فالأخيرة)
    1) MAIN: نرسل لثلاثة مع الفصل الزمني → نسنى يكملو كاملين → نعلجو
    2) INGREDIENTS: نفس الشيء
    """
    total_batches = (len(indices_all) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_num in range(total_batches):
        start = batch_num * BATCH_SIZE
        end = min(start + BATCH_SIZE, len(indices_all))
        batch_indices = indices_all[start:end]

        print(f"\n🚀 Starting batch {batch_num + 1}/{total_batches}", flush=True)
        print(f"--- Processing batch of {len(batch_indices)} rows ---", flush=True)

        # ===== MAIN أولاً =====
        need_main = [i for i in batch_indices if str(df.at[i, 'statu']).strip().upper() != 'DONE']
        if need_main:
            print(f"Processing MAIN for rows: {[i+1 for i in need_main]}", flush=True)
            submit_map_main = submit_jobs_for_indices(df, need_main, mode_prefix="main")
            wait_and_process_all(df, submit_map_main, mode_prefix="main")
        else:
            for i in batch_indices:
                print(f"  ⏩ Row {i + 1}: main prompt already DONE, skipping.", flush=True)

        # ===== INGREDIENTS من بعد =====
        need_ing = [i for i in batch_indices if str(df.at[i, 'statu_ing']).strip().upper() != 'DONE']
        if need_ing:
            print(f"Processing INGREDIENTS for rows: {[i+1 for i in need_ing]}", flush=True)
            submit_map_ing = submit_jobs_for_indices(df, need_ing, mode_prefix="ingredients")
            wait_and_process_all(df, submit_map_ing, mode_prefix="ingredients")
        else:
            for i in batch_indices:
                print(f"  ⏩ Row {i + 1}: ingredients prompt already DONE, skipping.", flush=True)

        print(f"--- Batch completed ---\n", flush=True)

        # Save after each batch
        df.to_excel(output_excel, index=False)
        print(f"💾 Progress saved to {output_excel}", flush=True)

        # Delay between batches (except last)
        if batch_num < total_batches - 1:
            print(f"⏳ Waiting {DELAY_BETWEEN_BATCHES} seconds before next batch...", flush=True)
            time.sleep(DELAY_BETWEEN_BATCHES)


# =============================
# Main
# =============================
def main():
    # Verify R2 connection
    try:
        r2.head_bucket(Bucket=BUCKET_NAME)
        print("✅ Cloudflare R2 connection successful", flush=True)
    except Exception as e:
        print(f"❌ R2 configuration error: {e}", flush=True)
        print("Make sure credentials/bucket/public base URL are correct.", flush=True)
        return

    # Sanity checks for UseAPI
    if not API_TOKEN or API_TOKEN == "YOUR_USEAPI_NET_API_TOKEN":
        print("⚠️  Please set USEAPI_NET_API_TOKEN env var.", flush=True)
    if not MIDJOURNEY_CHANNEL or MIDJOURNEY_CHANNEL == "YOUR_MIDJOURNEY_CHANNEL_ID":
        print("⚠️  Please set USEAPI_MJ_CHANNEL (Midjourney Channel ID).", flush=True)

    # Load input or resume from existing output
    if os.path.exists(output_excel):
        df = pd.read_excel(output_excel)
        print(f"Resuming from existing file: {output_excel}", flush=True)
    else:
        df = pd.read_excel(input_excel)
        print(f"Starting fresh from: {input_excel}", flush=True)

    df = ensure_columns(df)

    # rows needing processing:
    indices_to_process = []
    for idx, row in df.iterrows():
        need_main = str(row.get('statu', '')).strip().upper() != 'DONE'
        need_ing  = str(row.get('statu_ing', '')).strip().upper() != 'DONE'
        if need_main or need_ing:
            indices_to_process.append(idx)

    print(f"Total rows: {len(df)} | To process now (any not DONE): {len(indices_to_process)}", flush=True)

    if indices_to_process:
        process_batches_by_three(df, indices_to_process)

    # Final save
    df.to_excel(output_excel, index=False)
    print(f"\n✅ All processing completed! Results saved to {output_excel}", flush=True)

if __name__ == "__main__":
    print("🚀 Starting script in 3 seconds...", flush=True)
    time.sleep(3)
    main()
