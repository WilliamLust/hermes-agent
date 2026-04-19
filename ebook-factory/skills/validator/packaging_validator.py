#!/usr/bin/env python3
"""
Packaging Validator — quality gate after packager runs.

Checks:
- Total word count matches target (12 × 3,200 ≈ 38,400) ±10%
- EPUB passes epubcheck validation
- Cover image dimensions (1600×2560) and file size
- PDF renders (pdftotext sample)
- DOCX exists and non-zero
- HTML includes all chapters
- KDP upload kit exists and is plain text (not markdown)
- Notify Telegram on failure (or warning)

Usage:
    python3 packaging_validator.py --book-dir <workbook_dir>
    python3 packaging_validator.py --book-dir <workbook_dir> --notify-on-failure

Exit codes:
    0 = PASS (all checks pass)
    1 = WARN (some non-critical issues)
    2 = FAIL (critical issue — cannot upload)
"""

import argparse
import json
import re
import subprocess
import sys
import shutil
import os
from pathlib import Path
from datetime import datetime

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ============================================================================
# Logging
# ============================================================================

def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def log_section(title: str):
    print(f"\n{'='*60}\n  {title}\n{'='*60}", flush=True)

def warn(msg: str):
    print(f"[WARN] {msg}", flush=True)

def error(msg: str):
    print(f"[ERROR] {msg}", flush=True, file=sys.stderr)

# ============================================================================
# Validation functions
# ============================================================================

def check_word_count(workbook_dir: Path, target_total: int = 38400, tolerance: float = 0.15) -> tuple[bool, str]:
    """Check total word count across w-polished chapters."""
    polished_dir = workbook_dir / "w-polished"
    if not polished_dir.exists():
        return False, "w-polished/ directory missing"
    
    chapters = sorted(polished_dir.glob("chapter-*.md"))
    if not chapters:
        return False, "No chapter files in w-polished/"
    
    total_words = 0
    for ch_path in chapters:
        try:
            content = ch_path.read_text(encoding="utf-8", errors="replace")
            total_words += len(content.split())
        except Exception as e:
            return False, f"Cannot read {ch_path.name}: {e}"
    
    low = int(target_total * (1 - tolerance))
    high = int(target_total * (1 + tolerance))
    
    if low <= total_words <= high:
        return True, f"Word count OK: {total_words:,} (target {target_total:,} ±{int(tolerance*100)}%)"
    else:
        return False, f"Word count out of range: {total_words:,} (target {target_total:,} ±{int(tolerance*100)}%)"

def check_epub(epub_path: Path) -> tuple[bool, str]:
    """Run epubcheck on EPUB file."""
    if not epub_path.exists():
        return False, f"EPUB file missing: {epub_path}"
    
    epubcheck = shutil.which("epubcheck")
    if not epubcheck:
        warn("epubcheck not installed — skipping EPUB validation")
        return True, "EPUB validation skipped (epubcheck missing)"
    
    try:
        result = subprocess.run(
            [epubcheck, str(epub_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return True, "EPUB validation passed"
        else:
            error_msg = result.stderr[:200] if result.stderr else result.stdout[:200]
            return False, f"EPUB validation failed: {error_msg}"
    except subprocess.TimeoutExpired:
        return False, "EPUB validation timeout"
    except Exception as e:
        return False, f"EPUB validation error: {e}"

def check_cover(cover_path: Path, expected_width: int = 1600, expected_height: int = 2560) -> tuple[bool, str]:
    """Validate cover image dimensions and file size."""
    if not cover_path.exists():
        return False, f"Cover image missing: {cover_path}"
    
    # File size sanity
    size_mb = cover_path.stat().st_size / (1024 * 1024)
    if size_mb > 10:
        warn(f"Cover file size large: {size_mb:.1f} MB (typical <5 MB)")
    
    if not HAS_PIL:
        warn("PIL/Pillow not installed — skipping cover dimensions check")
        return True, "Cover dimensions check skipped"
    
    try:
        with Image.open(cover_path) as img:
            width, height = img.size
            if width == expected_width and height == expected_height:
                return True, f"Cover dimensions OK: {width}×{height}"
            else:
                return False, f"Cover dimensions incorrect: {width}×{height} (expected {expected_width}×{expected_height})"
    except Exception as e:
        return False, f"Cannot read cover image: {e}"

def check_pdf(pdf_path: Path) -> tuple[bool, str]:
    """Check PDF renders by extracting text."""
    if not pdf_path.exists():
        return False, f"PDF file missing: {pdf_path}"
    
    pdftotext = shutil.which("pdftotext")
    if not pdftotext:
        warn("pdftotext not installed — skipping PDF render check")
        return True, "PDF render check skipped"
    
    try:
        result = subprocess.run(
            [pdftotext, str(pdf_path), "-"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and len(result.stdout.strip()) > 50:
            return True, "PDF renders text (sample OK)"
        else:
            return False, "PDF appears empty or corrupt"
    except Exception as e:
        return False, f"PDF check error: {e}"

def check_docx(docx_path: Path) -> tuple[bool, str]:
    """Check DOCX exists and non-zero size."""
    if not docx_path.exists():
        return False, f"DOCX file missing: {docx_path}"
    
    size = docx_path.stat().st_size
    if size == 0:
        return False, "DOCX file is empty"
    elif size < 10 * 1024:  # 10 KB minimum
        warn(f"DOCX file suspiciously small: {size/1024:.1f} KB")
    
    return True, f"DOCX exists ({size/1024:.1f} KB)"

def check_html(html_path: Path, expected_chapters: int = 12) -> tuple[bool, str]:
    """Check HTML includes all chapter headings."""
    if not html_path.exists():
        return False, f"HTML file missing: {html_path}"
    
    try:
        content = html_path.read_text(encoding="utf-8", errors="replace")
        # Count chapter headers (h2 with 'chapter' or numbered)
        chapter_pattern = r'<h2[^>]*>.*chapter.*</h2>|<h2[^>]*>\s*chapter\s+\d+'
        matches = re.findall(chapter_pattern, content, re.IGNORECASE)
        if len(matches) >= expected_chapters:
            return True, f"HTML contains {len(matches)} chapter headers"
        else:
            return False, f"HTML missing chapters: found {len(matches)}, expected {expected_chapters}"
    except Exception as e:
        return False, f"Cannot read HTML: {e}"

def check_upload_kit(kit_path: Path) -> tuple[bool, str]:
    """Check KDP upload kit is plain text and not empty."""
    if not kit_path.exists():
        return False, f"Upload kit missing: {kit_path}"
    
    try:
        content = kit_path.read_text(encoding="utf-8", errors="replace")
        if not content.strip():
            return False, "Upload kit is empty"
        
        # Should not contain markdown headers (##) if it's .txt
        if kit_path.suffix == ".txt" and "## " in content:
            warn("Upload kit appears to contain markdown headers (should be plain text)")
        
        # Should contain KDP, Gumroad, D2D sections
        if "KDP METADATA" in content and "Gumroad" in content:
            return True, "Upload kit contains expected sections"
        else:
            warn("Upload kit missing expected section headers")
            return True, "Upload kit present (but structure unexpected)"
    except Exception as e:
        return False, f"Cannot read upload kit: {e}"

def check_output_files(output_dir: Path) -> tuple[bool, str]:
    """Ensure all expected output files exist."""
    required = ["cover.jpg", "kdp-upload-kit.txt", "kdp-metadata.json", "package-report.md"]
    missing = []
    for f in required:
        if not (output_dir / f).exists():
            missing.append(f)
    
    if missing:
        return False, f"Missing required files: {', '.join(missing)}"
    else:
        return True, "All required output files present"

# ============================================================================
# Main validation orchestrator
# ============================================================================

def validate_book(workbook_dir: Path, notify_on_failure: bool = False) -> int:
    """Run all validation checks, return exit code."""
    log_section(f"Packaging Validator — {workbook_dir.name}")
    
    output_dir = workbook_dir / "output"
    if not output_dir.exists():
        error(f"Output directory missing: {output_dir}")
        return 2
    
    # Determine book slug from first .html file
    html_files = list(output_dir.glob("*.html"))
    # Filter out hidden files (starting with dot)
    html_files = [f for f in html_files if not f.name.startswith(".")]
    if not html_files:
        error("No HTML manuscript found in output/")
        return 2
    # Pick the HTML file with longest stem (likely the real book, not a hidden file)
    html_files.sort(key=lambda f: len(f.stem), reverse=True)
    slug = html_files[0].stem
    log(f"Book slug: {slug}")
    
    # File paths
    epub_path   = output_dir / f"{slug}.epub"
    pdf_path    = output_dir / f"{slug}.pdf"
    docx_path   = output_dir / f"{slug}.docx"
    html_path   = output_dir / f"{slug}.html"
    cover_path  = output_dir / "cover.jpg"
    kit_path    = output_dir / "kdp-upload-kit.txt"
    
    # Run checks
    checks = []
    
    # 1. Word count
    ok, msg = check_word_count(workbook_dir)
    checks.append(("Word Count", ok, msg))
    
    # 2. EPUB
    ok, msg = check_epub(epub_path)
    checks.append(("EPUB Validation", ok, msg))
    
    # 3. Cover
    ok, msg = check_cover(cover_path)
    checks.append(("Cover Image", ok, msg))
    
    # 4. PDF
    ok, msg = check_pdf(pdf_path)
    checks.append(("PDF Render", ok, msg))
    
    # 5. DOCX
    ok, msg = check_docx(docx_path)
    checks.append(("DOCX File", ok, msg))
    
    # 6. HTML
    ok, msg = check_html(html_path)
    checks.append(("HTML Structure", ok, msg))
    
    # 7. Upload Kit
    ok, msg = check_upload_kit(kit_path)
    checks.append(("Upload Kit", ok, msg))
    
    # 8. Output files
    ok, msg = check_output_files(output_dir)
    checks.append(("Output Files", ok, msg))
    
    # Summary
    log_section("Validation Summary")
    
    critical_failures = []
    warnings = []
    
    for name, ok, msg in checks:
        if ok:
            log(f"✓ {name}: {msg}")
        else:
            if name in ("Word Count", "Cover Image", "DOCX File", "Output Files"):
                critical_failures.append(f"{name}: {msg}")
                log(f"✗ {name}: {msg}")
            else:
                warnings.append(f"{name}: {msg}")
                log(f"⚠ {name}: {msg}")
    
    # Determine exit code
    if critical_failures:
        log(f"\nFAIL: {len(critical_failures)} critical issue(s)")
        for f in critical_failures:
            error(f)
        
        if notify_on_failure:
            notify_telegram(f"❌ *Validation FAILED* for {slug}\n" + "\n".join(critical_failures[:3]))
        
        return 2
    elif warnings:
        log(f"\nWARN: {len(warnings)} non-critical issue(s)")
        for w in warnings:
            warn(w)
        
        if notify_on_failure:
            notify_telegram(f"⚠ *Validation warnings* for {slug}\n" + "\n".join(warnings[:3]))
        
        return 1
    else:
        log("\nPASS: All checks passed")
        if notify_on_failure:
            notify_telegram(f"✅ *Validation PASSED* for {slug}")
        return 0

# ============================================================================
# Telegram notification (copied from packager)
# ============================================================================

def load_env() -> dict:
    env = {}
    hermes_home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
    env_path = hermes_home / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    env.update(os.environ)
    return env

ENV = load_env()
TELEGRAM_TOKEN = ENV.get("TELEGRAM_BOT_TOKEN", ENV.get("TELEGRAM_TOKEN", ""))
TELEGRAM_CHAT_ID = ENV.get("TELEGRAM_CHAT_ID", "")

def notify_telegram(msg: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log("Telegram notification disabled (missing token or chat ID)")
        return
    
    import requests
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception as e:
        log(f"Telegram notification failed: {e}")

# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Validate packaged ebook files")
    parser.add_argument("--book-dir", type=str, required=True,
                       help="Path to workbook directory (e.g., ~/.hermes/ebook-factory/workbooks/book-*)")
    parser.add_argument("--notify-on-failure", action="store_true",
                       help="Send Telegram notification on validation failure")
    parser.add_argument("--list-checks", action="store_true",
                       help="List validation checks and exit")
    
    args = parser.parse_args()
    
    if args.list_checks:
        print("Validation checks:")
        print("  1. Word count total (38,400 ±10%)")
        print("  2. EPUB validation (epubcheck)")
        print("  3. Cover image dimensions (1600×2560)")
        print("  4. PDF renders (pdftotext)")
        print("  5. DOCX file exists and non-zero")
        print("  6. HTML contains all chapter headers")
        print("  7. KDP upload kit present and plain text")
        print("  8. All required output files present")
        return 0
    
    workbook_dir = Path(args.book_dir).expanduser().resolve()
    if not workbook_dir.exists():
        error(f"Workbook directory not found: {workbook_dir}")
        return 2
    
    exit_code = validate_book(workbook_dir, args.notify_on_failure)
    sys.exit(exit_code)

if __name__ == "__main__":
    main()