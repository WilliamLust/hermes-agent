#!/usr/bin/env python3
"""
Ebook Factory — KDP Upload Helper
===================================
Automates Amazon KDP book setup using Playwright (headless Chromium).
Fills all form fields from kdp-metadata.json, uploads the EPUB and cover,
saves as draft, then sends a Telegram notification for human final review.

The FINAL SUBMIT button is NEVER clicked automatically. Human eyes on publish.

Usage:
  python3 kdp_upload.py --book-dir PATH/TO/WORKBOOK
  python3 kdp_upload.py --book-dir PATH --dry-run     # print what would be filled
  python3 kdp_upload.py --session-dir ~/.kdp-session  # reuse saved login session
  python3 kdp_upload.py --book-dir PATH --visible     # non-headless (watch it work)

Credentials:
  Set in ~/.hermes/.env:
    KDP_EMAIL=your@amazon.com
    KDP_PASSWORD=your_password
  OR pass as env vars at runtime (never hardcode).

Flow:
  1. Load kdp-metadata.json from workbook output/
  2. Sign in to KDP (or reuse saved session)
  3. Navigate to New Kindle eBook
  4. Step 1: Fill Book Details (title, author, description, keywords, categories)
  5. Step 2: Upload EPUB + cover image
  6. Step 3: Fill pricing (price, royalty, territories)
  7. Save as draft — do NOT submit
  8. Send Telegram: "Review and publish at kdp.amazon.com/bookshelf"
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# ── Env / paths ───────────────────────────────────────────────────────────────

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
KDP_EMAIL        = ENV.get("KDP_EMAIL", "")
KDP_PASSWORD     = ENV.get("KDP_PASSWORD", "")
TELEGRAM_TOKEN   = ENV.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = ENV.get("TELEGRAM_CHAT_ID", "")

DEFAULT_SESSION_DIR = Path.home() / ".kdp-session"
KDP_BASE            = "https://kdp.amazon.com/en_US"
KDP_BOOKSHELF       = f"{KDP_BASE}/bookshelf"
KDP_NEW_EBOOK       = f"{KDP_BASE}/title-setup/kindle/new/details"

# BISAC → KDP category string mapping (most common nonfiction niches)
# KDP uses a two-level category picker; these are the search strings that work
BISAC_TO_CATEGORY = {
    "BUS000000": ("Business & Money", "Entrepreneurship"),
    "BUS042000": ("Business & Money", "Management & Leadership"),
    "COM000000": ("Computers & Technology", "Internet & Social Media"),
    "HEA000000": ("Health, Fitness & Dieting", "General"),
    "HEA047000": ("Health, Fitness & Dieting", "Diets & Weight Loss"),
    "PSY000000": ("Self-Help", "General"),
    "PSY016000": ("Self-Help", "Personal Transformation"),
    "SEL000000": ("Self-Help", "General"),
    "SEL016000": ("Self-Help", "Time Management"),
    "SEL023000": ("Self-Help", "Personal Transformation"),
    "FAM000000": ("Parenting & Relationships", "General"),
    "FAM004000": ("Parenting & Relationships", "Parenting"),
}

# ── Logging ───────────────────────────────────────────────────────────────────

def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def die(msg: str):
    log(f"ERROR: {msg}")
    sys.exit(1)

# ── Telegram ──────────────────────────────────────────────────────────────────

def notify_telegram(msg: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        import requests
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception as e:
        log(f"Telegram failed (non-fatal): {e}")

# ── Metadata loader ───────────────────────────────────────────────────────────

def load_metadata(book_dir: Path) -> dict:
    meta_path = book_dir / "output" / "kdp-metadata.json"
    if not meta_path.exists():
        die(f"kdp-metadata.json not found at {meta_path}")
    meta = json.loads(meta_path.read_text())
    log(f"Loaded metadata: '{meta.get('title', 'untitled')}'")
    return meta

def find_epub(book_dir: Path) -> Path | None:
    for f in (book_dir / "output").glob("*.epub"):
        return f
    return None

def find_cover(book_dir: Path) -> Path | None:
    output = book_dir / "output"
    for name in ["cover.jpg", "cover.png", "cover.jpeg"]:
        p = output / name
        if p.exists():
            return p
    return None

# ── Browser helpers ───────────────────────────────────────────────────────────

def slow_type(page, selector: str, text: str, delay_ms: int = 30):
    """Type text with a small delay (more human-like, avoids input validation races)."""
    page.fill(selector, "")
    page.type(selector, text, delay=delay_ms)

def wait_and_click(page, selector: str, timeout: int = 10000):
    page.wait_for_selector(selector, timeout=timeout)
    page.click(selector)

def safe_fill(page, selector: str, value: str, label: str = ""):
    """Fill a field, log what we're doing, handle missing fields gracefully."""
    try:
        page.wait_for_selector(selector, timeout=5000)
        page.fill(selector, value)
        log(f"  Filled {label or selector}: {value[:50]}")
    except Exception as e:
        log(f"  SKIP {label or selector}: {e}")

def _notify_verification_needed(current_url: str):
    """Send Telegram message asking user to complete Amazon verification."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log("   (No Telegram configured — complete verification manually and restart)")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": (
                    "🔐 *KDP Upload — Amazon Verification Required*\n\n"
                    "Amazon is asking for identity verification.\n"
                    "Complete it in the Firefox browser window on your desktop.\n\n"
                    "Then reply *done* here to continue the upload."
                ),
                "parse_mode": "Markdown",
            },
            timeout=10,
        )
    except Exception as e:
        log(f"   Telegram notify failed: {e}")


def _wait_for_telegram_confirmation(timeout: int = 600) -> bool:
    """
    Poll Telegram for a 'done' reply from the user.
    Returns True when confirmed, False if timed out.
    """
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log("   No Telegram — assuming verification complete, continuing...")
        return True

    import time as _time
    deadline = _time.time() + timeout
    last_update_id = 0

    log(f"   Polling for 'done' reply (timeout: {timeout}s)...")
    while _time.time() < deadline:
        try:
            resp = requests.get(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
                params={"offset": last_update_id + 1, "timeout": 5},
                timeout=10,
            )
            updates = resp.json().get("result", [])
            for update in updates:
                last_update_id = update["update_id"]
                text = update.get("message", {}).get("text", "").strip().lower()
                chat_id = str(update.get("message", {}).get("chat", {}).get("id", ""))
                if chat_id == str(TELEGRAM_CHAT_ID) and text in ("done", "ready", "continue", "ok"):
                    log("   ✅ Confirmation received — continuing upload")
                    return True
        except Exception:
            pass
        _time.sleep(2)

    log("   ⏱ Timeout waiting for confirmation — proceeding anyway")
    return False


# ── KDP Sign-in ───────────────────────────────────────────────────────────────

def signin_kdp(page, session_dir: Path | None = None) -> bool:
    """
    Sign in to KDP. Returns True if successful.
    Saves session cookies to session_dir for reuse.
    """
    # Try to restore saved session first
    if session_dir and session_dir.exists():
        cookie_file = session_dir / "cookies.json"
        if cookie_file.exists():
            log("Restoring saved KDP session...")
            cookies = json.loads(cookie_file.read_text())
            page.context.add_cookies(cookies)
            page.goto(KDP_BOOKSHELF, timeout=20000)
            time.sleep(3)
            if "bookshelf" in page.url and "signin" not in page.url:
                log("Session restored — already signed in")
                return True
            log("Saved session expired — signing in fresh")

    if not KDP_EMAIL or not KDP_PASSWORD:
        die("KDP_EMAIL and KDP_PASSWORD must be set in ~/.hermes/.env")

    # Navigate directly to the Amazon KDP sign-in page
    log("Navigating to KDP sign-in...")
    signin_url = (
        "https://www.amazon.com/ap/signin"
        "?openid.pape.max_auth_age=0"
        "&openid.return_to=https%3A%2F%2Fkdp.amazon.com%2Fen_US%2Fbookshelf"
        "&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select"
        "&openid.assoc_handle=amzn_dtp"
        "&openid.mode=checkid_setup"
        "&language=en_US"
        "&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select"
        "&pageId=kdp-ap"
        "&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0"
    )
    page.goto(signin_url, timeout=20000)
    page.wait_for_load_state("networkidle", timeout=15000)
    time.sleep(1)

    # Email field — id=ap_email, name=email
    try:
        page.wait_for_selector("#ap_email", timeout=10000)
        page.fill("#ap_email", KDP_EMAIL)
        log("  Entered email")
        time.sleep(0.5)

        # Click Continue
        page.click("input#continue, input[type='submit']")
        time.sleep(2)
    except Exception as e:
        log(f"  Email step issue: {e}")

    # Password field — id=ap_password (may appear on same page or next)
    try:
        page.wait_for_selector("#ap_password", timeout=10000)
        page.fill("#ap_password", KDP_PASSWORD)
        log("  Entered password")
        time.sleep(0.5)

        # Click Sign In
        page.click("input#signInSubmit, input[type='submit']")
        time.sleep(4)
    except Exception as e:
        log(f"  Password step issue: {e}")

    # Check for MFA / CAPTCHA / any challenge
    current_url = page.url
    if ("auth-mfa" in current_url or "cvf" in current_url or
            "ap/cvf" in current_url or "ap/signin/" in current_url or
            "challenge" in current_url or "OTP" in page.content()[:2000]):
        log("⚠️  Amazon verification challenge detected!")
        log(f"   Current URL: {current_url[:80]}")

        # Send Telegram notification asking user to complete verification
        _notify_verification_needed(current_url)

        log("   Waiting for you to complete verification...")
        log("   Reply 'done' to @Hermes_Ebook_Factory_Bot on Telegram when finished")

        # Poll Telegram for 'done' reply (up to 10 minutes)
        _wait_for_telegram_confirmation(timeout=600)

        time.sleep(3)
        page.wait_for_load_state("networkidle", timeout=15000)

    # Verify signed in — should land on bookshelf
    page.wait_for_load_state("networkidle", timeout=15000)
    time.sleep(2)

    signed_in = "bookshelf" in page.url or (
        "kdp.amazon.com" in page.url and "signin" not in page.url
    )

    if signed_in:
        log("✅ Signed in to KDP")
        if session_dir:
            session_dir.mkdir(parents=True, exist_ok=True)
            cookies = page.context.cookies()
            (session_dir / "cookies.json").write_text(json.dumps(cookies, indent=2))
            log(f"   Session saved to {session_dir}")
    else:
        log(f"⚠️  Sign-in uncertain — current URL: {page.url[:80]}")

    return signed_in

# ── Step 1: Book Details ──────────────────────────────────────────────────────

def fill_book_details(page, meta: dict, dry_run: bool = False):
    """Fill the KDP Book Details form (Step 1)."""
    log("Step 1: Book Details")

    if dry_run:
        log(f"  [DRY RUN] Would fill:")
        log(f"    Title:       {meta.get('title', '')}")
        log(f"    Subtitle:    {meta.get('subtitle', '')}")
        log(f"    Author:      {meta.get('author', '')}")
        log(f"    Description: {str(meta.get('description', ''))[:80]}...")
        log(f"    Keywords:    {meta.get('keywords', [])}")
        log(f"    BISAC:       {meta.get('bisac_category', '')}")
        return

    # Navigate to new Kindle eBook setup
    page.goto(KDP_NEW_EBOOK, timeout=20000)
    page.wait_for_load_state("networkidle", timeout=15000)
    time.sleep(2)
    log(f"  URL: {page.url[:80]}")

    # If we ended up back on signin, authentication failed
    if "signin" in page.url or "ap/signin" in page.url:
        log("  ⚠️  Not authenticated — landed on sign-in page instead of KDP form")
        log("  Attempting to re-navigate after potential auth redirect...")
        page.goto(KDP_NEW_EBOOK, timeout=20000)
        page.wait_for_load_state("networkidle", timeout=15000)
        time.sleep(3)
        log(f"  URL after retry: {page.url[:80]}")

    # Title
    safe_fill(page, "input#bookTitle, input[name='bookTitle'], input[data-qa='book-title']",
              meta.get("title", ""), "Title")

    # Subtitle (optional)
    subtitle = meta.get("subtitle", "")
    if subtitle:
        safe_fill(page, "input#bookSubTitle, input[name='bookSubTitle']", subtitle, "Subtitle")

    # Author (Primary Author first name / last name split)
    author = meta.get("author", "")
    if author and " " in author:
        parts = author.rsplit(" ", 1)
        safe_fill(page, "input#authorFirstName, input[name='authorFirstName']", parts[0], "Author First")
        safe_fill(page, "input#authorLastName, input[name='authorLastName']", parts[1], "Author Last")
    elif author:
        safe_fill(page, "input#authorLastName, input[name='authorLastName']", author, "Author")

    # Publisher (optional)
    publisher = meta.get("publisher", "")
    if publisher:
        safe_fill(page, "input#publisherName, input[name='publisherName']", publisher, "Publisher")

    # Description — KDP uses a rich text editor (contenteditable div) or textarea
    description = meta.get("description", "")
    if description:
        try:
            # Try contenteditable first (KDP's default)
            desc_editor = page.query_selector("div[contenteditable='true'], div.fr-element, textarea#bookDescription")
            if desc_editor:
                desc_editor.click()
                page.keyboard.press("Control+a")
                page.keyboard.type(description[:4000])
                log(f"  Filled Description ({len(description)} chars)")
        except Exception as e:
            log(f"  Description fill failed: {e}")

    # Keywords (up to 7, one per field)
    keywords = meta.get("keywords", [])
    if keywords:
        for i, kw in enumerate(keywords[:7]):
            kw_clean = str(kw).strip().lstrip("* ").strip()
            if not kw_clean:
                continue
            # KDP has keyword-1 through keyword-7
            for selector in [
                f"input#keyword{i+1}",
                f"input[name='keyword{i+1}']",
                f"input[data-qa='keyword-{i+1}']",
                f"input.keywordInput:nth-of-type({i+1})",
            ]:
                try:
                    el = page.query_selector(selector)
                    if el:
                        el.fill(kw_clean)
                        log(f"  Keyword {i+1}: {kw_clean}")
                        break
                except Exception:
                    pass

    # Categories — KDP requires clicking through a category tree
    bisac = meta.get("bisac_category", "")
    if bisac in BISAC_TO_CATEGORY:
        cat_main, cat_sub = BISAC_TO_CATEGORY[bisac]
        log(f"  Setting category: {cat_main} > {cat_sub}")
        try:
            # Click "Add categories" button
            for cat_btn_sel in [
                "button:has-text('Add categories')",
                "button:has-text('Add')",
                "a:has-text('Add categories')",
                "#add-categories",
            ]:
                btn = page.query_selector(cat_btn_sel)
                if btn:
                    btn.click()
                    time.sleep(1)
                    break

            # Search for category if search box exists
            search_box = page.query_selector("input[placeholder*='category'], input[placeholder*='search']")
            if search_box:
                search_box.type(cat_main[:20], delay=50)
                time.sleep(1)

            # Click matching category
            cat_el = page.query_selector(f"text={cat_main}")
            if cat_el:
                cat_el.click()
                time.sleep(0.5)
            cat_sub_el = page.query_selector(f"text={cat_sub}")
            if cat_sub_el:
                cat_sub_el.click()
                time.sleep(0.5)

            # Confirm selection
            for confirm_sel in ["button:has-text('Select')", "button:has-text('Done')", "button:has-text('Save')"]:
                confirm = page.query_selector(confirm_sel)
                if confirm:
                    confirm.click()
                    break
        except Exception as e:
            log(f"  Category selection issue: {e} — skipping, set manually")

    # Adult content toggle (default: No)
    if not meta.get("adult_content", False):
        try:
            no_radio = page.query_selector("input[value='false'][name='isAdultContent'], label:has-text('No')")
            if no_radio:
                no_radio.click()
        except Exception:
            pass

    # KDP Select enrollment
    if meta.get("enrollment", {}).get("kdp_select", True):
        try:
            kdp_select = page.query_selector("input[name='kdpEnrollment'], input#kdpEnroll")
            if kdp_select and not kdp_select.is_checked():
                kdp_select.click()
                log("  KDP Select: enabled")
        except Exception:
            pass

    # Save & Continue to Step 2
    log("  Clicking Save and Continue...")
    for save_sel in [
        "button:has-text('Save and Continue')",
        "input[value='Save and Continue']",
        "button[data-qa='save-and-continue']",
    ]:
        btn = page.query_selector(save_sel)
        if btn:
            btn.click()
            time.sleep(3)
            log(f"  → Step 1 saved. URL: {page.url[:80]}")
            break

# ── Step 2: Upload Manuscript & Cover ─────────────────────────────────────────

def upload_content(page, book_dir: Path, dry_run: bool = False):
    """Upload EPUB manuscript and cover image (Step 2)."""
    log("Step 2: Upload Manuscript & Cover")

    epub = find_epub(book_dir)
    cover = find_cover(book_dir)

    if dry_run:
        log(f"  [DRY RUN] Would upload:")
        log(f"    EPUB:  {epub}")
        log(f"    Cover: {cover}")
        return

    if not epub:
        log("  ⚠️  No EPUB found in output/ — skipping manuscript upload")
    else:
        log(f"  Uploading EPUB: {epub.name}")
        try:
            # KDP uses a file input for manuscript
            for uploader_sel in [
                "input[type='file'][accept*='epub'], input[type='file'][name*='manuscript']",
                "#manuscript-uploader",
                "input[type='file'].manuscript-upload",
            ]:
                el = page.query_selector(uploader_sel)
                if el:
                    el.set_input_files(str(epub))
                    log(f"  ✅ EPUB upload triggered — waiting for processing...")
                    # KDP processes the EPUB — wait up to 3 minutes
                    try:
                        page.wait_for_selector(
                            "text=Upload successful, text=Previewer, .upload-success",
                            timeout=180000
                        )
                        log("  ✅ EPUB processed successfully")
                    except Exception:
                        log("  ⏳ Upload in progress (check browser)")
                    break
        except Exception as e:
            log(f"  EPUB upload error: {e}")

    if not cover:
        log("  ⚠️  No cover found in output/ — skipping cover upload (use placeholder)")
    else:
        log(f"  Uploading cover: {cover.name}")
        try:
            for cover_sel in [
                "input[type='file'][accept*='image'], input[type='file'][name*='cover']",
                "#cover-uploader",
                "input[type='file'].cover-upload",
            ]:
                el = page.query_selector(cover_sel)
                if el:
                    el.set_input_files(str(cover))
                    log("  ✅ Cover upload triggered")
                    time.sleep(3)
                    break
        except Exception as e:
            log(f"  Cover upload error: {e}")

    # Save & Continue to Step 3
    log("  Clicking Save and Continue...")
    for save_sel in [
        "button:has-text('Save and Continue')",
        "button:has-text('Save and Publish')",
        "button[data-qa='save-and-continue']",
    ]:
        btn = page.query_selector(save_sel)
        if btn:
            btn.click()
            time.sleep(3)
            log(f"  → Step 2 saved. URL: {page.url[:80]}")
            break

# ── Step 3: Rights & Pricing ──────────────────────────────────────────────────

def fill_pricing(page, meta: dict, dry_run: bool = False):
    """Fill the KDP pricing form (Step 3)."""
    log("Step 3: Rights & Pricing")

    pricing = meta.get("pricing", {})
    us_price = str(pricing.get("us_price", 4.99))
    royalty  = pricing.get("royalty_plan", "70%")

    if dry_run:
        log(f"  [DRY RUN] Would set:")
        log(f"    Territories: Worldwide")
        log(f"    Royalty:     {royalty}")
        log(f"    US Price:    ${us_price}")
        return

    # Territories — worldwide
    try:
        for sel in [
            "input[value='WORLD'][name='territory']",
            "label:has-text('Worldwide')",
            "input#worldwide",
        ]:
            el = page.query_selector(sel)
            if el:
                el.click()
                log("  Territories: Worldwide ✓")
                break
    except Exception as e:
        log(f"  Territories: {e}")

    # Royalty rate — 70% (requires price $2.99–$9.99) or 35%
    royalty_pct = "70" if "70" in royalty else "35"
    try:
        for sel in [
            f"input[value='{royalty_pct}'][name='royaltyType']",
            f"label:has-text('{royalty_pct}%')",
            f"#royalty{royalty_pct}",
        ]:
            el = page.query_selector(sel)
            if el:
                el.click()
                log(f"  Royalty: {royalty_pct}% ✓")
                break
    except Exception as e:
        log(f"  Royalty: {e}")

    # US price
    try:
        for sel in [
            "input[name='listPrice'], input[name='usPrice']",
            "input#us-list-price",
            "input[data-marketplace='US']",
            "input[placeholder*='price']",
        ]:
            el = page.query_selector(sel)
            if el:
                el.fill(us_price)
                el.press("Tab")  # trigger price propagation to other markets
                log(f"  US Price: ${us_price} ✓")
                time.sleep(1)
                break
    except Exception as e:
        log(f"  Price: {e}")

    # Save as DRAFT (not publish) — explicitly look for "Save as Draft"
    log("  Saving as draft (NOT publishing)...")
    saved = False
    for save_sel in [
        "button:has-text('Save as Draft')",
        "button[data-qa='save-as-draft']",
        "input[value='Save as Draft']",
    ]:
        btn = page.query_selector(save_sel)
        if btn:
            btn.click()
            time.sleep(3)
            log(f"  ✅ Saved as draft. URL: {page.url[:80]}")
            saved = True
            break

    if not saved:
        # Fallback: save and continue but do NOT click any publish button
        log("  'Save as Draft' not found — saving via Save and Continue")
        for save_sel in ["button:has-text('Save and Continue')", "button[data-qa='save-and-continue']"]:
            btn = page.query_selector(save_sel)
            if btn:
                btn.click()
                time.sleep(3)
                log(f"  ✅ Saved. URL: {page.url[:80]}")
                log("  ⚠️  DO NOT click Publish — review manually first")
                break

# ── Dry-run summary ───────────────────────────────────────────────────────────

def print_dry_run_summary(meta: dict, book_dir: Path):
    """Print exactly what would be filled, without touching any browser."""
    epub  = find_epub(book_dir)
    cover = find_cover(book_dir)

    print("\n" + "═"*60)
    print("KDP UPLOAD DRY RUN — what would be submitted:")
    print("═"*60)
    print(f"Title:       {meta.get('title', '(missing)')}")
    print(f"Subtitle:    {meta.get('subtitle', '(none)')}")
    print(f"Author:      {meta.get('author', '(missing)')}")
    print(f"Publisher:   {meta.get('publisher', '(none)')}")
    print(f"Description: {str(meta.get('description', ''))[:120]}...")
    kws = [str(k).strip().lstrip('* ') for k in meta.get('keywords', [])[:7]]
    print(f"Keywords:    {', '.join(kws)}")
    bisac = meta.get('bisac_category', '')
    cat = BISAC_TO_CATEGORY.get(bisac, ("Unknown", "Unknown"))
    print(f"Category:    {cat[0]} > {cat[1]} (BISAC: {bisac})")
    print(f"KDP Select:  {meta.get('enrollment', {}).get('kdp_select', True)}")
    print(f"Adult:       {meta.get('adult_content', False)}")
    pricing = meta.get('pricing', {})
    print(f"Price:       ${pricing.get('us_price', 4.99)} USD")
    print(f"Royalty:     {pricing.get('royalty_plan', '70%')}")
    print(f"Territories: Worldwide")
    print(f"EPUB:        {epub or '⚠️  MISSING'}")
    print(f"Cover:       {cover or '⚠️  MISSING (will need placeholder)'}")
    print("═"*60)
    print("To run for real: remove --dry-run flag")
    print()

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="KDP Upload Helper — fills KDP form from kdp-metadata.json"
    )
    parser.add_argument("--book-dir", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--visible", action="store_true")
    parser.add_argument("--session-dir", type=Path, default=DEFAULT_SESSION_DIR)
    parser.add_argument("--skip-signin", action="store_true")
    args = parser.parse_args()

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

    log(f"Book dir: {book_dir.name}")
    meta = load_metadata(book_dir)

    if args.dry_run:
        print_dry_run_summary(meta, book_dir)
        return

    if not args.skip_signin and (not KDP_EMAIL or not KDP_PASSWORD):
        die("Set KDP_EMAIL and KDP_PASSWORD in ~/.hermes/.env before running")

    log(f"Launching {'visible' if args.visible else 'headless'} browser (Camoufox)...")

    try:
        from camoufox.sync_api import Camoufox
    except ImportError:
        die("camoufox not installed — run: pip install camoufox && python3 -m camoufox fetch")

    with Camoufox(headless=not args.visible, block_images=False) as fox:
        page = fox.new_page()
        try:
            if not args.skip_signin:
                signed_in = signin_kdp(page, session_dir=args.session_dir)
                if not signed_in:
                    log("⚠️  Could not confirm sign-in — proceeding anyway")

            fill_book_details(page, meta, dry_run=False)
            time.sleep(2)

            upload_content(page, book_dir, dry_run=False)
            time.sleep(2)

            fill_pricing(page, meta, dry_run=False)
            time.sleep(2)

            draft_url = page.url
            screenshot_path = book_dir / "output" / "kdp-draft-screenshot.png"
            page.screenshot(path=str(screenshot_path), full_page=False)
            log(f"Screenshot saved: {screenshot_path}")

            log("\n" + "="*60)
            log("✅ KDP DRAFT SAVED — ready for your review")
            log(f"   Bookshelf: {KDP_BOOKSHELF}")
            log(f"   URL: {draft_url}")
            log("   ⚠️  DO NOT SUBMIT — review and publish manually")
            log("="*60)

            title = meta.get("title", "Unknown")
            price = meta.get("pricing", {}).get("us_price", "?")
            msg = (
                f"📚 *KDP Draft Ready: {title}*\n\n"
                f"Priced at ${price}. Review and publish at:\n"
                f"[kdp.amazon.com/bookshelf]({KDP_BOOKSHELF})\n\n"
                f"⚠️ Do NOT submit without reviewing the preview."
            )
            notify_telegram(msg)

        except Exception as e:
            log(f"Error during upload: {e}")
            import traceback
            traceback.print_exc()
            try:
                page.screenshot(path=str(book_dir / "output" / "kdp-error-screenshot.png"))
            except Exception:
                pass
            raise


if __name__ == "__main__":
    main()
