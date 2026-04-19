#!/usr/bin/env python3
"""
Ebook Factory — Telegram Topic Approval
=========================================
Sends candidate topics from topic_plan_latest.md to Telegram,
listens for a numbered reply, appends the chosen topic to
approved_topics.md, and optionally starts the pipeline.

Usage:
  python3 topic_approval.py --send              # Send topics to Telegram
  python3 topic_approval.py --listen            # Listen for reply (number)
  python3 topic_approval.py --send --listen     # Send then listen
  python3 topic_approval.py --auto-pick 1       # Skip Telegram, pick by number
  python3 topic_approval.py --status            # Show current topic plan
  python3 topic_approval.py --list-queue        # Show approved queue

Telegram reply format:
  1, 2, 3     → Pick topic by number — auto-queues AND auto-starts the pipeline
  new topics  → Re-send the topic list (re-runs planner first)

Auto-start: When a topic is selected (by number), the pipeline starts automatically.
No separate "run" command needed. Selection = execution.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# ── Paths ──────────────────────────────────────────────────────────────────────

HERMES_HOME      = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
FACTORY_DIR      = Path.home() / "books" / "factory"
APPROVED_TOPICS  = FACTORY_DIR / "approved_topics.md"
TOPIC_PLAN_LATEST = HERMES_HOME / "output" / "planner" / "topic_plan_latest.md"
SKILLS_BASE      = HERMES_HOME / "ebook-factory" / "skills"
PIPELINE_SCRIPT  = SKILLS_BASE / "production" / "run_pipeline.py"
PLANNER_SCRIPT   = HERMES_HOME / "hermes_skills" / "planner" / "topic_pipeline.py"

VENV_PYTHON      = Path.home() / "hermes-agent" / "venv" / "bin" / "python3"
PYTHON           = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable

POLL_INTERVAL    = 5
STATE_FILE       = HERMES_HOME / "ebook-factory" / ".topic_approval_state.json"

# ── Env / Telegram ─────────────────────────────────────────────────────────────

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

ENV              = load_env()
BOT_TOKEN        = ENV.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID          = ENV.get("TELEGRAM_CHAT_ID", "")
BASE_API         = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ── Logging ────────────────────────────────────────────────────────────────────

def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def die(msg: str):
    log(f"ERROR: {msg}")
    tg_send(f"❌ *Topic Approval Error*\n{msg}")
    sys.exit(1)

# ── Telegram API ───────────────────────────────────────────────────────────────

def tg_send(text: str, parse_mode: str = "Markdown") -> dict:
    if not BOT_TOKEN or not CHAT_ID:
        log("WARNING: Telegram not configured — printing to console only")
        print(text)
        return {}
    try:
        resp = requests.post(
            f"{BASE_API}/sendMessage",
            json={"chat_id": CHAT_ID, "text": text, "parse_mode": parse_mode},
            timeout=15,
        )
        data = resp.json()
        if not data.get("ok"):
            log(f"Telegram send failed: {data.get('description', 'unknown')}")
        return data
    except Exception as e:
        log(f"Telegram send error: {e}")
        return {}

def tg_get_updates(offset: int = 0) -> list:
    try:
        resp = requests.get(
            f"{BASE_API}/getUpdates",
            params={"offset": offset, "timeout": POLL_INTERVAL, "allowed_updates": ["message"]},
            timeout=POLL_INTERVAL + 5,
        )
        return resp.json().get("result", [])
    except Exception as e:
        log(f"getUpdates error: {e}")
        return []

# ── Topic plan parsing ─────────────────────────────────────────────────────────

def parse_topic_plan(path: Path) -> list[dict]:
    """
    Extract candidate topics from topic_plan_latest.md.
    Parses the 'Top 3 Priorities' section for rich data (niche, score, signal),
    then adds any new titles from 'All Candidates Ranked' that weren't in Top 3.
    Returns list of {num, title, niche, score, signal} — deduplicated, numbered 1..N.
    """
    if not path.exists():
        return []

    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    topics = []
    seen_titles = set()

    # Phase 1: Parse "Top N Priorities" section — has niche/score/signal
    in_priorities = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if re.search(r'Top \d+ Priorit', line):
            in_priorities = True
            i += 1
            continue
        if in_priorities and line.startswith("---"):
            break

        if in_priorities:
            m = re.match(r'^(\d+)\.\s+\*\*(.+?)\*\*', line)
            if m:
                title = m.group(2).strip()
                seen_titles.add(title.lower())
                niche, score, signal = "", "", ""
                for j in range(i + 1, min(i + 6, len(lines))):
                    niche_m = re.search(r'Niche:\s*`(.+?)`', lines[j])
                    if niche_m:
                        niche = niche_m.group(1)
                    score_m = re.search(r'Score:\s*([\d.]+)', lines[j])
                    if score_m:
                        score = score_m.group(1)
                    signal_m = re.search(r'Market signal:\s*(.+)', lines[j])
                    if signal_m:
                        signal = signal_m.group(1).strip()
                topics.append({
                    "num": 0,  # renumbered below
                    "title": title,
                    "niche": niche,
                    "score": score,
                    "signal": signal,
                })
        i += 1

    # Phase 2: Parse "All Candidates Ranked" — add titles not already captured
    in_ranked = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if "All Candidates Ranked" in line:
            in_ranked = True
            i += 1
            continue
        if in_ranked and line.startswith("---"):
            break

        if in_ranked:
            m = re.match(r'^(\d+)\.\s+\*\*(.+?)\*\*', line)
            if m:
                title = m.group(2).strip()
                # Fuzzy dedup: check if any existing title contains this as prefix
                is_dup = any(
                    title.lower() == existing.lower() or
                    existing.lower().startswith(title.lower()) or
                    title.lower().startswith(existing.lower())
                    for existing in seen_titles
                )
                if not is_dup:
                    seen_titles.add(title.lower())
                    topics.append({
                        "num": 0,
                        "title": title,
                        "niche": "",
                        "score": "",
                        "signal": "",
                    })
        i += 1

    # Renumber sequentially
    for idx, t in enumerate(topics, 1):
        t["num"] = idx

    return topics

def parse_niche_from_title(title: str) -> str:
    """Best-effort niche extraction from title keywords."""
    t = title.lower()
    if any(w in t for w in ["gut", "inflammation", "sleep", "fatigue", "metabolic", "health"]):
        return "health"
    if any(w in t for w in ["security", "privacy", "network", "protecting"]):
        return "tech-security"
    if any(w in t for w in ["adhd", "procrastination", "productivity", "time block", "focus", "async"]):
        return "productivity"
    if any(w in t for w in ["ai", "algorithmic", "digital", "parenting", "family", "minimalism"]):
        return "self-help"
    return "self-help"

# ── State management ───────────────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"last_update_id": 0, "topics_sent": [], "sent_at": None}

def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))

# ── Approved topics management ─────────────────────────────────────────────────

def append_to_approved(topic: dict):
    """Append a topic to approved_topics.md."""
    APPROVED_TOPICS.parent.mkdir(parents=True, exist_ok=True)

    # Read existing content
    if APPROVED_TOPICS.exists():
        content = APPROVED_TOPICS.read_text(encoding="utf-8")
    else:
        content = (
            "# Approved Topic Queue\n"
            "# =====================\n"
            "# Topics you've approved for production.\n"
            "# Run: python3 ~/.hermes/ebook-factory/skills/production/run_pipeline.py\n\n"
        )

    # Extract niche from title if not set
    niche = topic.get("niche") or parse_niche_from_title(topic["title"])

    # Append entry
    entry = f"\ntitle: {topic['title']}\nniche: {niche}\nchapters: 12\n---\n"
    content += entry
    APPROVED_TOPICS.write_text(content, encoding="utf-8")
    log(f"Appended to approved_topics.md: {topic['title']}")

# ── SEND mode ──────────────────────────────────────────────────────────────────

def cmd_send(topic_plan_path: Path = None):
    """Send candidate topics to Telegram for approval."""
    path = topic_plan_path or TOPIC_PLAN_LATEST

    if not path.exists():
        die(f"No topic plan found at {path}\nRun topic_pipeline.py first.")

    topics = parse_topic_plan(path)
    if not topics:
        die(f"Could not parse any topics from {path}")

    # Build message
    header = (
        "📚 *Next Book Candidates*\n\n"
        "Reply with a number to approve and auto-start that topic.\n"
    )
    tg_send(header)
    time.sleep(0.5)

    for t in topics:
        niche_str = f"\nNiche: `{t['niche']}`" if t["niche"] else ""
        score_str = f"\nScore: {t['score']}/10" if t["score"] else ""
        signal_str = f"\n_{t['signal'][:100]}_" if t["signal"] else ""

        msg = (
            f"*{t['num']}.* {t['title']}"
            f"{niche_str}{score_str}\n"
            f"{signal_str}"
        )
        tg_send(msg)
        time.sleep(0.3)

    # Update state
    state = load_state()
    state["topics_sent"] = [{"num": t["num"], "title": t["title"], "niche": t.get("niche", "")} for t in topics]
    state["sent_at"] = datetime.now().isoformat()
    save_state(state)
    log(f"Sent {len(topics)} topic candidates to Telegram")

# ── LISTEN mode ────────────────────────────────────────────────────────────────

def cmd_listen(timeout: int = 3600, auto_start: bool = False):
    """Poll Telegram for topic selection replies."""
    log(f"Listening for topic approval (timeout: {timeout}s)...")

    state = load_state()
    last_update_id = state.get("last_update_id", 0)
    deadline = time.time() + timeout
    approved_topic = None

    tg_send("👂 Waiting for your pick. Reply with a number to approve and auto-start.")

    while time.time() < deadline:
        updates = tg_get_updates(offset=last_update_id + 1)

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

            # Number selection
            nums = re.findall(r"\d+", text)
            if nums and len(nums) == 1:
                pick = int(nums[0])
                topics_sent = state.get("topics_sent", [])
                selected = next((t for t in topics_sent if t["num"] == pick), None)

                if selected:
                    niche = selected.get("niche") or parse_niche_from_title(selected["title"])
                    approved_topic = {
                        "title": selected["title"],
                        "niche": niche,
                        "chapters": 12,
                    }
                    append_to_approved(approved_topic)

                    # Auto-start the pipeline immediately on selection
                    tg_send(
                        f"✅ *Approved: {selected['title']}*\n"
                        f"Niche: {niche}\n\n"
                        f"Starting pipeline automatically..."
                    )
                    state["last_update_id"] = last_update_id
                    save_state(state)

                    cmd = [PYTHON, str(PIPELINE_SCRIPT)]
                    log(f"Auto-starting pipeline: {' '.join(cmd)}")
                    try:
                        subprocess.Popen(cmd, start_new_session=True)
                        tg_send("🚀 Pipeline running. I'll notify you when it's done.")
                    except Exception as e:
                        tg_send(f"❌ Pipeline launch failed: {e}")
                    return
                else:
                    tg_send(
                        f"⚠️ Topic {pick} not found. "
                        f"Available: {', '.join(str(t['num']) for t in topics_sent)}"
                    )

            # "run" command — start pipeline (kept for manual use, but auto-start is default)
            elif text.lower().strip() == "run":
                tg_send("🚀 Starting pipeline...")
                state["last_update_id"] = last_update_id
                save_state(state)

                # Launch pipeline in background
                cmd = [PYTHON, str(PIPELINE_SCRIPT)]
                log(f"Launching: {' '.join(cmd)}")
                try:
                    subprocess.Popen(cmd, start_new_session=True)
                    tg_send("Pipeline running. I'll notify you when it's done.")
                except Exception as e:
                    tg_send(f"❌ Pipeline launch failed: {e}")
                return

            # "new topics" — re-send list
            elif "new" in text.lower() and "topic" in text.lower():
                cmd_send()

            state["last_update_id"] = last_update_id
            save_state(state)

        time.sleep(POLL_INTERVAL)

    log(f"Listener timed out after {timeout}s")

# ── AUTO-PICK mode ─────────────────────────────────────────────────────────────

def cmd_auto_pick(num: int, start_pipeline: bool = True):
    """Directly approve a topic by number without Telegram."""
    topics = parse_topic_plan(TOPIC_PLAN_LATEST)
    if not topics:
        die(f"No topics found in {TOPIC_PLAN_LATEST}")

    selected = next((t for t in topics if t["num"] == num), None)
    if not selected:
        die(f"Topic {num} not found. Available: {', '.join(str(t['num']) for t in topics)}")

    niche = selected.get("niche") or parse_niche_from_title(selected["title"])
    topic = {"title": selected["title"], "niche": niche, "chapters": 12}
    append_to_approved(topic)
    log(f"Auto-approved: {selected['title']} ({niche})")

    if start_pipeline:
        cmd = [PYTHON, str(PIPELINE_SCRIPT)]
        log(f"Starting pipeline: {' '.join(cmd)}")
        subprocess.Popen(cmd, start_new_session=True)

# ── STATUS mode ────────────────────────────────────────────────────────────────

def cmd_status():
    """Show current topic plan and queue status."""
    print("\n=== Current Topic Plan ===")
    if TOPIC_PLAN_LATEST.exists():
        topics = parse_topic_plan(TOPIC_PLAN_LATEST)
        if topics:
            for t in topics:
                niche_str = f" | Niche: {t['niche']}" if t["niche"] else ""
                score_str = f" | Score: {t['score']}" if t["score"] else ""
                print(f"  {t['num']}. {t['title']}{niche_str}{score_str}")
        else:
            print("  (no topics parsed)")
    else:
        print("  No topic plan found. Run topic_pipeline.py first.")

    print(f"\n=== Approved Queue ({APPROVED_TOPICS}) ===")
    if APPROVED_TOPICS.exists():
        content = APPROVED_TOPICS.read_text()
        entries = re.split(r"---", content)
        pending = [e for e in entries if "status: DONE" not in e and "title:" in e]
        done = [e for e in entries if "status: DONE" in e]
        print(f"  Pending: {len(pending)}")
        for e in pending:
            title_m = re.search(r"title:\s*(.+)", e)
            if title_m:
                print(f"    - {title_m.group(1).strip()}")
        print(f"  Completed: {len(done)}")
    else:
        print("  (empty)")

# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Ebook Factory — Telegram Topic Approval"
    )
    parser.add_argument("--send",        action="store_true", help="Send topics to Telegram")
    parser.add_argument("--listen",      action="store_true", help="Listen for approval reply")
    parser.add_argument("--auto-pick",   type=int, metavar="N",
                        help="Skip Telegram, directly approve topic N from plan")
    parser.add_argument("--no-start",    action="store_true",
                        help="With --auto-pick: add to queue but don't auto-start pipeline (default: auto-starts)")
    parser.add_argument("--status",      action="store_true", help="Show topic plan and queue")
    parser.add_argument("--timeout",     type=int, default=3600,
                        help="Listener timeout in seconds (default: 3600)")
    parser.add_argument("--topic-plan",  type=Path, default=None,
                        help="Path to topic plan (default: topic_plan_latest.md)")
    args = parser.parse_args()

    if not any([args.send, args.listen, args.auto_pick, args.status]):
        parser.print_help()
        sys.exit(0)

    if args.status:
        cmd_status()
        return 0

    if args.auto_pick:
        cmd_auto_pick(args.auto_pick, start_pipeline=not args.no_start)
        return 0

    if args.send:
        cmd_send(args.topic_plan)

    if args.listen:
        cmd_listen(timeout=args.timeout)

    return 0

if __name__ == "__main__":
    sys.exit(main())
