#!/usr/bin/env python3
"""
Packager Agent — Ebook Factory Phase 3
=======================================

Assembles all approved chapters from w-polished/ into a complete ebook package:
  - Full HTML manuscript
  - EPUB (via ebooklib)
  - PDF (via WeasyPrint, or fallback Calibre ebook-convert)
  - KDP metadata JSON
  - Front/back matter (title page, copyright, TOC, author bio, CTA)

Only runs after human review has approved chapters into w-polished/.

Usage:
    python3 packager.py
    python3 packager.py --book-dir ~/.hermes/ebook-factory/workbooks/book-my-topic/
    python3 packager.py --author "William Archer" --title "My Book Title"
    python3 packager.py --formats epub,pdf  # Comma-separated: epub, pdf, html

Reference: ~/hermes-agent/AGENTS.md section 6
"""

import os
import sys
import re
import json
import shutil
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================

HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
WORKBOOKS_DIR = HERMES_HOME / "ebook-factory" / "workbooks"
STYLE_GUIDE = Path.home() / "books" / "factory" / "style-guide.md"

DEFAULT_AUTHOR = "William Archer"
DEFAULT_LANGUAGE = "en"


# ============================================================================
# LOGGING
# ============================================================================

def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def log_section(title: str) -> None:
    print(f"\n{'='*60}", flush=True)
    print(f"  {title}", flush=True)
    print(f"{'='*60}", flush=True)


def error_exit(msg: str) -> None:
    print(f"\nERROR: {msg}", file=sys.stderr, flush=True)
    sys.exit(1)


# ============================================================================
# FILE I/O
# ============================================================================

def read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def write_file_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(content, encoding="utf-8")
    shutil.move(str(tmp), str(path))
    log(f"Written: {path}")


def find_latest_workbook() -> Path:
    if not WORKBOOKS_DIR.exists():
        error_exit(f"Workbooks directory not found: {WORKBOOKS_DIR}")
    books = [d for d in WORKBOOKS_DIR.iterdir() if d.is_dir() and d.name.startswith("book-")]
    if not books:
        error_exit("No workbooks found. Run outliner + chapter-builder first.")
    return sorted(books, key=lambda d: d.stat().st_mtime, reverse=True)[0]


# ============================================================================
# METADATA EXTRACTION
# ============================================================================

def extract_book_metadata(workbook_dir: Path, outline_path: Path, cli_args) -> dict:
    """
    Extract book metadata from outline and/or CLI args.
    Falls back to sensible defaults from the workbook dir name.
    """
    outline_content = read_file(outline_path) if outline_path.exists() else ""

    # Try to extract title from outline
    title = None
    title_match = re.search(r'^#\s+Book\s+Outline:\s*(.+)', outline_content, re.M)
    if title_match:
        title = title_match.group(1).strip()

    # CLI arg overrides
    if cli_args.title:
        title = cli_args.title

    if not title:
        # Derive from workbook dir name: "book-my-topic" -> "My Topic"
        slug = workbook_dir.name.replace("book-", "").replace("-", " ")
        title = slug.title()

    author = cli_args.author if cli_args.author else DEFAULT_AUTHOR
    slug = workbook_dir.name

    # Extract keywords from outline
    keywords = []
    kw_match = re.search(r'[Kk]eywords?[^:]*:\s*(.+)', outline_content)
    if kw_match:
        raw = kw_match.group(1).strip().strip("[]")
        keywords = [k.strip().strip("'\"") for k in raw.split(",") if k.strip()][:7]

    # Extract description from outline intro
    desc_match = re.search(r'(?:description|summary|about)[^:]*:\s*(.+?)(?:\n\n|\Z)', outline_content, re.I | re.DOTALL)
    description = desc_match.group(1).strip()[:200] if desc_match else f"A practical guide to {title}."

    return {
        "title": title,
        "author": author,
        "slug": slug,
        "language": DEFAULT_LANGUAGE,
        "description": description,
        "keywords": keywords,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "publisher": "William Archer",
        "rights": f"Copyright {datetime.now().year} {author}. All rights reserved.",
    }


# ============================================================================
# FRONT / BACK MATTER
# ============================================================================

def generate_title_page(meta: dict) -> str:
    return f"""<div class="title-page">
<h1 class="book-title">{meta['title']}</h1>
<p class="book-author">by {meta['author']}</p>
<p class="book-publisher">{meta['publisher']}</p>
<p class="book-date">{datetime.now().strftime('%Y')}</p>
</div>"""


def generate_copyright_page(meta: dict) -> str:
    return f"""<div class="copyright-page">
<p>{meta['rights']}</p>
<p>All rights reserved. No part of this publication may be reproduced, distributed,
or transmitted in any form or by any means, including photocopying, recording,
or other electronic or mechanical methods, without the prior written permission
of the publisher.</p>
<p>Published {meta['date']} by {meta['publisher']}</p>
</div>"""


def generate_author_bio(author: str) -> str:
    return f"""<div class="author-bio">
<h2>About the Author</h2>
<p>{author} is the author of multiple practical guides on productivity, health,
technology, and personal development. His books are designed to deliver real,
actionable information — no fluff, no filler, just results.</p>
<p>For more books and resources, search "{author}" on Amazon.</p>
</div>"""


def generate_cta(meta: dict, published_books: list) -> str:
    """Generate back-matter call-to-action listing other books."""
    books_html = ""
    for book in published_books[:5]:  # List up to 5 other books
        if book != meta["title"]:
            books_html += f'<li>{book}</li>\n'

    if not books_html:
        books_html = '<li>Search for more books by this author on Amazon</li>\n'

    return f"""<div class="also-by">
<h2>Also by {meta['author']}</h2>
<ul>
{books_html}
</ul>
<p>Find all books at: <strong>amazon.com/author/{meta['author'].lower().replace(' ', '')}</strong></p>
</div>"""


def generate_toc_html(chapters: list) -> str:
    """Generate HTML table of contents from chapter list."""
    items = ""
    for ch in chapters:
        items += f'<li><a href="#chapter-{ch["number"]:02d}">{ch["title"]}</a></li>\n'
    return f"""<div class="toc">
<h2>Table of Contents</h2>
<ol>
{items}
</ol>
</div>"""


# ============================================================================
# MARKDOWN TO HTML
# ============================================================================

def md_to_html(md_content: str, chapter_id: str = "") -> str:
    """
    Simple markdown-to-HTML converter.
    Handles: headings, bold, italic, lists, paragraphs, horizontal rules.
    Uses Python stdlib only — no external markdown library required.
    """
    # Strip validation report section (not for readers)
    md_content = re.sub(r'\n## Validation Report.*', '', md_content, flags=re.DOTALL)
    # Strip AUTO-GENERATED comment
    md_content = re.sub(r'<!--.*?-->', '', md_content, flags=re.DOTALL)

    lines = md_content.split("\n")
    html_lines = []
    in_list = False
    in_paragraph = False
    paragraph_lines = []

    def flush_paragraph():
        nonlocal in_paragraph, paragraph_lines
        if paragraph_lines:
            text = " ".join(paragraph_lines).strip()
            if text:
                html_lines.append(f"<p>{text}</p>")
        in_paragraph = False
        paragraph_lines = []

    def inline_format(text: str) -> str:
        # Bold
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        # Italic
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        # Code
        text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
        return text

    for line in lines:
        stripped = line.strip()

        # Close list if needed
        if in_list and not stripped.startswith(("- ", "* ", "+ ")) and not re.match(r'^\d+\.', stripped):
            html_lines.append("</ul>")
            in_list = False

        # Headings
        if stripped.startswith("# "):
            flush_paragraph()
            text = stripped[2:].strip()
            html_lines.append(f'<h1 id="{chapter_id}">{inline_format(text)}</h1>')
        elif stripped.startswith("## "):
            flush_paragraph()
            text = stripped[3:].strip()
            anchor = re.sub(r'[^a-z0-9]+', '-', text.lower())
            html_lines.append(f'<h2 id="{anchor}">{inline_format(text)}</h2>')
        elif stripped.startswith("### "):
            flush_paragraph()
            text = stripped[4:].strip()
            html_lines.append(f'<h3>{inline_format(text)}</h3>')
        elif stripped.startswith("#### "):
            flush_paragraph()
            text = stripped[5:].strip()
            html_lines.append(f'<h4>{inline_format(text)}</h4>')

        # Horizontal rule
        elif stripped in ("---", "***", "___"):
            flush_paragraph()
            html_lines.append("<hr/>")

        # Unordered list
        elif re.match(r'^[-*+]\s', stripped):
            if in_paragraph:
                flush_paragraph()
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            text = re.sub(r'^[-*+]\s', '', stripped)
            html_lines.append(f"<li>{inline_format(text)}</li>")

        # Ordered list
        elif re.match(r'^\d+\.\s', stripped):
            if in_paragraph:
                flush_paragraph()
            if not in_list:
                html_lines.append("<ol>")
                in_list = True
            text = re.sub(r'^\d+\.\s', '', stripped)
            html_lines.append(f"<li>{inline_format(text)}</li>")

        # Empty line — paragraph break
        elif not stripped:
            flush_paragraph()

        # Regular text — accumulate paragraph
        else:
            in_paragraph = True
            paragraph_lines.append(inline_format(stripped))

    # Close any open elements
    flush_paragraph()
    if in_list:
        html_lines.append("</ul>")

    return "\n".join(html_lines)


# ============================================================================
# CHAPTER LOADING
# ============================================================================

def load_polished_chapters(workbook_dir: Path) -> list:
    """
    Load all approved chapters from w-polished/.
    Returns list of dicts sorted by chapter number.
    """
    polished_dir = workbook_dir / "w-polished"

    if not polished_dir.exists():
        error_exit(f"w-polished/ directory not found: {polished_dir}\nComplete human review first.")

    chapter_files = sorted(polished_dir.glob("chapter-*.md"))

    if not chapter_files:
        error_exit(f"No approved chapters found in {polished_dir}\nMove approved chapters from w-drafts/ to w-polished/")

    chapters = []
    for path in chapter_files:
        content = read_file(path)

        # Extract chapter number from filename
        num_match = re.search(r'chapter-(\d+)\.md', path.name)
        num = int(num_match.group(1)) if num_match else 0

        # Extract title from first H1
        title_match = re.search(r'^#\s+Chapter\s+\d+:\s*(.+)', content, re.M)
        if not title_match:
            title_match = re.search(r'^#\s+(.+)', content, re.M)
        title = title_match.group(1).strip() if title_match else f"Chapter {num}"

        chapters.append({
            "number": num,
            "title": title,
            "content": content,
            "path": path,
        })

    chapters.sort(key=lambda c: c["number"])
    log(f"Loaded {len(chapters)} approved chapters")
    return chapters


# ============================================================================
# HTML MANUSCRIPT ASSEMBLY
# ============================================================================

CSS = """
body {
    font-family: Georgia, 'Times New Roman', serif;
    font-size: 11pt;
    line-height: 1.6;
    max-width: 650px;
    margin: 0 auto;
    padding: 20px;
    color: #1a1a1a;
}
h1, h2, h3, h4 { font-family: 'Helvetica Neue', Arial, sans-serif; }
h1 { font-size: 2em; margin-top: 2em; }
h2 { font-size: 1.4em; margin-top: 1.8em; border-bottom: 1px solid #ddd; padding-bottom: 4px; }
h3 { font-size: 1.1em; margin-top: 1.5em; }
p { margin: 0.8em 0; text-align: justify; }
ul, ol { margin: 0.8em 0 0.8em 1.5em; }
li { margin: 0.3em 0; }
strong { font-weight: bold; }
em { font-style: italic; }
hr { border: none; border-top: 1px solid #ccc; margin: 2em 0; }
code { font-family: monospace; background: #f5f5f5; padding: 2px 4px; border-radius: 2px; }
.title-page { text-align: center; page-break-after: always; padding: 4em 0; }
.book-title { font-size: 2.5em; margin-bottom: 0.5em; }
.book-author { font-size: 1.3em; color: #555; }
.copyright-page { font-size: 0.85em; color: #555; margin: 2em 0; page-break-after: always; }
.toc { page-break-after: always; }
.toc ol { line-height: 2; }
.author-bio, .also-by { page-break-before: always; margin-top: 2em; }
.chapter-break { page-break-before: always; }
"""


def assemble_html(meta: dict, chapters: list, published_books: list) -> str:
    """Assemble full manuscript as HTML."""
    body_parts = []

    # Front matter
    body_parts.append(generate_title_page(meta))
    body_parts.append('<div class="chapter-break"></div>')
    body_parts.append(generate_copyright_page(meta))
    body_parts.append('<div class="chapter-break"></div>')
    body_parts.append(generate_toc_html(chapters))
    body_parts.append('<div class="chapter-break"></div>')

    # Chapters
    for i, ch in enumerate(chapters):
        chapter_id = f"chapter-{ch['number']:02d}"
        chapter_html = md_to_html(ch["content"], chapter_id)
        div_class = "chapter-break" if i > 0 else ""
        body_parts.append(f'<div class="{div_class}" id="{chapter_id}">')
        body_parts.append(chapter_html)
        body_parts.append("</div>")

    # Back matter
    body_parts.append('<div class="chapter-break"></div>')
    body_parts.append(generate_author_bio(meta["author"]))
    body_parts.append(generate_cta(meta, published_books))

    body = "\n".join(body_parts)

    return f"""<!DOCTYPE html>
<html lang="{meta['language']}">
<head>
<meta charset="UTF-8"/>
<meta name="author" content="{meta['author']}"/>
<meta name="description" content="{meta['description']}"/>
<title>{meta['title']}</title>
<style>
{CSS}
</style>
</head>
<body>
{body}
</body>
</html>"""


# ============================================================================
# EPUB GENERATION
# ============================================================================

def build_epub(meta: dict, chapters: list, output_dir: Path) -> Path:
    """Build EPUB using ebooklib (if available) or ebook-convert (Calibre)."""

    epub_path = output_dir / f"{meta['slug']}.epub"

    # Try ebooklib first
    try:
        import ebooklib
        from ebooklib import epub

        book = epub.EpubBook()
        book.set_identifier(f"{meta['slug']}-{meta['date']}")
        book.set_title(meta["title"])
        book.set_language(meta["language"])
        book.add_author(meta["author"])

        # Add CSS
        css = epub.EpubItem(uid="style_nav", file_name="style/main.css",
                           media_type="text/css", content=CSS)
        book.add_item(css)

        # Add chapters
        epub_chapters = []
        for ch in chapters:
            chapter_id = f"chapter-{ch['number']:02d}"
            html_content = md_to_html(ch["content"], chapter_id)

            # Ensure content is non-empty for ebooklib
            if not html_content.strip():
                html_content = f"<p>{ch['title']}</p>"

            c = epub.EpubHtml(
                title=ch["title"],
                file_name=f"{chapter_id}.xhtml",
                lang=meta["language"],
            )
            c.content = f"""<?xml version='1.0' encoding='utf-8'?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>{ch['title']}</title>
<link rel="stylesheet" type="text/css" href="style/main.css"/>
</head>
<body>{html_content}</body></html>"""
            c.add_item(css)
            book.add_item(c)
            epub_chapters.append(c)

        book.toc = tuple(epub_chapters)
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ["nav"] + epub_chapters

        epub.write_epub(str(epub_path), book)
        log(f"EPUB built via ebooklib: {epub_path}")
        return epub_path

    except ImportError:
        log("ebooklib not found — trying ebook-convert (Calibre)")
    except Exception as e:
        log(f"ebooklib failed ({e}) — falling back to Calibre")

    # Fallback: Calibre ebook-convert
    html_path = output_dir / f"{meta['slug']}.html"
    if not html_path.exists():
        error_exit("HTML manuscript must be generated before EPUB via Calibre.")

    ebook_convert = shutil.which("ebook-convert")
    if not ebook_convert:
        log("WARNING: Neither ebooklib nor ebook-convert found. Skipping EPUB.")
        log("  To fix: pip install ebooklib  OR  sudo apt install calibre")
        return None

    cmd = [
        ebook_convert, str(html_path), str(epub_path),
        "--title", meta["title"],
        "--authors", meta["author"],
        "--language", meta["language"],
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log(f"WARNING: ebook-convert failed: {result.stderr[:200]}")
        return None

    log(f"EPUB built via Calibre: {epub_path}")
    return epub_path


# ============================================================================
# PDF GENERATION
# ============================================================================

def build_pdf(meta: dict, html_path: Path, output_dir: Path) -> Path:
    """Build PDF via WeasyPrint or Calibre fallback."""
    pdf_path = output_dir / f"{meta['slug']}.pdf"

    # Try WeasyPrint
    try:
        from weasyprint import HTML as WeasyHTML
        WeasyHTML(filename=str(html_path)).write_pdf(str(pdf_path))
        log(f"PDF built via WeasyPrint: {pdf_path}")
        return pdf_path
    except ImportError:
        log("weasyprint not found — trying ebook-convert")

    # Fallback: Calibre
    ebook_convert = shutil.which("ebook-convert")
    if not ebook_convert:
        log("WARNING: Neither weasyprint nor ebook-convert found. Skipping PDF.")
        log("  To fix: pip install weasyprint  OR  sudo apt install calibre")
        return None

    cmd = [
        ebook_convert, str(html_path), str(pdf_path),
        "--title", meta["title"],
        "--authors", meta["author"],
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log(f"WARNING: ebook-convert PDF failed: {result.stderr[:200]}")
        return None

    log(f"PDF built via Calibre: {pdf_path}")
    return pdf_path


# ============================================================================
# KDP METADATA
# ============================================================================

def build_kdp_metadata(meta: dict, chapters: list, output_dir: Path) -> Path:
    """Write KDP-ready metadata JSON."""

    # BISAC category mapping (basic heuristic)
    title_lower = meta["title"].lower()
    bisac = "SEL027000"  # SELF-HELP / Personal Growth / General (default)
    if any(w in title_lower for w in ["health", "fitness", "weight", "sleep", "fatigue"]):
        bisac = "HEA039000"  # HEALTH & FITNESS
    elif any(w in title_lower for w in ["finance", "money", "budget", "invest"]):
        bisac = "BUS050000"  # BUSINESS / Personal Finance
    elif any(w in title_lower for w in ["tech", "digital", "ai", "computer", "network", "privacy"]):
        bisac = "COM000000"  # COMPUTERS / General

    kdp_meta = {
        "title": meta["title"],
        "subtitle": "",
        "author": meta["author"],
        "description": meta["description"],
        "keywords": meta["keywords"],
        "language": meta["language"],
        "publisher": meta["publisher"],
        "publication_date": meta["date"],
        "bisac_category": bisac,
        "adult_content": False,
        "enrollment": {
            "kdp_select": True,
            "print_replica": False,
        },
        "pricing": {
            "us_price": 3.99,
            "royalty_plan": "70%",
        },
        "chapter_count": len(chapters),
        "word_count_estimate": sum(len(ch["content"].split()) for ch in chapters),
        "generated": datetime.now().isoformat(),
    }

    path = output_dir / "kdp-metadata.json"
    path.write_text(json.dumps(kdp_meta, indent=2, ensure_ascii=False))
    log(f"KDP metadata written: {path}")
    return path


# ============================================================================
# VALIDATION REPORT
# ============================================================================

def write_package_report(meta: dict, outputs: dict, chapters: list, output_dir: Path) -> None:
    """Write a package validation report."""
    total_words = sum(len(ch["content"].split()) for ch in chapters)
    lines = [
        f"# Package Report: {meta['title']}",
        f"<!-- AUTO-GENERATED: {datetime.now().isoformat(timespec='seconds')} -->",
        "",
        f"- Author: {meta['author']}",
        f"- Chapters: {len(chapters)}",
        f"- Total words: {total_words:,}",
        f"- Date: {meta['date']}",
        "",
        "## Output Files",
    ]

    for fmt, path in outputs.items():
        status = "✓" if path and Path(path).exists() else "✗ (not generated)"
        lines.append(f"- {fmt.upper()}: {path} {status}")

    lines += [
        "",
        "## Chapters Included",
    ]
    for ch in chapters:
        words = len(ch["content"].split())
        lines.append(f"- Chapter {ch['number']:02d}: {ch['title']} ({words:,} words)")

    lines += [
        "",
        "## Validation",
        f"- Chapter count: {len(chapters)} {'✓' if len(chapters) >= 10 else '✗ (expected 10-12)'}",
        f"- Total words: {total_words:,} {'✓' if total_words >= 20000 else '✗ (low)'}",
        "",
        "## Next Steps",
        "1. Review output/ files",
        "2. Check epub in Calibre or e-reader",
        "3. Upload to Amazon KDP (use kdp-metadata.json as reference)",
    ]

    report_path = output_dir / "package-report.md"
    report_path.write_text("\n".join(lines))
    log(f"Package report: {report_path}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Packager Agent — Ebook Factory Phase 3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 packager.py
  python3 packager.py --book-dir ~/.hermes/ebook-factory/workbooks/book-my-topic/
  python3 packager.py --author "William Archer" --title "My Book Title"
  python3 packager.py --formats epub,html
        """
    )
    parser.add_argument("--book-dir", type=str, default=None,
                        help="Workbook directory (auto-detects latest if not set)")
    parser.add_argument("--author", type=str, default=None,
                        help=f"Author name (default: {DEFAULT_AUTHOR})")
    parser.add_argument("--title", type=str, default=None,
                        help="Override book title")
    parser.add_argument("--formats", type=str, default="html,epub,pdf",
                        help="Comma-separated output formats: html,epub,pdf (default: all)")

    args = parser.parse_args()

    # Determine workbook
    if args.book_dir:
        workbook_dir = Path(args.book_dir)
        if not workbook_dir.exists():
            error_exit(f"Book directory not found: {workbook_dir}")
    else:
        workbook_dir = find_latest_workbook()
        log(f"Auto-detected workbook: {workbook_dir.name}")

    log(f"Packaging: {workbook_dir}")

    # Parse formats
    formats = [f.strip().lower() for f in args.formats.split(",")]

    # Paths
    outline_path = workbook_dir / "01_outline.md"
    output_dir = workbook_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get list of published books for CTA
    published_books = []
    pub_dir = Path.home() / "books" / "factory" / "references" / "published-books"
    if pub_dir.exists():
        for d in pub_dir.iterdir():
            if d.is_dir():
                # Extract book name from dir name "1. Book Title" -> "Book Title"
                name = re.sub(r'^\d+\.\s*', '', d.name)
                published_books.append(name)

    # Load metadata
    log_section("Step 1: Loading metadata")
    meta = extract_book_metadata(workbook_dir, outline_path, args)
    log(f"Title: {meta['title']}")
    log(f"Author: {meta['author']}")
    log(f"Keywords: {meta['keywords']}")

    # Load chapters
    log_section("Step 2: Loading approved chapters")
    chapters = load_polished_chapters(workbook_dir)
    for ch in chapters:
        words = len(ch["content"].split())
        log(f"  Chapter {ch['number']:02d}: {ch['title']} ({words:,} words)")

    outputs = {}

    # HTML
    if "html" in formats:
        log_section("Step 3: Assembling HTML manuscript")
        html = assemble_html(meta, chapters, published_books)
        html_path = output_dir / f"{meta['slug']}.html"
        write_file_atomic(html_path, html)
        outputs["html"] = html_path

    # EPUB
    if "epub" in formats:
        log_section("Step 4: Building EPUB")
        epub_path = build_epub(meta, chapters, output_dir)
        outputs["epub"] = epub_path

    # PDF
    if "pdf" in formats:
        log_section("Step 5: Building PDF")
        html_path = output_dir / f"{meta['slug']}.html"
        if html_path.exists():
            pdf_path = build_pdf(meta, html_path, output_dir)
            outputs["pdf"] = pdf_path
        else:
            log("WARNING: HTML not generated — skipping PDF")

    # KDP metadata
    log_section("Step 6: Writing KDP metadata")
    kdp_path = build_kdp_metadata(meta, chapters, output_dir)
    outputs["kdp-metadata"] = kdp_path

    # Package report
    log_section("Step 7: Writing package report")
    write_package_report(meta, outputs, chapters, output_dir)

    # Summary
    log_section("PACKAGING COMPLETE")
    total_words = sum(len(ch["content"].split()) for ch in chapters)
    log(f"Book: {meta['title']}")
    log(f"Chapters: {len(chapters)}")
    log(f"Total words: {total_words:,}")
    log(f"Output: {output_dir}")
    log("")
    log("Files:")
    for fmt, path in outputs.items():
        if path and Path(str(path)).exists():
            log(f"  ✓ {fmt}: {path}")
        elif path:
            log(f"  ✗ {fmt}: FAILED")
    log("")
    log("Next: Upload to Amazon KDP using output/kdp-metadata.json as reference.")
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.", flush=True)
        sys.exit(130)
