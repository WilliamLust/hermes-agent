---
name: ebook-factory-kdp-upload
category: ebook-factory
description: "KDP Upload Helper — fills all KDP form fields from kdp-metadata.json, uploads EPUB + cover, saves draft. Never auto-submits. Sends Telegram when ready for human review."
tags: [ebook, kdp, upload, playwright, automation]
version: 1.0
---

# Ebook Factory — KDP Upload Helper

Automates Amazon KDP new title setup using Playwright (headless Chromium).
Fills every form field, uploads EPUB and cover, saves as draft.
The Publish button is NEVER clicked automatically — human review required.

## Location
`~/.hermes/ebook-factory/skills/kdp-upload/kdp_upload.py`

## Setup (one-time)

Add KDP credentials to `~/.hermes/.env`:
```
KDP_EMAIL=your@amazon.com
KDP_PASSWORD=yourpassword
```

These are only used locally. Never committed anywhere.

## Usage

```bash
source ~/hermes-agent/venv/bin/activate
cd ~/.hermes/ebook-factory/skills/kdp-upload/

# Dry run — see exactly what would be filled (no browser, no KDP)
python3 kdp_upload.py --dry-run

# Real run (headless — runs invisibly)
python3 kdp_upload.py

# Watch the automation (non-headless)
python3 kdp_upload.py --visible

# Target a specific workbook
python3 kdp_upload.py --book-dir ~/.hermes/ebook-factory/workbooks/book-slug/

# Reuse saved login session (faster — skips sign-in)
python3 kdp_upload.py --session-dir ~/.kdp-session
```

## What It Does

```
1. Load kdp-metadata.json from workbook/output/
2. Sign in to KDP (or restore saved session from ~/.kdp-session/)
3. Navigate to "Add new Kindle eBook"
4. Step 1 — Fill Book Details:
     Title, subtitle, author, publisher
     Description (up to 4000 chars)
     Keywords (up to 7)
     Category (from BISAC code mapping)
     KDP Select enrollment
     Adult content flag
5. Step 2 — Upload:
     EPUB manuscript (from output/*.epub)
     Cover image (from output/cover.jpg)
6. Step 3 — Pricing:
     Territories: Worldwide
     Royalty: 70% (or 35% if price outside $2.99-$9.99)
     US Price (from kdp-metadata.json pricing.us_price)
7. Save as Draft — NEVER PUBLISH
8. Screenshot saved to output/kdp-draft-screenshot.png
9. Telegram notification: "Review and publish at kdp.amazon.com/bookshelf"
```

## What It Does NOT Do

- Click "Publish" or "Submit for Review" — ever
- Set up print edition
- Handle A+ content
- Manage KDP ads

## Pipeline Position

```
Packager → output/
  ├── manuscript.epub
  ├── cover.jpg           ← from Ideogram (when ready)
  └── kdp-metadata.json
              ↓
         kdp_upload.py --visible
              ↓
         KDP Draft saved
              ↓
         Telegram: "Review at bookshelf"
              ↓
         William publishes manually
```

## Credentials & Session

Login session is saved to `~/.kdp-session/cookies.json` after first sign-in.
Subsequent runs reuse the saved session — no password prompt.
Sessions expire after ~30 days; delete the cookies.json to force re-login.

## MFA / CAPTCHA Handling

If Amazon triggers MFA or CAPTCHA during sign-in:
- Run with `--visible` to see the browser
- The script pauses and waits for you to complete verification manually
- Then presses Enter in the terminal to continue

## BISAC → KDP Category Mapping

Maintained in `BISAC_TO_CATEGORY` dict in the script. Current mappings:
```
COM000000 → Computers & Technology > Internet & Social Media
HEA000000 → Health, Fitness & Dieting > General
SEL016000 → Self-Help > Time Management
PSY016000 → Self-Help > Personal Transformation
FAM004000 → Parenting & Relationships > Parenting
BUS042000 → Business & Money > Management & Leadership
```
Add more as needed — KDP has ~300 Kindle categories.

## Known Pitfalls

- KDP UI changes frequently — field selectors may need updating
  → Run `--visible` to diagnose, patch selectors in the script
- Session cookies expire — delete `~/.kdp-session/cookies.json` to re-login
- EPUB processing takes 1-3 minutes — script waits up to 3 min
- Cover required for publishing — use Ideogram-generated cover or placeholder
- KDP Select and 70% royalty require specific price ranges ($2.99-$9.99)
- Description field uses a rich text editor (contenteditable div) on some accounts
  → If fill fails, description must be pasted manually
- After major Amazon UI updates: check field selectors still work with `--visible`
