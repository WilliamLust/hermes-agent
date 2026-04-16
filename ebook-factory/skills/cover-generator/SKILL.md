---
name: ebook-factory-cover-generator
category: ebook-factory
description: "Cover generator — Ideogram API for background art + Pillow for text compositing. Produces KDP-ready 1600x2560 JPEG covers at ~$0.09 each. Sends Telegram thumbnail preview."
tags: [ebook, cover, ideogram, pillow, kdp, image-generation]
version: 1.0
---

# Ebook Factory — Cover Generator

Generates KDP-ready book covers (1600x2560 JPEG, RGB, <5MB) using a two-layer architecture:

```
Layer 1: Ideogram API  →  background art, no text, ~5 seconds
Layer 2: Pillow        →  title + subtitle + author compositing, local, free
```

Cost per cover: **~$0.09** (TURBO $0.03 + upscale $0.06)

## Location
`~/.hermes/ebook-factory/skills/cover-generator/cover_generator.py`

## Setup

`IDEOGRAM_API_KEY` must be in `~/.hermes/.env` — already set.

```bash
pip install Pillow requests  # both already installed
```

## Usage

```bash
source ~/hermes-agent/venv/bin/activate
cd ~/.hermes/ebook-factory/skills/cover-generator/

# Standard run (auto-detects niche from BISAC + title keywords)
python3 cover_generator.py

# Force niche palette
python3 cover_generator.py --niche productivity
python3 cover_generator.py --niche health
python3 cover_generator.py --niche tech-security
python3 cover_generator.py --niche parenting
python3 cover_generator.py --niche business
python3 cover_generator.py --niche self-help

# Generate 3 variations, pick the best one
python3 cover_generator.py --variations 3

# Higher quality background ($0.06 generate + $0.06 upscale = $0.12)
python3 cover_generator.py --quality

# Skip upscale (faster, lower res base but still padded to 1600x2560)
python3 cover_generator.py --no-upscale

# See what would be generated without spending credits
python3 cover_generator.py --dry-run

# Specific workbook
python3 cover_generator.py --book-dir ~/.hermes/ebook-factory/workbooks/book-slug/
```

## Output

```
output/
├── cover.jpg          ← KDP-ready (1600x2560, RGB, <5MB)
└── cover-thumb.jpg    ← 160x256 thumbnail (sent to Telegram)
```

With `--variations 3`:
```
output/
├── cover-v1.jpg, cover-v1-thumb.jpg
├── cover-v2.jpg, cover-v2-thumb.jpg
└── cover-v3.jpg, cover-v3-thumb.jpg
```
Rename the best one to `cover.jpg` before running the KDP uploader.

## Niche Palettes

| Niche | Background | Title | Accent | Keywords |
|-------|-----------|-------|--------|---------|
| `productivity` | Orange→black, hexagons | White | Orange #FF6B00 | time, habits, focus, efficiency |
| `health` | Teal→forest green, botanical | White | Teal #00BFA5 | health, gut, sleep, nutrition |
| `tech-security` | Navy→charcoal, circuit grid | Green #00FF88 | Green | security, privacy, network, AI |
| `parenting` | Warm yellow→coral, soft bokeh | Dark brown | Coral #FF6B35 | parenting, children, family |
| `business` | Navy→slate, geometric | White | Blue #2196F3 | business, finance, leadership |
| `self-help` | Purple→indigo, light bloom | White | Purple #AB47BC | mindset, anxiety, motivation |
| `default` | Navy→dark, minimal | White | Blue #4FC3F7 | (fallback) |

## Architecture Decisions

**Why Ideogram for background, not text?**
- Full font control for catalog branding consistency
- Swap title/price/subtitle without regenerating the background
- Ideogram's text placement is creative not strategic — thumbnails need precision
- Pillow compositing is free, instant, and deterministic

**Why not Recraft V4 Pro ($0.25)?**
- Recraft Pro is 2.8x more expensive at $0.25/image
- Its main advantage is native 1664x2560 (vs 1472x2624 from Ideogram + upscale)
- The 64px width difference is handled by Pillow padding — not worth the cost
- At 5 books/month: Ideogram = $0.45, Recraft Pro = $1.25

**Why not Flux?**
- Flux has near-zero text rendering capability — completely wrong tool for covers
- Even for backgrounds, Ideogram's DESIGN style produces more cover-appropriate art

## KDP Compliance

| Requirement | Status |
|-------------|--------|
| Dimensions | ✅ 1600x2560 (exact) |
| Format | ✅ JPEG |
| Color space | ✅ RGB |
| File size | ✅ <5MB (typically 200-600 KB) |
| Resolution | ✅ At least 72 DPI (effectively 300+ at final size) |
| Gray border | ✅ Added automatically for light-background covers |
| AI disclosure | ⚠️ Must disclose AI-generated covers during KDP publishing |

## Known Limitations & How to Address Them

### Generic backgrounds
Ideogram's DESIGN style is conservative. For more distinctive backgrounds:
- Add specific visual metaphors to the prompt (a stopwatch for time management, a lock for security)
- Use `--quality` tier for more detailed generation
- Generate `--variations 3` and pick the most distinctive
- Edit the `bg_prompt` in NICHE_PALETTES for your specific book

### Font selection
The script uses Ubuntu-Bold (system font) — clean but not unique.
To use Google Fonts (Oswald, Montserrat, etc.):
```bash
# Download to ~/.hermes/ebook-factory/skills/cover-generator/fonts/
wget https://fonts.gstatic.com/s/oswald/v54/TK3_WkUHHAIjg75cFRf3bXL8LICs13Nv.ttf \
     -O ~/.hermes/ebook-factory/skills/cover-generator/fonts/Oswald-Bold.ttf
```
Then update FONT_BOLD in cover_generator.py to point to it.

### Text contrast
On some backgrounds, text contrast is insufficient. Fix by:
- Increasing the overlay opacity in `composite_cover()` (change `160` to `200`)
- Switching to a more contrasting title color in the palette
- Running `--variations 2` and picking the one with better contrast

### Title word-wrapping
Long titles may wrap awkwardly. The agent auto-reduces font size for long titles,
but you can also:
- Edit the title in kdp-metadata.json before running
- Adjust `title_font_size` in `generate_cover()` manually

## Pipeline Position

```
Packager output/ → cover_generator.py → output/cover.jpg → kdp_upload.py
```

The cover generator should run after the Packager (which creates kdp-metadata.json)
and before the KDP uploader (which uploads cover.jpg).

## Cost Tracking

At $0.09/cover (TURBO + upscale):
- 5 books/month = $0.45/month
- 10 books/month = $0.90/month
- 50 books/month = $4.50/month

The Ideogram API auto-tops up when balance drops below $10 (default setting).
Adjust the threshold in the Ideogram developer dashboard if needed.
