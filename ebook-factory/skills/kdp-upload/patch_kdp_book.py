#!/usr/bin/env python3
"""
KDP Book Patcher — fills missing fields on an EXISTING KDP draft.

Usage:
    python3 patch_kdp_book.py --book-id A1CLFE136T01RN
    python3 patch_kdp_book.py --book-id A1CLFE136T01RN --dry-run

This script patches:
  - Description (via CKEditor iframe)
  - Keywords (all 7)
  - Cover image upload
  
It does NOT create a new book — it edits the existing draft.
"""

import json
import os
import sys
import time
import argparse
from pathlib import Path

import requests

def get_hermes_home() -> Path:
    try:
        from hermes_constants import get_hermes_home as _ghh
        return Path(_ghh())
    except ImportError:
        return Path.home() / ".hermes"

HERMES_HOME = get_hermes_home()
SESSION_FILE = Path.home() / ".kdp-session" / "cookies.json"

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

ENV = load_env()
TELEGRAM_TOKEN = ENV.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = ENV.get("TELEGRAM_CHAT_ID", "")

def log(msg):
    print(f"[{__import__('datetime').datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def notify(msg):
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"},
                timeout=10,
            )
        except Exception:
            pass


def patch_book(book_id: str, book_dir: Path, dry_run: bool = False):
    if not SESSION_FILE.exists():
        print("ERROR: No saved session. Run setup_kdp_session.py first.")
        sys.exit(1)

    # Load metadata
    meta_path = book_dir / "output" / "kdp-metadata.json"
    if not meta_path.exists():
        print(f"ERROR: {meta_path} not found")
        sys.exit(1)
    meta = json.loads(meta_path.read_text())

    description = meta.get("description", "")
    keywords    = [str(k).strip().lstrip("* ") for k in meta.get("keywords", [])[:7]]
    cover_path  = book_dir / "output" / "cover.jpg"

    print(f"\nPatching KDP book: {book_id}")
    print(f"  Description: {len(description)} chars")
    print(f"  Keywords:    {keywords}")
    print(f"  Cover:       {cover_path} ({'exists' if cover_path.exists() else 'MISSING'})")

    if dry_run:
        print("\n[DRY RUN] Would patch the above fields")
        return

    cookies = json.loads(SESSION_FILE.read_text())

    try:
        from camoufox.sync_api import Camoufox
    except ImportError:
        print("ERROR: camoufox not installed")
        sys.exit(1)

    details_url = f"https://kdp.amazon.com/en_US/title-setup/kindle/{book_id}/details"

    with Camoufox(headless=False) as fox:  # visible so user can see progress
        page = fox.new_page()
        page.context.add_cookies(cookies)
        page.goto(details_url, timeout=20000)
        page.wait_for_load_state("networkidle", timeout=15000)
        time.sleep(2)

        if "signin" in page.url:
            print("ERROR: Session expired. Run setup_kdp_session.py again.")
            sys.exit(1)

        log(f"On details page: {page.url[:60]}")

        # ── Fill Description ──────────────────────────────────────────────────
        if description:
            try:
                # CKEditor iframe
                cke = page.query_selector("iframe.cke_wysiwyg_frame")
                if cke:
                    frame = cke.content_frame()
                    body = frame.query_selector("body")
                    if body:
                        # Clear and set content
                        frame.evaluate(f"document.body.innerHTML = ''")
                        body.click()
                        # Type the description (CKEditor picks up keyboard events)
                        page.keyboard.type(description[:3900])
                        log(f"✓ Description filled via CKEditor ({len(description)} chars)")
                else:
                    # Try direct JS on the CKEditor instance
                    result = page.evaluate(f"""
                        (function() {{
                            for (var id in CKEDITOR.instances) {{
                                CKEDITOR.instances[id].setData({repr(description[:3900])});
                                return 'set via CKEDITOR API: ' + id;
                            }}
                            return 'no CKEDITOR instance found';
                        }})()
                    """)
                    log(f"✓ Description: {result}")
            except Exception as e:
                log(f"⚠️  Description fill failed: {e}")
        
        time.sleep(1)

        # ── Fill Keywords ─────────────────────────────────────────────────────
        filled_kw = 0
        for i, kw in enumerate(keywords):
            if not kw:
                continue
            sel = f"#data-keywords-{i}"
            try:
                el = page.query_selector(sel)
                if el:
                    el.fill(kw)
                    filled_kw += 1
            except Exception as e:
                log(f"  Keyword {i}: {e}")
        log(f"✓ Keywords filled: {filled_kw}/7")

        # ── Save Step 1 ───────────────────────────────────────────────────────
        log("Saving Step 1 (details)...")
        try:
            page.evaluate("document.getElementById('save-and-continue-announce').click()")
            time.sleep(4)
            log(f"  URL after save: {page.url[:70]}")
        except Exception as e:
            log(f"  Save failed: {e}")

        # ── Upload Cover (Step 2) ─────────────────────────────────────────────
        if cover_path.exists():
            log("Moving to content step for cover upload...")
            content_url = f"https://kdp.amazon.com/en_US/title-setup/kindle/{book_id}/content"
            page.goto(content_url, timeout=20000)
            page.wait_for_load_state("networkidle", timeout=15000)
            time.sleep(3)

            log(f"  Content URL: {page.url[:70]}")

            # Find cover upload input
            file_inputs = page.query_selector_all("input[type='file']")
            log(f"  File inputs on content page: {len(file_inputs)}")
            
            cover_uploaded = False
            for fi in file_inputs:
                accept = fi.get_attribute("accept") or ""
                if "image" in accept or "jpg" in accept or "jpeg" in accept:
                    fi.set_input_files(str(cover_path))
                    log(f"  ✓ Cover upload triggered")
                    cover_uploaded = True
                    time.sleep(5)
                    break

            if not cover_uploaded:
                # Try by position — cover input is usually the second file input
                # (first is manuscript)
                log("  ⚠️  Could not identify cover input by accept attr")
                log("  File inputs:")
                for fi in file_inputs:
                    log(f"    id='{fi.get_attribute('id')}' accept='{fi.get_attribute('accept')}'")

            # Save content step
            try:
                page.evaluate("document.getElementById('save-and-continue-announce').click()")
                time.sleep(4)
                log(f"  ✓ Content step saved. URL: {page.url[:70]}")
            except Exception as e:
                log(f"  Content save: {e}")

        # ── Final save as draft ───────────────────────────────────────────────
        log("Saving as draft...")
        try:
            page.evaluate("document.getElementById('save-announce').click()")
            time.sleep(3)
            log("✅ Saved as draft")
        except Exception as e:
            log(f"  Draft save: {e}")

        log("\nDone! Go to kdp.amazon.com/bookshelf to review and publish.")
        notify(
            f"📚 *KDP Book Patched*\n\n"
            f"Description, keywords, and cover upload attempted.\n"
            f"Review at: kdp.amazon.com/bookshelf"
        )

        # Brief pause so user can see final state
        time.sleep(3)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--book-id",  required=True, help="KDP book ID (e.g. A1CLFE136T01RN)")
    parser.add_argument("--book-dir", type=Path, default=None)
    parser.add_argument("--dry-run",  action="store_true")
    args = parser.parse_args()

    if args.book_dir:
        book_dir = args.book_dir
    else:
        workbooks = HERMES_HOME / "ebook-factory" / "workbooks"
        dirs = sorted(workbooks.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        dirs = [d for d in dirs if d.is_dir()]
        book_dir = dirs[0] if dirs else None

    if not book_dir or not book_dir.exists():
        print("ERROR: Could not find workbook directory")
        sys.exit(1)

    patch_book(args.book_id, book_dir, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
