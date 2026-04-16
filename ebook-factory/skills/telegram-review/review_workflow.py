#!/usr/bin/env python3
"""
Ebook Factory — Telegram Review Workflow
==========================================
Sends chapter draft summaries to Telegram for human review,
polls for approve/redo replies, and moves chapters accordingly.

Two modes:
  1. SEND   — push all w-drafts chapters to Telegram for review
  2. LISTEN — poll for replies and process approve/redo commands

Usage:
  python3 review_workflow.py --send   [--book-dir PATH]
  python3 review_workflow.py --listen [--book-dir PATH] [--timeout 3600]
  python3 review_workflow.py --status [--book-dir PATH]
  python3 review_workflow.py --send --listen [--book-dir PATH]  # send then listen

Telegram reply format (you send these from your phone):
  approve 1,2,3,5         → move chapters 1,2,3,5 to w-polished/
  approve all             → move all drafted chapters to w-polished/
  redo 4,6                → flag chapters 4,6 for regeneration
  status                  → bot replies with current chapter status
"""

import argparse
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# ── Constants ─────────────────────────────────────────────────────────────────

POLL_INTERVAL   = 5    # seconds between getUpdates calls
STATE_FILE_NAME = ".review_state.json"  # in book-dir

# ── Paths ──────────────────────────────────────────────────────────────────────

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

ENV             = load_env()
BOT_TOKEN       = ENV.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID         = ENV.get("TELEGRAM_CHAT_ID", "")
BASE_API        = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ── Logging ────────────────────────────────────────────────────────────────────

def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def die(msg: str):
    log(f"ERROR: {msg}")
    sys.exit(1)

# ── Telegram API ───────────────────────────────────────────────────────────────

def tg_send(text: str, parse_mode: str = "Markdown") -> dict:
    """Send message to the configured chat."""
    if not BOT_TOKEN or not CHAT_ID:
        log("WARNING: Telegram not configured — printing to console only")
        print(text)
        return {}
    resp = requests.post(
        f"{BASE_API}/sendMessage",
        json={"chat_id": CHAT_ID, "text": text, "parse_mode": parse_mode},
        timeout=15,
    )
    data = resp.json()
    if not data.get("ok"):
        log(f"Telegram send failed: {data.get('description', 'unknown error')}")
    return data

def tg_get_updates(offset: int = 0) -> list:
    """Poll for new messages from the bot."""
    resp = requests.get(
        f"{BASE_API}/getUpdates",
        params={"offset": offset, "timeout": POLL_INTERVAL, "allowed_updates": ["message"]},
        timeout=POLL_INTERVAL + 5,
    )
    data = resp.json()
    return data.get("result", [])

# ── Chapter discovery ──────────────────────────────────────────────────────────

def find_book_dir() -> Path:
    """Auto-detect the most recent workbook if not specified."""
    workbooks = HERMES_HOME / "ebook-factory" / "workbooks"
    if not workbooks.exists():
        die(f"No workbooks directory at {workbooks}")
    dirs = sorted(workbooks.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    dirs = [d for d in dirs if d.is_dir()]
    if not dirs:
        die("No workbook directories found")
    return dirs[0]

def get_drafts(book_dir: Path) -> list[dict]:
    """
    Find all chapter draft files. Supports naming conventions:
      w-drafts/chapter-NN.md
      02_chapter_NN.md  (old format, in book root)
      chapter-NN.md     (root)
    Returns sorted list of {num, path, word_count, has_validation, title}.
    """
    candidates = []

    # w-drafts/ subdirectory (canonical new format)
    drafts_dir = book_dir / "w-drafts"
    if drafts_dir.exists():
        candidates.extend(drafts_dir.glob("chapter-*.md"))
        candidates.extend(drafts_dir.glob("chapter_*.md"))

    # Root-level legacy naming (02_chapter_01.md etc.)
    for f in book_dir.glob("0*_chapter_*.md"):
        candidates.append(f)
    for f in book_dir.glob("chapter-*.md"):
        if f.parent == book_dir:
            candidates.append(f)

    chapters = []
    for path in candidates:
        num = extract_chapter_num(path.name)
        if num is None:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        word_count = len(text.split())
        # Extract title from first H1 or H2 heading
        title_m = re.search(r"^#+\s+(.+)$", text, re.MULTILINE)
        title = title_m.group(1).strip() if title_m else path.name
        # Check for validation section
        has_validation = "## Validation Report" in text or "Status:" in text
        # Check pass/fail
        passed = ("PASS" in text or "✓" in text) if has_validation else None

        chapters.append({
            "num": num,
            "path": path,
            "word_count": word_count,
            "title": title[:80],
            "has_validation": has_validation,
            "passed": passed,
        })

    chapters.sort(key=lambda c: c["num"])
    return chapters

def extract_chapter_num(filename: str) -> int | None:
    """Extract chapter number from filename."""
    m = re.search(r"(\d+)", filename)
    return int(m.group(1)) if m else None

def get_polished(book_dir: Path) -> set[int]:
    """Return set of chapter numbers already in w-polished/."""
    polished_dir = book_dir / "w-polished"
    if not polished_dir.exists():
        return set()
    nums = set()
    for f in polished_dir.glob("*.md"):
        n = extract_chapter_num(f.name)
        if n:
            nums.add(n)
    return nums

# ── State management ───────────────────────────────────────────────────────────

def load_state(book_dir: Path) -> dict:
    state_file = book_dir / STATE_FILE_NAME
    if state_file.exists():
        try:
            return json.loads(state_file.read_text())
        except Exception:
            pass
    return {"approved": [], "redo": [], "pending": [], "last_update_id": 0, "sent_at": None}

def save_state(book_dir: Path, state: dict):
    state_file = book_dir / STATE_FILE_NAME
    state_file.write_text(json.dumps(state, indent=2))

# ── SEND mode ─────────────────────────────────────────────────────────────────

def cmd_send(book_dir: Path):
    """Send chapter summaries to Telegram for review."""
    chapters = get_drafts(book_dir)
    polished = get_polished(book_dir)

    if not chapters:
        die(f"No draft chapters found in {book_dir}")

    pending = [c for c in chapters if c["num"] not in polished]

    if not pending:
        tg_send("✅ All chapters already approved — nothing to review.")
        return

    book_name = book_dir.name.replace("book-", "").replace("-", " ").title()
    header = (
        f"📚 *Chapter Review: {book_name}*\n"
        f"{len(pending)} chapter(s) ready for your review.\n\n"
        f"Reply with:\n"
        f"  `approve 1,2,3` — approve by number\n"
        f"  `approve all` — approve everything\n"
        f"  `redo 4,6` — flag for regeneration\n"
        f"  `status` — see current state\n"
    )
    tg_send(header)
    time.sleep(0.5)

    # Send one summary message per chapter
    for c in pending:
        # Read first ~200 words as preview
        text = c["path"].read_text(encoding="utf-8", errors="replace")
        # Strip markdown headers/meta for preview
        lines = [l for l in text.split("\n") if l.strip() and not l.startswith("#") and ":" not in l[:30]]
        preview_words = " ".join(" ".join(lines).split()[:60])
        if len(" ".join(lines).split()) > 60:
            preview_words += "..."

        validation_line = ""
        if c["has_validation"]:
            status = "✅ PASS" if c["passed"] else "⚠️ needs review"
            validation_line = f"\nValidation: {status}"

        msg = (
            f"*Chapter {c['num']}* — {c['title']}\n"
            f"Words: {c['word_count']:,}{validation_line}\n\n"
            f"_{preview_words}_"
        )
        tg_send(msg)
        time.sleep(0.3)

    # Update state
    state = load_state(book_dir)
    state["pending"] = [c["num"] for c in pending]
    state["sent_at"] = datetime.now().isoformat()
    save_state(book_dir, state)
    log(f"Sent {len(pending)} chapter summaries to Telegram")

# ── LISTEN mode ───────────────────────────────────────────────────────────────

def parse_chapter_nums(text: str) -> list[int]:
    """Parse '1,2,3' or '1 2 3' or 'all' from reply text."""
    if "all" in text.lower():
        return []  # special: means all pending
    nums = re.findall(r"\d+", text)
    return [int(n) for n in nums]

def move_to_polished(book_dir: Path, chapter_num: int) -> bool:
    """Move a chapter draft to w-polished/. Returns True if successful."""
    polished_dir = book_dir / "w-polished"
    polished_dir.mkdir(exist_ok=True)

    # Find the source file
    chapters = get_drafts(book_dir)
    chapter = next((c for c in chapters if c["num"] == chapter_num), None)
    if not chapter:
        log(f"Chapter {chapter_num} not found in drafts")
        return False

    dest = polished_dir / f"chapter-{chapter_num:02d}.md"
    shutil.copy2(chapter["path"], dest)
    log(f"Moved chapter {chapter_num} → w-polished/chapter-{chapter_num:02d}.md")
    return True

def process_reply(text: str, book_dir: Path, state: dict) -> str | None:
    """
    Process a Telegram reply. Returns response message or None.
    Mutates state in-place.
    """
    text = text.strip().lower()

    # STATUS
    if text.startswith("status"):
        chapters = get_drafts(book_dir)
        polished = get_polished(book_dir)
        pending = state.get("pending", [])
        approved = state.get("approved", [])
        redo = state.get("redo", [])

        lines = ["📊 *Chapter Status*\n"]
        for c in chapters:
            if c["num"] in polished:
                icon = "✅"
                label = "polished"
            elif c["num"] in approved:
                icon = "✅"
                label = "approved"
            elif c["num"] in redo:
                icon = "🔄"
                label = "redo queued"
            else:
                icon = "⏳"
                label = "pending review"
            lines.append(f"{icon} Ch {c['num']}: {c['title'][:40]} [{label}]")

        return "\n".join(lines)

    # APPROVE
    if text.startswith("approve"):
        nums = parse_chapter_nums(text)
        chapters = get_drafts(book_dir)
        pending = state.get("pending", [c["num"] for c in chapters])

        if not nums:  # "approve all"
            targets = pending
        else:
            targets = [n for n in nums if n in pending or True]  # allow approving any

        moved = []
        failed = []
        for n in targets:
            if move_to_polished(book_dir, n):
                moved.append(n)
                if n not in state["approved"]:
                    state["approved"].append(n)
                if n in state["pending"]:
                    state["pending"].remove(n)
            else:
                failed.append(n)

        polished = get_polished(book_dir)
        all_pending = [c["num"] for c in chapters]
        remaining = [n for n in all_pending if n not in polished]

        resp = f"✅ Approved chapters: {', '.join(str(n) for n in moved)}\n"
        if failed:
            resp += f"⚠️ Not found: {', '.join(str(n) for n in failed)}\n"
        if remaining:
            resp += f"\n⏳ Still pending: {', '.join(str(n) for n in remaining)}"
        else:
            resp += "\n🎉 All chapters approved! Ready to package."
            # Auto-trigger packager notification
            tg_send(
                "🚀 *All chapters approved!*\n\n"
                "Run packager to assemble the final book:\n"
                f"`cd ~/.hermes/ebook-factory/skills/packager/`\n"
                f"`python3 packager.py --book-dir {book_dir}`"
            )
        return resp

    # REDO
    if text.startswith("redo") or text.startswith("reject"):
        nums = parse_chapter_nums(text)
        if not nums:
            return "Please specify chapters: `redo 4,6`"

        for n in nums:
            if n not in state["redo"]:
                state["redo"].append(n)
            if n in state["approved"]:
                state["approved"].remove(n)

        resp = (
            f"🔄 Chapters flagged for regeneration: {', '.join(str(n) for n in nums)}\n\n"
            f"To regenerate:\n"
        )
        for n in nums:
            resp += f"`python3 chapter_builder.py --chapter {n} --force`\n"
        resp += "\nRun `send` again after regeneration to re-review."
        return resp

    return None  # unrecognized — ignore

def cmd_listen(book_dir: Path, timeout: int = 3600):
    """Poll Telegram for replies and process approve/redo commands."""
    log(f"Listening for Telegram replies (timeout: {timeout}s)...")
    tg_send("👂 Review bot is listening. Send `approve 1,2,3` or `redo 4` to manage chapters.")

    state = load_state(book_dir)
    last_update_id = state.get("last_update_id", 0)
    deadline = time.time() + timeout
    processed = 0

    while time.time() < deadline:
        try:
            updates = tg_get_updates(offset=last_update_id + 1)
        except Exception as e:
            log(f"getUpdates error: {e} — retrying in 10s")
            time.sleep(10)
            continue

        for update in updates:
            last_update_id = update["update_id"]
            msg = update.get("message", {})
            text = msg.get("text", "").strip()
            from_id = str(msg.get("chat", {}).get("id", ""))

            # Only process messages from our chat
            if from_id != str(CHAT_ID):
                continue

            if not text:
                continue

            log(f"Received: {text!r}")
            response = process_reply(text, book_dir, state)
            if response:
                tg_send(response)
                processed += 1
                save_state(book_dir, state)

        state["last_update_id"] = last_update_id
        save_state(book_dir, state)

        # Check if all done
        chapters = get_drafts(book_dir)
        polished = get_polished(book_dir)
        if chapters and all(c["num"] in polished for c in chapters):
            log("All chapters approved — exiting listener")
            break

        time.sleep(POLL_INTERVAL)

    log(f"Listener stopped. Processed {processed} commands.")

# ── STATUS mode ───────────────────────────────────────────────────────────────

def cmd_status(book_dir: Path):
    """Print chapter status to console."""
    chapters = get_drafts(book_dir)
    polished = get_polished(book_dir)
    state = load_state(book_dir)

    print(f"\nBook: {book_dir.name}")
    print(f"Drafts:   {len(chapters)} chapters")
    print(f"Polished: {len(polished)} chapters")
    print()

    for c in chapters:
        if c["num"] in polished:
            status = "✅ polished"
        elif c["num"] in state.get("approved", []):
            status = "✅ approved (not yet moved)"
        elif c["num"] in state.get("redo", []):
            status = "🔄 redo queued"
        else:
            status = "⏳ pending review"
        print(f"  Ch {c['num']:02d}: {c['title'][:55]:55s} {c['word_count']:5d}w  {status}")

    print()
    if state.get("sent_at"):
        print(f"Last sent: {state['sent_at']}")

# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Ebook Factory Telegram Review Workflow"
    )
    parser.add_argument("--send",    action="store_true", help="Send chapter summaries to Telegram")
    parser.add_argument("--listen",  action="store_true", help="Listen for approve/redo replies")
    parser.add_argument("--status",  action="store_true", help="Show chapter status")
    parser.add_argument("--book-dir", type=Path, default=None,
                        help="Path to workbook dir (auto-detects most recent if omitted)")
    parser.add_argument("--timeout", type=int, default=3600,
                        help="Listener timeout in seconds (default: 3600 = 1 hour)")
    args = parser.parse_args()

    if not BOT_TOKEN or not CHAT_ID:
        die("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in ~/.hermes/.env")

    book_dir = args.book_dir or find_book_dir()
    if not book_dir.exists():
        die(f"Book directory not found: {book_dir}")

    log(f"Working on: {book_dir.name}")

    if not args.send and not args.listen and not args.status:
        parser.print_help()
        sys.exit(0)

    if args.status:
        cmd_status(book_dir)

    if args.send:
        cmd_send(book_dir)

    if args.listen:
        cmd_listen(book_dir, timeout=args.timeout)

if __name__ == "__main__":
    main()
