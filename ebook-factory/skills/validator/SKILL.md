---
name: ebook-validator
category: ebook-factory
description: "Packaging Validator — quality gate after packager runs. Checks word count, EPUB validation, cover dimensions, PDF render, DOCX existence, HTML structure, upload kit."
tags: [ebook, validator, quality, epubcheck, validation, phase-3]
version: 1.0
---

# Packaging Validator — SKILL.md

**Script:** `~/.hermes/ebook-factory/skills/validator/packaging_validator.py`

## Quick Start
```bash
cd ~/.hermes/ebook-factory/workbooks/book-your-topic/
python3 ~/.hermes/ebook-factory/skills/validator/packaging_validator.py --book-dir .
```

## Prerequisites
- `epubcheck` installed (for EPUB validation)
- PIL/Pillow (optional, for cover image validation)
- `pdftotext` (optional, for PDF sanity check)

## Usage
```bash
# Validate a book
python3 packaging_validator.py --book-dir <workbook_dir>

# Validate and notify on failure
python3 packaging_validator.py --book-dir <workbook_dir> --notify-on-failure

# Exit codes:
#   0 = PASS (all checks pass)
#   1 = WARN (some non-critical issues)
#   2 = FAIL (critical issue — cannot upload)
```

## Checks Performed
1. **Word Count**: Total words across w-polished chapters (target 38,400 ±15%)
2. **EPUB Validation**: Runs epubcheck on EPUB file (warning if fails)
3. **Cover Image**: Dimensions (1600×2560) and file size
4. **PDF Render**: Ensures PDF contains text (pdftotext sample)
5. **DOCX File**: Exists and non-zero size
6. **HTML Structure**: Verifies chapter count matches outline
7. **Upload Kit**: Contains expected sections (KDP, Gumroad, D2D)
8. **Output Files**: All required files present (cover.jpg, kdp-upload-kit.txt, etc.)

## Integration
Integrated into `run_pipeline.py` as Step 5 (after cover generator). Pipeline continues with warnings, halts on critical failures.

## See Also
- Full usage: load skill `ebook-agent-validator`
- Pipeline overview: load skill `walnut-agent-orchestrator`
- Master reference: `~/hermes-agent/AGENTS.md` section 6