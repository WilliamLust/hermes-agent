#!/usr/bin/env python3
"""
KDP Cookie Setup — run this ONCE to save your KDP session.

This opens a real Firefox browser where you log into KDP manually.
After you log in successfully, press Enter in this terminal.
The session cookies are saved to ~/.kdp-session/cookies.json
and used by kdp_upload.py for all future uploads.

Usage:
    python3 setup_kdp_session.py
"""

import json
import time
import sys
from pathlib import Path

SESSION_DIR = Path.home() / ".kdp-session"
SESSION_DIR.mkdir(exist_ok=True)
COOKIE_FILE = SESSION_DIR / "cookies.json"

def main():
    print("KDP Session Setup")
    print("=" * 50)
    print()
    print("This will open a Firefox browser window.")
    print("Log into kdp.amazon.com manually.")
    print("Complete any verification Amazon asks for.")
    print("Once you see your KDP Bookshelf, come back here and press Enter.")
    print()

    try:
        from camoufox.sync_api import Camoufox
    except ImportError:
        print("ERROR: camoufox not installed")
        print("Run: pip install camoufox && python3 -m camoufox fetch")
        sys.exit(1)

    print("Opening Firefox...")
    with Camoufox(headless=False) as fox:
        page = fox.new_page()
        page.goto("https://kdp.amazon.com/en_US/", timeout=20000)
        
        print()
        print("Browser is open. Please:")
        print("  1. Click 'Sign in' on the KDP page")
        print("  2. Enter your Amazon email and password")
        print("  3. Complete any OTP / verification Amazon requires")
        print("  4. Wait until you see your KDP Bookshelf")
        print()
        
        # Wait for user confirmation
        try:
            input("Press Enter here once you're logged in and see your bookshelf... ")
        except EOFError:
            time.sleep(30)  # Fallback if stdin not available
        
        current_url = page.url
        print(f"Current URL: {current_url[:80]}")
        
        if "bookshelf" in current_url or "kdp.amazon.com" in current_url:
            # Save session
            cookies = page.context.cookies()
            COOKIE_FILE.write_text(json.dumps(cookies, indent=2))
            print(f"\n✅ Session saved to {COOKIE_FILE}")
            print(f"   {len(cookies)} cookies saved")
            print()
            print("You can now run:")
            print("  python3 kdp_upload.py --visible")
            print("  (It will reuse this saved session — no sign-in needed)")
        else:
            print(f"\n⚠️  Doesn't look like you're on KDP (URL: {current_url[:60]})")
            print("   Try again after confirming you're on kdp.amazon.com/en_US/bookshelf")

if __name__ == "__main__":
    main()
