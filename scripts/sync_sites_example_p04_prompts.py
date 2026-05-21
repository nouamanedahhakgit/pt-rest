"""
Rebuild site id p04 in config/sites.example.json from config/prompts/*.json.

Run from repo root (when your shell allows):
  python scripts/sync_sites_example_p04_prompts.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
PROMPTS = CONFIG / "prompts"
SITES_EXAMPLE = CONFIG / "sites.example.json"
# Single-file copy of all inline prompt objects (kept in sync with config/prompts/*.json).
PROMPTS_BUNDLE = CONFIG / "examples" / "site-p04-full-prompts.json"

NAMES = (
    "a1_start",
    "a2_json",
    "a2_prompt",
    "a4_articles",
    "a5_pin_data",
    "a8_pin_bulk",
)


def main() -> None:
    doc = json.loads(SITES_EXAMPLE.read_text(encoding="utf-8"))
    if PROMPTS_BUNDLE.is_file():
        prompts = json.loads(PROMPTS_BUNDLE.read_text(encoding="utf-8"))
    else:
        prompts = {}
        for name in NAMES:
            path = PROMPTS / f"{name}.json"
            prompts[name] = json.loads(path.read_text(encoding="utf-8"))

    site = {
        "id": "p04",
        "display_name": "Site D (full inline prompts — every system / user_template / user block from config/prompts/*.json)",
        "out_dir": "A1-Pinterest_01-out",
        "start_file": "START1.xlsx",
        "openai_api_key": "",
        "openai_model": "gpt-4o-mini",
        "useapi_token": "",
        "useapi_midjourney_channel": "",
        "r2_account_id": "",
        "r2_access_key_id": "",
        "r2_secret_access_key": "",
        "r2_bucket": "",
        "r2_public_base_url": "",
        "wordpress_url": "https://your-site-4.example",
        "wordpress_user": "wp-user-4",
        "wordpress_app_password": "paste app password here",
        "no_shared_settings": False,
        "no_shared_prompts": False,
        "settings": {
            "article_language": "English",
            "a4_total_words": 2500,
            "a4_recipe_excel": "ALL/A1-Pinterest_01-out/images.xlsx",
            "category_id_mapping": {
                "drinks": 10,
                "dessert": 20,
                "appetizers": 5,
                "dinner": 4,
            },
        },
        "prompts": prompts,
    }

    sites = [s for s in doc["sites"] if s.get("id") != "p04"]
    idx = next((i for i, s in enumerate(sites) if s.get("id") == "p03"), len(sites))
    sites.insert(idx, site)
    doc["sites"] = sites

    SITES_EXAMPLE.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("Updated", SITES_EXAMPLE)


if __name__ == "__main__":
    main()
