import os
import requests
import pandas as pd
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import random
import sys

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
import a1_config  # noqa: E402

def wrap_text_by_width(draw, text, font, max_width):
    words = text.split()
    lines = []
    current_line = []

    for word in words:
        test_line = current_line + [word]
        test_text = " ".join(test_line)
        bbox = draw.textbbox((0, 0), test_text, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))
    return lines

def create_image(template_path, url_img1, url_img2, title_text,
                font_path, font_size,
                text_color_hex, line_spacing, jpeg_quality,
                crop_from_top=0, desired_width=600,
                x1=0, y1=0, x2=0, y2=600,
                stroke_color_hex="#000000", stroke_width=2,
                stroke_opacity=255,
                output_path="output.jpg"):

    try:
        template = Image.open(template_path).convert("RGBA")
    except Exception as e:
        print(f"Error loading template '{template_path}': {e}")
        return None

    width, height = template.size

    try:
        img1 = Image.open(BytesIO(requests.get(url_img1, timeout=10).content)).convert("RGBA")
        img2 = Image.open(BytesIO(requests.get(url_img2, timeout=10).content)).convert("RGBA")
    except Exception as e:
        print(f"Error fetching images: {e}")
        return None

    img1 = img1.crop((0, crop_from_top, img1.width, img1.height))
    img2 = img2.crop((0, crop_from_top, img2.width, img2.height))

    img1 = img1.resize((desired_width, int(desired_width * img1.height / img1.width)), Image.Resampling.LANCZOS)
    img2 = img2.resize((desired_width, int(desired_width * img2.height / img2.width)), Image.Resampling.LANCZOS)

    background = Image.new("RGBA", template.size, (0, 0, 0, 0))
    background.paste(img1, (x1, y1), img1)
    background.paste(img2, (x2, y2), img2)

    final_image = Image.new("RGBA", template.size, (0, 0, 0, 0))
    final_image.paste(background, (0, 0), background)
    final_image.paste(template, (0, 0), template)

    scale = 2
    text_layer = Image.new("RGBA", (width * scale, height * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(text_layer)
    try:
        font = ImageFont.truetype(font_path, font_size * scale)
    except Exception as e:
        print(f"Error loading font '{font_path}': {e}")
        return None

    max_text_width = int(width * 0.9 * scale)
    wrapped_lines = wrap_text_by_width(draw, title_text, font, max_text_width)
    if not wrapped_lines:
        print("No text to draw.")
        return None

    total_text_height = sum(
        [draw.textbbox((0, 0), line, font=font)[3] - draw.textbbox((0, 0), line, font=font)[1] + line_spacing * scale
         for line in wrapped_lines])
    current_y = (height * scale - total_text_height) // 2

    fill_rgb = tuple(int(text_color_hex.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    stroke_rgb = tuple(int(stroke_color_hex.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) + (stroke_opacity,)

    for line in wrapped_lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (width * scale - text_width) // 2

        # رسم الستروك يدويًا
        for dx in range(-stroke_width * scale, stroke_width * scale + 1):
            for dy in range(-stroke_width * scale, stroke_width * scale + 1):
                if dx**2 + dy**2 <= (stroke_width * scale)**2:
                    draw.text((x + dx, current_y + dy), line, font=font, fill=stroke_rgb)

        # النص الأبيض
        draw.text((x, current_y), line, font=font, fill=fill_rgb)

        current_y += text_height + line_spacing * scale

    text_layer = text_layer.resize((width, height), Image.Resampling.LANCZOS)
    final_image = Image.alpha_composite(final_image, text_layer)

    try:
        final_rgb = final_image.convert("RGB")
        final_rgb.save(output_path, format="JPEG", quality=jpeg_quality, optimize=True, progressive=True)
        print(f"Saved: {output_path}")
        return output_path
    except Exception as e:
        print(f"Error saving image '{output_path}': {e}")
        return None

# MAIN
if __name__ == "__main__":
    templates_dir = a1_config.resolve_templates_dir()
    settings = a1_config.load_settings()
    output_dir = a1_config.all_output_join("output_images")
    os.makedirs(output_dir, exist_ok=True)

    template_config = {
        "1.png": {
            "font_path": "fonts/CoffeeButter.ttf",
            "font_size": 65,
            "text_color_hex": "#FFFFFF",
            "stroke_color_hex": "#000000",
            "stroke_width": 3,
            "stroke_opacity": 255
        },
        "2.png": {
            "font_path": "fonts/DkCanoodleRegular.otf",
            "font_size": 80,
            "text_color_hex": "#FFFFFF",
            "stroke_color_hex": "#000000",
            "stroke_width": 3,
            "stroke_opacity": 255
        },
        "3.png": {
            "font_path": "fonts/CampingTrip.otf",
            "font_size": 85,
            "text_color_hex": "#FFFFFF",
            "stroke_color_hex": "#000000",
            "stroke_width": 3,
            "stroke_opacity": 255
        },
    }

    # Optional per-site override from settings:
    # a6_template_fonts = { "1.png": "fonts/Other.ttf", "2.png": "fonts/Other2.otf" }
    font_overrides = settings.get("a6_template_fonts") if isinstance(settings, dict) else None
    if isinstance(font_overrides, dict):
        for tpl_name, font_path in font_overrides.items():
            nm = str(tpl_name or "").strip()
            fp = str(font_path or "").strip()
            if not nm or not fp:
                continue
            if nm not in template_config:
                template_config[nm] = {
                    "font_size": 65,
                    "text_color_hex": "#FFFFFF",
                    "stroke_color_hex": "#000000",
                    "stroke_width": 3,
                    "stroke_opacity": 255,
                }
            template_config[nm]["font_path"] = fp

    line_spacing = 17
    jpeg_quality = 70
    excel_file = a1_config.all_output_join("Recipes.xlsx")
    output_excel_file = a1_config.all_output_join("Recipes.xlsx")

    try:
        df = pd.read_excel(excel_file)
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        sys.exit(1)

    image_paths = []
    template_files = list(template_config.keys())

    for idx, row in df.iterrows():
        url_img1 = row.get('image_1')
        url_img2 = row.get('image_2')
        title_text = row.get('recipe_title_pin', '')
        output_name = str(row.get('output_name', f"image_{idx + 1}"))

        selected_template_filename = random.choice(template_files)
        template_path = os.path.join(templates_dir, selected_template_filename)

        if not os.path.isfile(template_path):
            print(f"Template '{template_path}' not found.")
            image_paths.append(None)
            continue

        config = template_config[selected_template_filename]
        output_path = os.path.join(output_dir, f"{output_name}.jpg")

        image_path = create_image(
            template_path=template_path,
            url_img1=url_img1,
            url_img2=url_img2,
            title_text=title_text,
            font_path=config["font_path"],
            font_size=config["font_size"],
            text_color_hex=config["text_color_hex"],
            line_spacing=line_spacing,
            jpeg_quality=jpeg_quality,
            stroke_color_hex=config.get("stroke_color_hex", "#000000"),
            stroke_width=config.get("stroke_width", 3),
            stroke_opacity=config.get("stroke_opacity", 255),
            output_path=output_path
        )

        image_paths.append(image_path)

    df['pinterest_image'] = image_paths

    try:
        df.to_excel(output_excel_file, index=False)
        print(f"Updated Excel file: {output_excel_file}")
    except Exception as e:
        print(f"Error saving Excel file: {e}")
        sys.exit(1)
