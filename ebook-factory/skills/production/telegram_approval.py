#!/usr/bin/env python3
"""
Telegram approval gate for ebook factory.
Sends chapter summaries, waits for user approval/redo commands via Telegram.
"""

import os
import re
import json
import time
import logging
from pathlib import Path
from typing import List, Tuple, Optional, Dict
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Load environment
HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))

def load_env() -> dict:
    env = {}
    for p in [HERMES_HOME / ".env", Path.home() / ".hermes" / ".env"]:
        if p.exists():
            for line in p.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    env[k.strip()] = v.strip()
    env.update(os.environ)
    return env

ENV = load_env()
TELEGRAM_TOKEN = ENV.get("TELEGRAM_TOKEN", ENV.get("TELEGRAM_BOT_TOKEN", ""))
TELEGRAM_CHAT_ID = ENV.get("TELEGRAM_CHAT_ID", "")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in environment")

def send_message(text: str, parse_mode: str = "Markdown") -> Optional[int]:
    """Send a Telegram message, return message_id on success."""
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": parse_mode},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("result", {}).get("message_id")
    except Exception as e:
        logging.warning(f"Failed to send Telegram message: {e}")
        return None

def get_updates(offset: Optional[int] = None, timeout: int = 30) -> List[Dict]:
    """Poll Telegram for new messages."""
    params = {"timeout": timeout}
    if offset:
        params["offset"] = offset
    try:
        resp = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
            params=params,
            timeout=timeout + 5,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("result", [])
    except Exception as e:
        logging.warning(f"Failed to get Telegram updates: {e}")
        return []

def parse_approval_command(text: str) -> Tuple[List[int], List[int]]:
    """
    Extract approve and redo lists from a message like:
    'approve 1,2,3,5,7,8,9,10' and 'redo 4,6'
    Returns (approve_list, redo_list).
    """
    text = text.strip().lower()
    approve = []
    redo = []
    # Look for 'approve' pattern
    approve_match = re.search(r'approve\s+([\d,\s]+)', text)
    if approve_match:
        nums = approve_match.group(1).replace(' ', '').split(',')
        for n in nums:
            if n.isdigit():
                approve.append(int(n))
    # Look for 'redo' pattern
    redo_match = re.search(r'redo\s+([\d,\s]+)', text)
    if redo_match:
        nums = redo_match.group(1).replace(' ', '').split(',')
        for n in nums:
            if n.isdigit():
                redo.append(int(n))
    # Fallback: if only numbers, treat as approve
    if not approve and not redo:
        nums = re.findall(r'\b\d+\b', text)
        if nums:
            approve = [int(n) for n in nums]
    return approve, redo

def collect_chapter_status(workbook_dir: Path) -> List[Dict]:
    """Scan w-drafts/ for chapters, read validation report."""
    drafts_dir = workbook_dir / "w-drafts"
    if not drafts_dir.exists():
        return []
    chapters = []
    for path in sorted(drafts_dir.glob("chapter-*.md")):
        match = re.search(r'chapter-(\d+)\.md$', path.name)
        if not match:
            continue
        ch_num = int(match.group(1))
        content = path.read_text(encoding="utf-8", errors="ignore")
        # Extract validation report
        status = "UNKNOWN"
        word_count = len(content.split())
        if "## Validation Report" in content:
            report_section = content.split("## Validation Report")[-1]
            if "PASS" in report_section:
                status = "PASS"
            elif "WARN" in report_section:
                status = "WARN"
            elif "FAIL" in report_section:
                status = "FAIL"
        chapters.append({
            "number": ch_num,
            "path": path,
            "status": status,
            "word_count": word_count,
        })
    return chapters

def format_approval_message(book_title: str, chapters: List[Dict]) -> str:
    """Generate a readable summary for Telegram."""
    lines = [f"📚 *{book_title}*", "", "Chapters ready for review:"]
    for ch in chapters:
        lines.append(
            f"  {ch['number']:2d}. {'✅' if ch['status'] == 'PASS' else '⚠️' if ch['status'] == 'WARN' else '❓'} "
            f"{ch['word_count']} words"
        )
    lines.extend([
        "",
        "To approve, reply with:",
        "`approve 1,2,3,5,7,8,9,10`",
        "`redo 4,6`",
        "",
        "Or reply `auto` to auto‑approve all.",
        "Timeout: 24h (will auto‑approve)."
    ])
    return "\n".join(lines)

def poll_for_approval(
    start_offset: Optional[int] = None,
    timeout_seconds: int = 86400,
    poll_interval: int = 30,
) -> Tuple[List[int], List[int], bool]:
    """
    Wait for user approval command.
    Returns (approve_list, redo_list, auto_approved).
    If timeout or 'auto' command, returns all chapters approved, empty redo, auto_approved=True.
    """
    offset = start_offset
    start = time.time()
    while time.time() - start < timeout_seconds:
        updates = get_updates(offset, timeout=poll_interval)
        for update in updates:
            offset = update["update_id"] + 1
            if "message" in update and "text" in update["message"]:
                text = update["message"]["text"].strip()
                if text.lower() == "auto":
                    return [], [], True  # auto‑approve all
                approve, redo = parse_approval_command(text)
                if approve or redo:
                    return approve, redo, False
        # small sleep to avoid tight loop
        time.sleep(2)
    # Timeout: auto‑approve all
    return [], [], True

def move_approved_chapters(workbook_dir: Path, approve_list: List[int]):
    """Copy approved chapters from w-drafts/ to w-polished/."""
    drafts_dir = workbook_dir / "w-drafts"
    polished_dir = workbook_dir / "w-polished"
    polished_dir.mkdir(parents=True, exist_ok=True)
    moved = []
    for ch in approve_list:
        src = drafts_dir / f"chapter-{ch:02d}.md"
        dest = polished_dir / f"chapter-{ch:02d}.md"
        if src.exists():
            import shutil
            shutil.copy2(src, dest)
            moved.append(ch)
    return moved

def run_redo_chapters(workbook_dir: Path, redo_list: List[int], python_cmd: str) -> bool:
    """Re‑run chapter‑builder for specified chapters."""
    if not redo_list:
        return True
    from subprocess import Popen
    procs = []
    chapter_builder_script = HERMES_HOME / "ebook-factory" / "skills" / "chapter-builder" / "chapter_builder.py"
    for ch in redo_list:
        cmd = [python_cmd, str(chapter_builder_script),
               "--chapter", str(ch), "--book-dir", str(workbook_dir), "--force"]
        procs.append((ch, Popen(cmd)))
    failed = []
    for ch, p in procs:
        try:
            p.wait(timeout=1800)
            if p.returncode != 0:
                failed.append(ch)
        except Exception:
            p.kill()
            failed.append(ch)
    return len(failed) == 0

def human_review_gate(workbook_dir: Path, book_title: str, python_cmd: str, auto: bool = False) -> bool:
    """
    Main human review gate.
    If auto=True, auto‑promote all drafts and return True.
    Otherwise, send Telegram summary, wait for approval, process, loop until all approved.
    """
    if auto:
        chapters = collect_chapter_status(workbook_dir)
        approve_all = [ch["number"] for ch in chapters]
        moved = move_approved_chapters(workbook_dir, approve_all)
        logging.info(f"Auto‑promoted {len(moved)} chapters.")
        return True

    # Ensure Telegram credentials
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logging.error("Telegram credentials missing. Cannot proceed with human review.")
        return False

    # Loop until all chapters approved
    while True:
        chapters = collect_chapter_status(workbook_dir)
        if not chapters:
            logging.warning("No chapters found in w-drafts/.")
            return False

        # Send summary
        msg = format_approval_message(book_title, chapters)
        msg_id = send_message(msg)
        if not msg_id:
            logging.error("Failed to send approval request.")
            return False

        # Poll for response
        approve, redo, auto_approved = poll_for_approval(timeout_seconds=86400)
        if auto_approved:
            # Auto‑approve all
            approve_all = [ch["number"] for ch in chapters]
            moved = move_approved_chapters(workbook_dir, approve_all)
            logging.info(f"Auto‑approved {len(moved)} chapters (timeout or 'auto' command).")
            return True

        # Move approved chapters
        moved = move_approved_chapters(workbook_dir, approve)
        logging.info(f"Moved {len(moved)} approved chapters to w-polished/.")

        # Re‑run redos
        if redo:
            success = run_redo_chapters(workbook_dir, redo, python_cmd)
            if not success:
                logging.warning(f"Failed to re‑run some chapters: {redo}")
            # After redo, loop again (new drafts will be considered)
            continue

        # If no redo chapters left, we're done
        if not redo:
            return True

def main():
    import sys
    if len(sys.argv) < 3:
        print("Usage: python telegram_approval.py <workbook_dir> <book_title> [--auto]")
        sys.exit(1)
    wb = Path(sys.argv[1])
    title = sys.argv[2]
    auto_flag = "--auto" in sys.argv
    try:
        success = human_review_gate(wb, title, sys.executable, auto=auto_flag)
        sys.exit(0 if success else 1)
    except Exception as e:
        logging.error(f"Human review gate failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()