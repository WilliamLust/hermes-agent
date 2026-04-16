---
name: ebook-factory-kdp-upload
category: ebook-factory
description: "KDP Upload Helper — fills title/description/keywords/cover on KDP. Saves as draft. Requires manual: EPUB upload, DRM, AI disclosure, categories, publish."
tags: [ebook, kdp, upload, camoufox, automation]
version: 1.1
---

# Ebook Factory — KDP Upload Helper

Automates the repetitive parts of KDP new title setup using Camoufox (anti-detect Firefox).
Saves a draft with all metadata filled. The EPUB, DRM, AI disclosure, and Publish are manual.

## Location
`~/.hermes/ebook-factory/skills/kdp-upload/kdp_upload.py`

## Honest Assessment

**At 5 books/month: just do it manually.** KDP sessions expire in hours,
requiring `setup_kdp_session.py` before each use. The tool saves ~5 min/book —
25 min/month — which may not justify the setup overhead at low volume.

**At 10+ books/month:** clearly worthwhile. Automation compounds.

## What It Does (Tested ✅)

| Field | Status |
|-------|--------|
| Title, Subtitle | ✅ |
| Author first/last name | ✅ |
| Description (CKEditor iframe) | ✅ |
| All 7 keywords | ✅ |
| Cover image upload | ✅ |
| Save as draft | ✅ |
| Session restore from cookies | ✅ |

## What Requires Manual Action in KDP

| Step | Field | Time |
|------|-------|------|
| Step 2 | EPUB manuscript upload | 30 sec |
| Step 2 | DRM selection (Yes) | 5 sec |
| Step 2 | AI content disclosure (Yes) | 5 sec |
| Step 1 | Categories (React modal) | 1-2 min |
| Step 3 | Pricing review | 30 sec |
| Step 3 | **Publish** (intentionally manual) | 5 sec |

Total manual work after the uploader runs: ~3-4 minutes.

## First-Time Setup (One-Time)

```bash
source ~/hermes-agent/venv/bin/activate
cd ~/.hermes/ebook-factory/skills/kdp-upload/
python3 setup_kdp_session.py
# Firefox opens — log in manually — press Enter when on Bookshelf
# Should save 14+ cookies
```

Session lasts a few hours. Re-run `setup_kdp_session.py` when it expires.

## Usage

```bash
source ~/hermes-agent/venv/bin/activate
cd ~/.hermes/ebook-factory/skills/kdp-upload/

# Dry run — preview what would be submitted
python3 kdp_upload.py --dry-run

# Real run (visible browser)
python3 kdp_upload.py --visible

# Specific workbook
python3 kdp_upload.py --visible --book-dir PATH/TO/WORKBOOK
```

## Patching an Existing Draft

To fill missing fields on an already-created draft (description, keywords, cover):

```bash
python3 patch_kdp_book.py --book-id A1CLFE136T01RN
# Get the book ID from the KDP URL when editing the draft
```

## Known Issues

- Session expires after a few hours → re-run `setup_kdp_session.py`
- Publisher field is hidden in KDP's form → skip, add manually if needed
- Categories modal uses React dynamic loading → not automated
- EPUB file input detection works on content page but depends on page variant
- If EPUB doesn't upload automatically, do it manually (30 seconds)
