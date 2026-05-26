"""
A.6b-PIN IMAGES HTML.py
Generate Pinterest pin images by rendering per-project HTML/CSS templates with Playwright.
AI (OpenAI) generates three text fields per row: title, hook, text.

- Templates live in:   ALL/<out_dir>/templates-html/*.html
- Seeded from:         A1-Pinterest_01/templates-html/
- Placeholders in templates: {{image_1}}, {{image_2}}, {{title}}, {{hook}}, {{text}}
- Each row picks an .html template at random (same rotation concept as A.6-PIN IMAGES.py)
- Output: JPEG 1000x1500 saved to output_images/, pinterest_image column updated
"""
import html as _html
import json
import os
import random
import re
import sys
import time
from pathlib import Path

import pandas as pd

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import openai_chat_compat  # noqa: E402
openai_chat_compat.install()

import openai          # noqa: E402
import a1_config       # noqa: E402

PIN_W = 1000
PIN_H = 1500
JPEG_QUALITY = 80


# ---------- helpers ----------

def _read_template(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _escape(v: str) -> str:
    return _html.escape(str(v or ""), quote=True)


def _fill_template(tpl: str, image_1: str, image_2: str,
                   title: str, hook: str, text: str) -> str:
    return (
        tpl
        .replace("{{image_1}}", str(image_1 or ""))
        .replace("{{image_2}}", str(image_2 or ""))
        .replace("{{title}}", _escape(title))
        .replace("{{hook}}",  _escape(hook))
        .replace("{{text}}",  _escape(text))
    )


# ---------- OpenAI ----------

def _generate_pin_texts(recipe_name: str, settings: dict, keys: dict) -> dict:
    """
    Call OpenAI to generate three visual pin text fields:
      title  – bold visual pin title (max 8 words)
      hook   – short punchy hook/teaser (max 6 words)
      text   – brief tagline (max 10 words)
    Returns dict with keys title/hook/text; falls back to recipe_name on failure.
    """
    lang = str(settings.get("article_language", "English"))
    prompts = a1_config.load_prompts("a6b_pin_image_html")
    sec = prompts.get("pin_texts") or {}
    system, user = a1_config.format_a6b_pin_texts(recipe_name, prompts=prompts, settings=settings)

    for attempt in range(3):
        try:
            resp = openai.ChatCompletion.create(
                model=a1_config.get_openai_model(settings, keys),
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                max_tokens=int(sec.get("max_tokens", 220)),
                temperature=float(sec.get("temperature", 0.85)),
            )
            raw = resp.choices[0].message["content"].strip()

            # Strip markdown code fences if present
            raw = re.sub(r"^```[a-z]*\n?", "", raw, flags=re.MULTILINE)
            raw = re.sub(r"\n?```$", "", raw, flags=re.MULTILINE).strip()

            data = json.loads(raw)
            return {
                "title": str(data.get("title") or recipe_name).strip(),
                "hook":  str(data.get("hook")  or "").strip(),
                "text":  str(data.get("text")  or "").strip(),
            }
        except json.JSONDecodeError:
            # Try to pull the first {...} from the response
            m = re.search(r"\{[^{}]+\}", raw, re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group())
                    return {
                        "title": str(data.get("title") or recipe_name).strip(),
                        "hook":  str(data.get("hook")  or "").strip(),
                        "text":  str(data.get("text")  or "").strip(),
                    }
                except Exception:
                    pass
            print(f"  [WARN] JSON parse failed (attempt {attempt+1}), raw: {raw[:120]}")
        except Exception as e:
            print(f"  [WARN] OpenAI error (attempt {attempt+1}): {e}")
            if attempt < 2:
                time.sleep(3 * (attempt + 1))

    # Final fallback
    return {"title": recipe_name, "hook": "", "text": ""}


# ---------- Playwright ----------

def _playwright_install_hint(extra: str = "") -> None:
    py = sys.executable
    print(f"Python used by this script: {py}", file=sys.stderr)
    if extra:
        print(extra, file=sys.stderr)
    print(
        "Install Playwright for THIS Python (copy/paste):\n"
        f'  "{py}" -m pip install playwright\n'
        f'  "{py}" -m playwright install chromium',
        file=sys.stderr,
    )


def _ensure_playwright() -> bool:
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return True
    except ImportError as e:
        print(f"ERROR: playwright is not available ({e}).", file=sys.stderr)
        _playwright_install_hint(
            "If you already ran pip install, the dashboard may use a different Python than your terminal."
        )
        # One-shot auto-install with the same interpreter as this script
        try:
            import subprocess
            print("Trying auto-install with this Python...", file=sys.stderr)
            pip = subprocess.run(
                [sys.executable, "-m", "pip", "install", "playwright"],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if pip.stdout.strip():
                print(pip.stdout.strip(), file=sys.stderr)
            if pip.returncode != 0 and pip.stderr.strip():
                print(pip.stderr.strip(), file=sys.stderr)
                return False
            from playwright.sync_api import sync_playwright  # noqa: F401
            subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                check=False,
                timeout=600,
            )
            print("Playwright installed. Re-run PIN IMAGE HTML if browser download just finished.", file=sys.stderr)
            return True
        except Exception as install_err:
            print(f"Auto-install failed: {install_err}", file=sys.stderr)
            return False


def _launch_chromium(playwright):
    try:
        return playwright.chromium.launch(headless=True)
    except Exception as e:
        msg = str(e).lower()
        if "executable" in msg or "browser" in msg or "chromium" in msg or "doesn't exist" in msg:
            print(f"ERROR: Chromium browser missing ({e}).", file=sys.stderr)
            _playwright_install_hint("Run the chromium install line above, then retry PIN IMAGE HTML.")
        else:
            print(f"ERROR: Could not launch Chromium: {e}", file=sys.stderr)
        raise


def _render_pin(page, html: str, output_path: str) -> bool:
    try:
        page.set_viewport_size({"width": PIN_W, "height": PIN_H})
        page.set_content(html, wait_until="networkidle", timeout=60_000)
        try:
            page.wait_for_load_state("networkidle", timeout=15_000)
        except Exception:
            pass
        page.screenshot(
            path=output_path,
            type="jpeg",
            quality=JPEG_QUALITY,
            full_page=False,
            clip={"x": 0, "y": 0, "width": PIN_W, "height": PIN_H},
        )
        print(f"  Saved: {output_path}")
        return True
    except Exception as e:
        print(f"  [ERROR] render '{output_path}': {e}", file=sys.stderr)
        return False


# ---------- main ----------

def main() -> int:
    if not _ensure_playwright():
        return 1
    from playwright.sync_api import sync_playwright

    settings = a1_config.load_settings()
    keys     = a1_config.load_keys()
    a1_config.set_openai_key_from_keys(keys)

    site = a1_config.get_active_site()
    print(f"Site id       : {site.get('id', '')}")
    print(f"Output dir    : {a1_config.all_output_dir()}")

    templates_dir = Path(a1_config.resolve_html_templates_dir())
    output_dir    = a1_config.all_output_join("output_images")
    os.makedirs(output_dir, exist_ok=True)

    template_files = sorted(p for p in templates_dir.glob("*.html") if p.is_file())
    if not template_files:
        print(f"No HTML templates in '{templates_dir}'.", file=sys.stderr)
        return 1
    print(f"Templates dir : {templates_dir}")
    print(f"HTML templates: {[p.name for p in template_files]}")

    excel_file = a1_config.all_output_join("Recipes.xlsx")
    try:
        df = a1_config.read_excel_with_retry(excel_file)
    except Exception as e:
        print(f"Error reading Excel: {e}", file=sys.stderr)
        return 1

    # ------ phase 1: generate AI texts for all rows ------
    print(f"\n=== Phase 1: Generating AI texts for {len(df)} rows ===")
    ai_rows: list[dict] = []
    for idx, row in df.iterrows():
        recipe_name = (
            str(row.get("recipe_title_pin", "") or "")
            or str(row.get("recipe_title", "") or "")
            or str(row.get("title", "") or "")
            or f"Recipe {idx + 1}"
        ).strip()
        output_name = str(row.get("output_name", f"image_{idx + 1}"))
        print(f"  [{idx + 1}/{len(df)}] AI text for: {recipe_name[:60]}")
        texts = _generate_pin_texts(recipe_name, settings, keys)
        print(f"         title: {texts['title']}")
        print(f"         hook : {texts['hook']}")
        print(f"         text : {texts['text']}")
        ai_rows.append({
            "url_img1":    str(row.get("image_1", "") or ""),
            "url_img2":    str(row.get("image_2", "") or ""),
            "output_name": output_name,
            "title":       texts["title"],
            "hook":        texts["hook"],
            "text":        texts["text"],
        })

    # ------ phase 2: render all images with Playwright ------
    print(f"\n=== Phase 2: Rendering {len(ai_rows)} pin images ===")
    image_paths: list = []

    with sync_playwright() as pw:
        browser = _launch_chromium(pw)
        try:
            ctx  = browser.new_context(
                viewport={"width": PIN_W, "height": PIN_H},
                device_scale_factor=1,
            )
            page = ctx.new_page()

            for i, row_data in enumerate(ai_rows):
                tpl_path = random.choice(template_files)
                tpl_html = _read_template(tpl_path)
                filled   = _fill_template(
                    tpl_html,
                    row_data["url_img1"],
                    row_data["url_img2"],
                    row_data["title"],
                    row_data["hook"],
                    row_data["text"],
                )
                output_path = os.path.join(output_dir, f"{row_data['output_name']}.jpg")
                print(f"  [{i+1}/{len(ai_rows)}] {tpl_path.name} → {row_data['output_name']}.jpg")
                ok = _render_pin(page, filled, output_path)
                image_paths.append(output_path if ok else None)

            page.close()
            ctx.close()
        finally:
            browser.close()

    df["pinterest_image"] = image_paths
    try:
        a1_config.to_excel_with_retry(df, excel_file)
        print(f"\nUpdated Excel: {excel_file}")
    except Exception as e:
        print(f"Error saving Excel: {e}", file=sys.stderr)
        return 1

    done = sum(1 for p in image_paths if p)
    print(f"Done: {done}/{len(image_paths)} images rendered.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
