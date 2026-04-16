#!/usr/bin/env python3
"""
Ebook Factory — Cover Generator
=================================
Generates KDP-ready book covers (1600x2560 JPEG, RGB, <5MB) using:
  Layer 1: Ideogram API — generates background art only (no text)
  Layer 2: Pillow — composites title, subtitle, author name locally

This gives full font control and consistent catalog branding while
getting high-quality, niche-appropriate background art from Ideogram.

Cost per cover: ~$0.09 (Turbo generate $0.03 + upscale $0.06)

Usage:
  python3 cover_generator.py --book-dir PATH/TO/WORKBOOK
  python3 cover_generator.py --book-dir PATH --niche productivity
  python3 cover_generator.py --book-dir PATH --dry-run    # show what would be generated
  python3 cover_generator.py --book-dir PATH --no-upscale # faster, lower res
  python3 cover_generator.py --book-dir PATH --quality    # $0.06 generate tier
  python3 cover_generator.py --book-dir PATH --variations 3  # generate 3, pick best

Requires:
  IDEOGRAM_API_KEY in ~/.hermes/.env
  pip install Pillow requests
"""

import argparse
import io
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# ── Paths ─────────────────────────────────────────────────────────────────────

def get_hermes_home() -> Path:
    try:
        from hermes_constants import get_hermes_home as _ghh
        return Path(_ghh())
    except ImportError:
        return Path.home() / ".hermes"

HERMES_HOME = get_hermes_home()

def load_env() -> dict:
    env = {}
    for path in [HERMES_HOME / ".env", Path.home() / ".hermes" / ".env"]:
        if path.exists():
            for line in path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    env[k.strip()] = v.strip()
    env.update(os.environ)
    return env

ENV              = load_env()
IDEOGRAM_KEY     = ENV.get("IDEOGRAM_API_KEY", "")
TELEGRAM_TOKEN   = ENV.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = ENV.get("TELEGRAM_CHAT_ID", "")

# KDP standard dimensions
KDP_W, KDP_H = 1600, 2560

# ── Font paths (priority order) ───────────────────────────────────────────────

FONT_BOLD = [
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]
FONT_REGULAR = [
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
]
FONT_LIGHT = [
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-L.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-ExtraLight.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]

# ── Niche → Visual Design Palettes ───────────────────────────────────────────
#
# bg_prompt: what Ideogram should generate (background only, no text)
# title_color: hex for the title text
# subtitle_color: hex for subtitle
# author_color: hex for author name
# accent: thin rule lines, decorative accents
# bg_dark: True = dark background (use light text), False = light bg (use dark text)

NICHE_PALETTES = {
    "productivity": {
        "keywords": ["productivity", "time management", "habits", "focus", "goals", "efficiency", "getting things done", "ADHD"],
        "bg_prompt": (
            "Translucent human head shown front-facing, cool steel blue-gray tones. "
            "Brain visible inside skull split into two halves: "
            "left side chaotic tangled neural threads in dark muted colors, "
            "right side glowing organized orange geometric neural network with bright nodes. "
            "Orange energy sparks radiating outward. Deep black background. "
            "Cinematic lighting, photorealistic CGI render, dramatic contrast. "
            "No text. Professional nonfiction book cover background."
        ),
        "title_color":    "#FFFFFF",
        "subtitle_color": "#FFD580",
        "author_color":   "#FFA040",
        "accent":         "#FF6B00",
        "bg_dark": True,
    },
    "health": {
        "keywords": ["health", "wellness", "gut", "sleep", "diet", "fitness", "nutrition", "weight", "fatigue"],
        "bg_prompt": (
            "Serene human body outline in translucent teal, glowing from within with warm light. "
            "Abstract organic flowing shapes representing biological systems — circular cells, "
            "gentle waves, botanical micro-details. Deep forest green to teal gradient background. "
            "Soft volumetric lighting, calm and healing atmosphere. "
            "No text. Professional nonfiction health book cover background."
        ),
        "title_color":    "#FFFFFF",
        "subtitle_color": "#B2EBE0",
        "author_color":   "#80CBC4",
        "accent":         "#00BFA5",
        "bg_dark": True,
    },
    "tech-security": {
        "keywords": ["security", "privacy", "network", "digital", "cyber", "hacking", "tech", "computer", "ai", "data"],
        "bg_prompt": (
            "Dark control room perspective: glowing circuit board patterns recede into deep space. "
            "Bright green and cyan data streams flow along geometric pathways. "
            "Central lock symbol radiates light outward against midnight blue black background. "
            "High contrast, sleek, cinematic tech aesthetic. "
            "No text. Professional cybersecurity nonfiction book cover background."
        ),
        "title_color":    "#00FF88",
        "subtitle_color": "#FFFFFF",
        "author_color":   "#80CBC4",
        "accent":         "#00FF88",
        "bg_dark": True,
    },
    "parenting": {
        "keywords": ["parenting", "children", "family", "kids", "baby", "toddler", "parent", "child"],
        "bg_prompt": (
            "Warm sunlit living room scene, soft bokeh background. "
            "Gentle golden light streaming through a window onto a cozy reading corner. "
            "Abstract warm shapes suggesting connection and growth — overlapping circles in "
            "amber, peach, and coral. Inviting, nurturing, joyful atmosphere. "
            "No text, no people visible. Professional parenting book cover background."
        ),
        "title_color":    "#3D2B1F",
        "subtitle_color": "#5D4037",
        "author_color":   "#4E342E",
        "accent":         "#FF6B35",
        "bg_dark": False,
    },
    "business": {
        "keywords": ["business", "money", "finance", "entrepreneur", "startup", "leadership", "management", "income"],
        "bg_prompt": (
            "Aerial perspective of a modern city at night, lights forming geometric grid patterns. "
            "Deep navy to midnight blue gradient. Golden light traces of movement suggesting "
            "commerce and flow. Sharp architectural lines, perspective vanishing point at center. "
            "Authoritative, sophisticated, high-stakes atmosphere. "
            "No text. Professional business nonfiction book cover background."
        ),
        "title_color":    "#FFFFFF",
        "subtitle_color": "#CFD8DC",
        "author_color":   "#90CAF9",
        "accent":         "#2196F3",
        "bg_dark": True,
    },
    "self-help": {
        "keywords": ["procrastination", "mindset", "motivation", "anxiety", "confidence", "success", "happiness", "stress"],
        "bg_prompt": (
            "Single beam of brilliant white-gold light breaking through dense storm clouds "
            "from above, illuminating a dramatic landscape below. "
            "Dark purple-blue storm above, warm golden light at the focal point. "
            "Rays radiating downward, volumetric god-rays effect. "
            "Inspiring, transformative, powerful visual metaphor for breakthrough. "
            "No text. Professional self-help nonfiction book cover background."
        ),
        "title_color":    "#FFFFFF",
        "subtitle_color": "#E1BEE7",
        "author_color":   "#CE93D8",
        "accent":         "#AB47BC",
        "bg_dark": True,
    },
    "default": {
        "keywords": [],
        "bg_prompt": (
            "Deep navy blue to dark gradient. "
            "Minimal subtle geometric shapes. "
            "Clean, professional, modern."
        ),
        "title_color":    "#FFFFFF",
        "subtitle_color": "#CFD8DC",
        "author_color":   "#B0C4DE",
        "accent":         "#4FC3F7",
        "bg_dark": True,
    },
}

# ── Logging ───────────────────────────────────────────────────────────────────

def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def die(msg: str):
    log(f"ERROR: {msg}")
    sys.exit(1)

# ── Niche detection ───────────────────────────────────────────────────────────

def detect_niche(meta: dict, niche_override: str | None = None) -> str:
    """
    Detect the best niche palette from metadata.
    Priority: explicit override > bisac_category > keyword matching in title/niche.
    """
    if niche_override:
        if niche_override in NICHE_PALETTES:
            return niche_override
        # Try partial match
        for key in NICHE_PALETTES:
            if niche_override.lower() in key:
                return key

    # BISAC-based detection
    bisac = meta.get("bisac_category", "").upper()
    bisac_map = {
        "HEA": "health", "FAM004": "parenting", "FAM": "parenting",
        "BUS": "business", "COM": "tech-security", "SEL016": "productivity",
        "SEL": "self-help", "PSY": "self-help",
    }
    for prefix, niche in bisac_map.items():
        if bisac.startswith(prefix):
            return niche

    # Keyword matching in title + subtitle
    title_text = (meta.get("title", "") + " " + meta.get("subtitle", "")).lower()
    for niche, data in NICHE_PALETTES.items():
        if niche == "default":
            continue
        if any(kw in title_text for kw in data["keywords"]):
            return niche

    return "default"

# ── Ideogram API ──────────────────────────────────────────────────────────────

def ideogram_generate(prompt: str, speed: str = "TURBO",
                       negative_prompt: str = "") -> bytes | None:
    """
    Generate background image via Ideogram API.
    Returns raw image bytes or None on failure.
    Speed: TURBO ($0.03) | DEFAULT ($0.06) | QUALITY ($0.09)
    """
    if not IDEOGRAM_KEY:
        die("IDEOGRAM_API_KEY not set in ~/.hermes/.env")

    log(f"  Ideogram generate ({speed})...")
    resp = requests.post(
        "https://api.ideogram.ai/v1/ideogram-v3/generate",
        headers={"Api-Key": IDEOGRAM_KEY},
        json={
            "prompt": prompt,
            "rendering_speed": speed,
            "aspect_ratio": "9x16",
            "style_type": "DESIGN",
            "num_images": 1,
            "magic_prompt": "OFF",
            "negative_prompt": negative_prompt or (
                "text, letters, words, numbers, title, author name, "
                "watermark, logo, busy, cluttered, photorealistic faces"
            ),
        },
        timeout=90,
    )
    if resp.status_code != 200:
        log(f"  Generate failed: {resp.status_code} — {resp.text[:200]}")
        return None

    img_url = resp.json()["data"][0]["url"]
    resolution = resp.json()["data"][0]["resolution"]
    log(f"  Generated at {resolution}")
    img_bytes = requests.get(img_url, timeout=30).content
    log(f"  Downloaded: {len(img_bytes):,} bytes")
    return img_bytes

def ideogram_upscale(img_bytes: bytes,
                      resemblance: int = 80,
                      detail: int = 70) -> bytes | None:
    """
    Upscale image via Ideogram API.
    Returns upscaled image bytes or None on failure.
    Cost: $0.06 flat.
    """
    log("  Ideogram upscale...")
    resp = requests.post(
        "https://api.ideogram.ai/upscale",
        headers={"Api-Key": IDEOGRAM_KEY},
        data={"image_request": json.dumps({
            "resemblance": resemblance,
            "detail": detail,
        })},
        files={"image_file": ("bg.png", img_bytes, "image/png")},
        timeout=120,
    )
    if resp.status_code != 200:
        log(f"  Upscale failed: {resp.status_code} — {resp.text[:200]}")
        return None

    up_url = resp.json()["data"][0]["url"]
    up_res = resp.json()["data"][0]["resolution"]
    up_bytes = requests.get(up_url, timeout=30).content
    log(f"  Upscaled to {up_res} — {len(up_bytes):,} bytes")
    return up_bytes

# ── Font helpers ──────────────────────────────────────────────────────────────

def get_font(size: int, weight: str = "bold") -> "ImageFont":
    paths = {"bold": FONT_BOLD, "regular": FONT_REGULAR, "light": FONT_LIGHT}
    for path in paths.get(weight, FONT_BOLD):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

def hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

# ── Text compositing ──────────────────────────────────────────────────────────

def wrap_text(draw: "ImageDraw", text: str, font: "ImageFont",
              max_width: int) -> list[str]:
    """Word-wrap text to fit within max_width pixels."""
    words = text.split()
    lines = []
    current = []
    for word in words:
        test = " ".join(current + [word])
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width or not current:
            current.append(word)
        else:
            lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines

def draw_text_block(draw: "ImageDraw", text: str, y: int, font: "ImageFont",
                     color: str, canvas_w: int = KDP_W,
                     max_w_ratio: float = 0.82,
                     line_spacing_ratio: float = 0.20,
                     shadow: bool = True,
                     shadow_offset: int = 4,
                     letter_spacing: int = 0) -> int:
    """
    Draw centered, wrapped text block. Returns the y position after the last line.
    """
    max_w = int(canvas_w * max_w_ratio)
    rgb = hex_to_rgb(color)
    shadow_rgb = tuple(max(0, c - 90) for c in rgb)
    lines = wrap_text(draw, text, font, max_w)
    line_gap = int(font.size * line_spacing_ratio)

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        line_h = bbox[3] - bbox[1]
        x = (canvas_w - line_w) // 2

        if shadow:
            draw.text((x + shadow_offset, y + shadow_offset),
                      line, font=font, fill=shadow_rgb)
        draw.text((x, y), line, font=font, fill=rgb)
        y += line_h + line_gap

    return y

def draw_rule(draw: "ImageDraw", y: int, accent_rgb: tuple,
               canvas_w: int = KDP_W, width_ratio: float = 0.55,
               thickness: int = 5) -> None:
    """Draw a thin centered horizontal accent line."""
    rule_w = int(canvas_w * width_ratio)
    x0 = (canvas_w - rule_w) // 2
    draw.rectangle([(x0, y), (x0 + rule_w, y + thickness)], fill=accent_rgb)

def add_vignette(canvas: "Image") -> "Image":
    """Add a subtle dark vignette to the edges for depth and to frame text."""
    vignette = Image.new("RGB", (KDP_W, KDP_H), (0, 0, 0))
    mask = Image.new("L", (KDP_W, KDP_H), 0)
    mask_draw = ImageDraw.Draw(mask)
    # Radial-ish vignette via gradient rectangles
    for i in range(120):
        alpha = int(180 * (1 - i / 120) ** 1.5)
        margin = i * 4
        if margin < KDP_W // 2 and margin < KDP_H // 2:
            mask_draw.rectangle(
                [(margin, margin), (KDP_W - margin, KDP_H - margin)],
                fill=alpha
            )
    # Invert: dark at edges, transparent in center
    mask = Image.fromarray(
        __import__("numpy", fromlist=[""]).array(mask).__class__(
            [255 - p for p in mask.tobytes()]
        ) if False else bytes([255 - b for b in mask.tobytes()]),
        "L"
    )
    canvas.paste(vignette, mask=mask)
    return canvas

def composite_cover(bg_bytes: bytes, meta: dict, palette: dict) -> "Image":
    """
    Composite text layers over the background image.
    Returns a PIL Image at exactly KDP_W x KDP_H.
    """
    if not PIL_AVAILABLE:
        die("Pillow not installed — run: pip install Pillow")

    title    = meta.get("title", "Untitled")
    subtitle = meta.get("subtitle", "")
    author   = meta.get("author", "")

    # Load and fit background to KDP canvas
    bg = Image.open(io.BytesIO(bg_bytes)).convert("RGB")
    bg_w, bg_h = bg.size

    # Scale to fill (cover) then center-crop
    scale = max(KDP_W / bg_w, KDP_H / bg_h)
    new_w = int(bg_w * scale)
    new_h = int(bg_h * scale)
    bg = bg.resize((new_w, new_h), Image.LANCZOS)
    # Center crop
    left = (new_w - KDP_W) // 2
    top  = (new_h - KDP_H) // 2
    bg = bg.crop((left, top, left + KDP_W, top + KDP_H))

    canvas = bg.copy()
    draw = ImageDraw.Draw(canvas)

    accent_rgb = hex_to_rgb(palette["accent"])

    # ── Dark overlay strips to ensure text readability ────────────────────────
    # Top overlay: gradient-ish via semi-transparent rectangles
    overlay = Image.new("RGBA", (KDP_W, KDP_H), (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    # Top strip (title area) — darkened
    for i in range(int(KDP_H * 0.55)):
        alpha = int(160 * max(0, 1 - (i / (KDP_H * 0.45)) ** 0.6))
        ov_draw.rectangle([(0, i), (KDP_W, i + 1)], fill=(0, 0, 0, alpha))
    # Bottom strip (author area)
    for i in range(int(KDP_H * 0.22)):
        y = KDP_H - 1 - i
        alpha = int(160 * max(0, 1 - (i / (KDP_H * 0.18)) ** 0.6))
        ov_draw.rectangle([(0, y), (KDP_W, y + 1)], fill=(0, 0, 0, alpha))

    canvas = canvas.convert("RGBA")
    canvas = Image.alpha_composite(canvas, overlay).convert("RGB")
    draw = ImageDraw.Draw(canvas)

    # ── Top accent rule ───────────────────────────────────────────────────────
    rule_top_y = int(KDP_H * 0.075)
    draw_rule(draw, rule_top_y, accent_rgb, thickness=7)

    # ── Title ─────────────────────────────────────────────────────────────────
    # Size the title dynamically: start large, reduce until it fits well
    title_font_size = 115
    title_y = int(KDP_H * 0.095)
    title_font = get_font(title_font_size)
    # Reduce font if title is long
    test_lines = wrap_text(draw, title.upper(), title_font, int(KDP_W * 0.82))
    if len(test_lines) > 3:
        title_font_size = 88
        title_font = get_font(title_font_size)
    elif len(test_lines) > 2:
        title_font_size = 100
        title_font = get_font(title_font_size)

    after_title = draw_text_block(
        draw, title.upper(), title_y, title_font,
        palette["title_color"],
        line_spacing_ratio=0.22,
        shadow=True, shadow_offset=5,
    )

    # ── Subtitle ──────────────────────────────────────────────────────────────
    if subtitle:
        sub_font_size = 54
        sub_y = after_title + 35
        sub_font = get_font(sub_font_size, weight="regular")
        # Reduce if very long
        sub_lines = wrap_text(draw, subtitle, sub_font, int(KDP_W * 0.78))
        if len(sub_lines) > 3:
            sub_font = get_font(44, weight="regular")

        draw_text_block(
            draw, subtitle, sub_y, sub_font,
            palette["subtitle_color"],
            max_w_ratio=0.78,
            line_spacing_ratio=0.18,
            shadow=True, shadow_offset=3,
        )

    # ── Bottom accent rule + author name ─────────────────────────────────────
    rule_bottom_y = int(KDP_H * 0.875)
    draw_rule(draw, rule_bottom_y, accent_rgb, width_ratio=0.45, thickness=5)

    author_font_size = 68
    author_y = int(KDP_H * 0.888)
    author_font = get_font(author_font_size)
    draw_text_block(
        draw, author.upper(), author_y, author_font,
        palette["author_color"],
        line_spacing_ratio=0.15,
        shadow=True, shadow_offset=3,
    )

    return canvas

# ── KDP border ────────────────────────────────────────────────────────────────

def add_kdp_border(canvas: "Image", palette: dict) -> "Image":
    """
    KDP requires a 3-4px border on light-background covers.
    Always add a subtle border for consistency.
    """
    if not palette.get("bg_dark", True):
        draw = ImageDraw.Draw(canvas)
        draw.rectangle(
            [(0, 0), (KDP_W - 1, KDP_H - 1)],
            outline=(150, 150, 150),
            width=4,
        )
    return canvas

# ── Save + validate ───────────────────────────────────────────────────────────

def save_cover(canvas: "Image", out_path: Path) -> dict:
    """Save as KDP-compliant JPEG. Returns stats dict."""
    # Ensure RGB (not RGBA)
    if canvas.mode != "RGB":
        canvas = canvas.convert("RGB")

    # Verify dimensions
    assert canvas.size == (KDP_W, KDP_H), f"Wrong size: {canvas.size}"

    # Save with quality tuned to stay under 5MB
    for quality in [92, 88, 85, 80]:
        buf = io.BytesIO()
        canvas.save(buf, "JPEG", quality=quality, optimize=True)
        size_kb = buf.tell() // 1024
        if size_kb < 4500:  # stay comfortably under 5MB
            break

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(str(out_path), "JPEG", quality=quality, optimize=True)
    file_size_kb = out_path.stat().st_size // 1024

    return {
        "path": str(out_path),
        "dimensions": f"{KDP_W}x{KDP_H}",
        "file_size_kb": file_size_kb,
        "quality": quality,
        "mode": canvas.mode,
    }

def save_thumbnail(canvas: "Image", out_path: Path) -> str:
    """Save 160x256 thumbnail for Telegram preview."""
    thumb = canvas.copy()
    thumb.thumbnail((160, 256), Image.LANCZOS)
    thumb.save(str(out_path), "JPEG", quality=85)
    return str(out_path)

# ── Telegram ──────────────────────────────────────────────────────────────────

def notify_telegram_with_image(msg: str, image_path: Path):
    """Send Telegram notification with cover thumbnail attached."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        # Send image
        with open(image_path, "rb") as f:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto",
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": msg, "parse_mode": "Markdown"},
                files={"photo": f},
                timeout=15,
            )
    except Exception as e:
        log(f"Telegram failed (non-fatal): {e}")
        # Fallback: text only
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"},
                timeout=10,
            )
        except Exception:
            pass

# ── Main flow ─────────────────────────────────────────────────────────────────

def build_background_prompt(palette: dict, meta: dict) -> str:
    """Build the full Ideogram prompt for the background layer."""
    title = meta.get("title", "")
    return (
        f"Minimalist professional nonfiction book cover background art. "
        f"{palette['bg_prompt']} "
        f"Abstract, elegant, modern design. "
        f"No text, no letters, no words, no numbers, no title. "
        f"Pure atmospheric background artwork only. "
        f"High quality, visually striking, suitable for a bestselling book."
    )

def generate_cover(meta: dict, book_dir: Path,
                   niche: str | None = None,
                   speed: str = "TURBO",
                   upscale: bool = True,
                   variation: int = 1,
                   dry_run: bool = False) -> dict | None:
    """
    Full cover generation pipeline for one variation.
    Returns dict with path, size, stats or None on failure.
    """
    palette = NICHE_PALETTES.get(detect_niche(meta, niche), NICHE_PALETTES["default"])
    detected_niche = detect_niche(meta, niche)

    log(f"Cover generation — niche: {detected_niche}, speed: {speed}, upscale: {upscale}")

    if dry_run:
        log(f"  [DRY RUN] Title:    {meta.get('title', '')}")
        log(f"  [DRY RUN] Author:   {meta.get('author', '')}")
        log(f"  [DRY RUN] Niche:    {detected_niche}")
        log(f"  [DRY RUN] Palette:  {palette['accent']} accent, bg_dark={palette['bg_dark']}")
        log(f"  [DRY RUN] BG prompt snippet: {palette['bg_prompt'][:80]}...")
        log(f"  [DRY RUN] Cost estimate: ${0.03 + (0.06 if upscale else 0):.2f}")
        return None

    # Step 1: Generate background
    bg_prompt = build_background_prompt(palette, meta)
    bg_bytes  = ideogram_generate(bg_prompt, speed=speed)
    if not bg_bytes:
        log("Background generation failed")
        return None

    # Step 2: Upscale (optional)
    if upscale:
        up_bytes = ideogram_upscale(bg_bytes, resemblance=80, detail=70)
        final_bg = up_bytes or bg_bytes  # fallback to original if upscale fails
    else:
        final_bg = bg_bytes

    # Step 3: Composite text layers
    log("Compositing text layers...")
    canvas = composite_cover(final_bg, meta, palette)
    canvas = add_kdp_border(canvas, palette)

    # Step 4: Save
    suffix   = f"-v{variation}" if variation > 1 else ""
    out_name = f"cover{suffix}.jpg"
    thumb_name = f"cover{suffix}-thumb.jpg"
    out_path   = book_dir / "output" / out_name
    thumb_path = book_dir / "output" / thumb_name

    stats = save_cover(canvas, out_path)
    save_thumbnail(canvas, thumb_path)

    log(f"  Saved: {out_path.name} — {stats['file_size_kb']} KB — {stats['dimensions']}")

    return {
        "cover_path": str(out_path),
        "thumb_path": str(thumb_path),
        "niche": detected_niche,
        "stats": stats,
    }

# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Ebook Factory Cover Generator — Ideogram API + Pillow compositing"
    )
    parser.add_argument("--book-dir", type=Path, default=None,
                        help="Workbook directory (auto-detects most recent if omitted)")
    parser.add_argument("--niche", default=None,
                        help="Force niche palette: productivity|health|tech-security|parenting|business|self-help")
    parser.add_argument("--quality", action="store_true",
                        help="Use QUALITY tier ($0.09) instead of TURBO ($0.03)")
    parser.add_argument("--no-upscale", action="store_true",
                        help="Skip upscale step (faster, 736x1312 base, still padded to 1600x2560)")
    parser.add_argument("--variations", type=int, default=1,
                        help="Generate N variations (1-4). Review the best one.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be generated — no API calls")
    args = parser.parse_args()

    if not PIL_AVAILABLE:
        die("Pillow not installed — run: pip install Pillow")

    # Find workbook
    if args.book_dir:
        book_dir = args.book_dir
    else:
        workbooks = HERMES_HOME / "ebook-factory" / "workbooks"
        dirs = sorted(workbooks.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        dirs = [d for d in dirs if d.is_dir()]
        if not dirs:
            die("No workbook directories found")
        book_dir = dirs[0]

    if not book_dir.exists():
        die(f"Book directory not found: {book_dir}")

    # Load metadata
    meta_path = book_dir / "output" / "kdp-metadata.json"
    if not meta_path.exists():
        die(f"kdp-metadata.json not found at {meta_path}")
    meta = json.loads(meta_path.read_text())
    log(f"Book: {meta.get('title', 'untitled')}")

    speed      = "QUALITY" if args.quality else "TURBO"
    upscale    = not args.no_upscale
    variations = max(1, min(4, args.variations))
    cost_each  = (0.06 if args.quality else 0.03) + (0.06 if upscale else 0)
    log(f"Generating {variations} variation(s) at ${cost_each:.2f} each = ${cost_each*variations:.2f} total")

    results = []
    for i in range(1, variations + 1):
        if variations > 1:
            log(f"\n── Variation {i}/{variations} ──")
        result = generate_cover(
            meta=meta,
            book_dir=book_dir,
            niche=args.niche,
            speed=speed,
            upscale=upscale,
            variation=i,
            dry_run=args.dry_run,
        )
        if result:
            results.append(result)
        if i < variations:
            time.sleep(1)  # brief pause between API calls

    if not results:
        if not args.dry_run:
            log("No covers generated successfully")
        return

    # Report
    log("\n" + "="*55)
    log(f"✅ Generated {len(results)} cover(s)")
    for r in results:
        log(f"   {Path(r['cover_path']).name} — {r['stats']['file_size_kb']} KB")
    if len(results) == 1:
        log(f"   Cover ready: {results[0]['cover_path']}")

    # Telegram notification with first cover thumbnail
    if results and not args.dry_run:
        title = meta.get("title", "Unknown")
        msg = (
            f"🎨 *Cover ready: {title}*\n\n"
            f"Niche: {results[0]['niche']} | Size: {results[0]['stats']['file_size_kb']} KB\n"
            f"{len(results)} variation(s) in output/ folder\n\n"
            f"Review covers and rename best one to `cover.jpg`\n"
            f"Then run KDP uploader."
        )
        notify_telegram_with_image(msg, Path(results[0]["thumb_path"]))
        log("Telegram notification sent with thumbnail")

if __name__ == "__main__":
    main()
