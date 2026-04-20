#!/usr/bin/env python3
"""
Production Orchestrator — runs the full ebook factory pipeline for one book.

Reads the next approved topic from ~/books/factory/approved_topics.md,
runs outliner → chapter-builder (parallel) → packager → cover-generator,
marks the topic done, and notifies via Telegram.

Usage:
    python3 run_pipeline.py                  # process next approved topic
    python3 run_pipeline.py --dry-run        # show what would run
    python3 run_pipeline.py --topic "Title"  # override (skip queue, use this)
    python3 run_pipeline.py --niche health   # paired with --topic
    python3 run_pipeline.py --chapters 10    # override chapter count
    python3 run_pipeline.py --list           # show approved queue
"""

import os
import sys
import re
import json
import time
import shlex
import subprocess
import argparse
import requests
from pathlib import Path
from datetime import datetime

# ── Paths ──────────────────────────────────────────────────────────────────────

HERMES_HOME      = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
FACTORY_DIR      = Path.home() / "books" / "factory"
APPROVED_TOPICS  = FACTORY_DIR / "approved_topics.md"
PRODUCED_TOPICS  = FACTORY_DIR / "produced_topics.md"
WORKBOOKS_DIR    = HERMES_HOME / "ebook-factory" / "workbooks"

SKILLS_BASE      = HERMES_HOME / "ebook-factory" / "skills"
OUTLINER         = HERMES_HOME / "skills" / "ebook-factory" / "skills" / "outliner" / "orchestrator.py"
CHAPTER_BUILDER  = SKILLS_BASE / "chapter-builder" / "chapter_builder.py"
PACKAGER         = SKILLS_BASE / "packager" / "packager.py"
COVER_GENERATOR  = SKILLS_BASE / "cover-generator" / "cover_generator.py"
VALIDATOR        = SKILLS_BASE / "validator" / "packaging_validator.py"
OLLAMA_CLIENT    = SKILLS_BASE / "ollama_client.py"

PLANNER_SCRIPT   = HERMES_HOME / "hermes_skills" / "planner" / "topic_pipeline.py"

# Pipeline concurrency lock
LOCK_FILE        = HERMES_HOME / "ebook-factory" / ".pipeline.lock"

# Ollama configuration for model management
OLLAMA_BASE_URL  = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OUTLINE_MODEL    = "qwen3.5:27b-16k"

VENV_PYTHON      = Path.home() / "hermes-agent" / "venv" / "bin" / "python3"
PYTHON           = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable

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

ENV = load_env()
TELEGRAM_TOKEN   = ENV.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = ENV.get("TELEGRAM_CHAT_ID", "")


def notify(msg: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception:
        pass

# ── Logging ────────────────────────────────────────────────────────────────────

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def log_section(title):
    print(f"\n{'='*60}\n  {title}\n{'='*60}", flush=True)

def die(msg):
    print(f"\n[ERROR] {msg}", file=sys.stderr, flush=True)
    notify(f"❌ *Pipeline ERROR*\n{msg}")
    release_pipeline_lock()
    sys.exit(1)

# ── Pipeline Lock ──────────────────────────────────────────────────────────────

def acquire_pipeline_lock():
    """Prevent concurrent pipeline runs on the same GPU. Dies if already running."""
    if LOCK_FILE.exists():
        try:
            pid = int(LOCK_FILE.read_text().strip())
            os.kill(pid, 0)  # signal 0 = check existence only
            die(
                f"Pipeline already running (PID {pid}).\n"
                f"If stale, delete {LOCK_FILE} and retry."
            )
        except (ProcessLookupError, ValueError):
            log(f"Stale lock from dead PID {LOCK_FILE.read_text().strip()}, removing")
            LOCK_FILE.unlink()
    LOCK_FILE.write_text(str(os.getpid()))
    log(f"Acquired pipeline lock (PID {os.getpid()})")

def release_pipeline_lock():
    """Release the pipeline lock. Safe to call multiple times."""
    try:
        LOCK_FILE.unlink(missing_ok=True)
    except Exception:
        pass

# ── Model Management ───────────────────────────────────────────────────────────

def unload_ollama_model(model_name: str):
    """Ask Ollama to unload a model from VRAM to free memory for the next phase."""
    try:
        sys.path.insert(0, str(SKILLS_BASE))
        from ollama_client import unload_model
        unload_model(model_name)
    except Exception as e:
        log(f"Model unload notice: {e} (non-critical — Ollama will evict on its own)")

# ── Queue management ───────────────────────────────────────────────────────────

def parse_queue(path: Path) -> list[dict]:
    """Parse approved_topics.md into a list of topic dicts."""
    if not path.exists():
        return []

    content = path.read_text(encoding="utf-8")
    topics = []

    # Split on --- separators; also handle entries at the top of the file
    # before the first separator by prepending a synthetic separator
    normalized = re.sub(r"^(#[^\n]*\n)+", "", content)  # strip leading comment block
    blocks = re.split(r"^---\s*$", normalized, flags=re.MULTILINE)
    for block in blocks:
        block = block.strip()
        if not block or block.startswith("#"):
            continue

        topic = {}

        # Skip DONE entries
        if re.search(r"^status:\s*DONE", block, re.IGNORECASE | re.MULTILINE):
            continue

        title_m = re.search(r"^title:\s*(.+)", block, re.MULTILINE)
        niche_m = re.search(r"^niche:\s*(.+)", block, re.MULTILINE)
        ch_m    = re.search(r"^chapters:\s*(\d+)", block, re.MULTILINE)
        notes_m = re.search(r"^notes:\s*(.+)", block, re.MULTILINE)

        if title_m:
            topic["title"]    = title_m.group(1).strip()
            topic["niche"]    = niche_m.group(1).strip() if niche_m else "self-help"
            topic["chapters"] = int(ch_m.group(1)) if ch_m else 10
            topic["notes"]    = notes_m.group(1).strip() if notes_m else ""
            topic["raw"]      = block
            topics.append(topic)

    return topics


def mark_done(topic: dict):
    """Mark a topic as DONE in approved_topics.md."""
    if not APPROVED_TOPICS.exists():
        return
    content = APPROVED_TOPICS.read_text(encoding="utf-8")
    # Replace status: RUNNING with status: DONE (or append DONE if no status)
    if "status: RUNNING" in topic.get("raw", ""):
        updated_block = topic["raw"].replace("status: RUNNING", "status: DONE")
    else:
        updated_block = topic["raw"] + "\nstatus: DONE"
    content = content.replace(topic["raw"], updated_block, 1)
    APPROVED_TOPICS.write_text(content, encoding="utf-8")
    log(f"Marked DONE in queue: {topic['title']}")

    # R1: Auto-trigger planner when queue drops below 2
    remaining = parse_queue(APPROVED_TOPICS)
    if len(remaining) < 2:
        log(f"Queue low ({len(remaining)} topics) — triggering topic planner...")
        try:
            subprocess.Popen(
                [PYTHON, str(PLANNER_SCRIPT)],
                start_new_session=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            log("Planner launched in background")
        except Exception as e:
            log(f"Could not launch planner: {e}")


def append_to_produced(topic: dict, workbook_dir: Path):
    """Append a completed book to produced_topics.md."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    output_dir = workbook_dir / "output"
    entry = (
        f"\n---\n"
        f"title: {topic['title']}\n"
        f"niche: {topic['niche']}\n"
        f"completed: {timestamp}\n"
        f"output: {output_dir}\n"
        f"upload_kit: {output_dir / 'kdp-upload-kit.txt'}\n"
    )
    with open(PRODUCED_TOPICS, "a", encoding="utf-8") as f:
        f.write(entry)
    log(f"Appended to produced log: {topic['title']}")


def mark_running(topic: dict):
    """Mark a topic as RUNNING in approved_topics.md (crash-safe tracking)."""
    if not APPROVED_TOPICS.exists():
        return
    content = APPROVED_TOPICS.read_text(encoding="utf-8")
    # Add status: RUNNING to the raw block
    if "status:" not in topic.get("raw", ""):
        updated_block = topic["raw"] + "\nstatus: RUNNING"
        content = content.replace(topic["raw"], updated_block, 1)
        APPROVED_TOPICS.write_text(content, encoding="utf-8")
        log(f"Marked RUNNING in queue: {topic['title']}")


def recover_orphans():
    """On startup, reset any RUNNING topics whose pipeline crashed."""
    if not APPROVED_TOPICS.exists():
        return
    content = APPROVED_TOPICS.read_text(encoding="utf-8")
    if "status: RUNNING" not in content:
        return
    # Reset all RUNNING back to PENDING (no status line)
    content = content.replace("\nstatus: RUNNING", "")
    APPROVED_TOPICS.write_text(content, encoding="utf-8")
    log("Recovered orphaned RUNNING topics — reset to PENDING")


def list_queue():
    topics = parse_queue(APPROVED_TOPICS)
    if not topics:
        print("Queue is empty. Add topics to ~/books/factory/approved_topics.md")
        return
    print(f"\n{'#':<4} {'Title':<55} {'Niche':<15} {'Ch':>3}")
    print("-" * 82)
    for i, t in enumerate(topics, 1):
        title = t['title'][:52] + "..." if len(t['title']) > 55 else t['title']
        print(f"{i:<4} {title:<55} {t['niche']:<15} {t['chapters']:>3}")
    print(f"\n{len(topics)} topic(s) in queue.")

# ── Pipeline steps ─────────────────────────────────────────────────────────────

def run_step(label: str, cmd: list[str], timeout: int = 600) -> bool:
    """Run a subprocess step. Returns True on success."""
    log_section(label)
    log(f"Running: {' '.join(shlex.quote(c) for c in cmd)}")
    start = time.time()
    try:
        result = subprocess.run(cmd, timeout=timeout, check=False)
        elapsed = round(time.time() - start, 1)
        if result.returncode == 0:
            log(f"  DONE in {elapsed}s")
            return True
        else:
            log(f"  FAILED (exit {result.returncode}) after {elapsed}s")
            return False
    except subprocess.TimeoutExpired:
        log(f"  TIMEOUT after {timeout}s")
        return False
    except Exception as e:
        log(f"  ERROR: {e}")
        return False


def find_workbook(title: str) -> Path | None:
    """Find the workbook directory for a given title."""
    if not WORKBOOKS_DIR.exists():
        return None
    slug_words = re.sub(r"[^a-z0-9\s]", "", title.lower()).split()
    slug = "-".join(slug_words)[:60]
    # Try exact slug match first
    for d in WORKBOOKS_DIR.iterdir():
        if d.is_dir() and d.name.startswith("book-") and slug[:20] in d.name:
            return d
    # Fall back to most recently modified
    dirs = [d for d in WORKBOOKS_DIR.iterdir() if d.is_dir() and d.name.startswith("book-")]
    if dirs:
        return sorted(dirs, key=lambda d: d.stat().st_mtime, reverse=True)[0]
    return None


def run_outliner(topic: dict, dry_run: bool) -> bool:
    cmd = [
        PYTHON, str(OUTLINER),
        "--topic", topic["title"],
        "--niche", topic["niche"],
        "--chapters", str(topic["chapters"]),
    ]
    if dry_run:
        log(f"[DRY RUN] Would run: {' '.join(cmd)}")
        return True
    return run_step("Outliner", cmd, timeout=600)


def run_chapter_builder(workbook_dir: Path, num_chapters: int, dry_run: bool) -> bool:
    """Run all chapters in parallel using subprocess."""
    log_section(f"Chapter Builder (chapters 1-{num_chapters} in parallel)")
    if dry_run:
        log(f"[DRY RUN] Would run {num_chapters} chapter-builder processes in parallel")
        return True

    procs = []
    for ch in range(1, num_chapters + 1):
        cmd = [
            PYTHON, str(CHAPTER_BUILDER),
            "--chapter", str(ch),
            "--book-dir", str(workbook_dir),
        ]
        log(f"  Starting chapter {ch}...")
        p = subprocess.Popen(cmd)
        procs.append((ch, p))
        # R10: Stagger launches to reduce GPU memory pressure spikes
        # Ollama handles queuing but 12 simultaneous requests cause model thrashing
        if ch < num_chapters:
            time.sleep(15)

    # Wait for all
    failed = []
    for ch, p in procs:
        try:
            p.wait(timeout=1800)  # 30 min max per chapter
            # Exit code 0 = PASS, exit code 1 = WARN (issues remain but chapter written)
            # Both are acceptable — only treat as failed if chapter file doesn't exist
            chapter_file = workbook_dir / "w-drafts" / f"chapter-{ch:02d}.md"
            if not chapter_file.exists():
                failed.append(ch)
                log(f"  Chapter {ch}: FAILED — no output file written")
            elif p.returncode == 0:
                log(f"  Chapter {ch}: PASS")
            else:
                log(f"  Chapter {ch}: WARN (validation issues remain — chapter written, manual review recommended)")
        except subprocess.TimeoutExpired:
            p.kill()
            failed.append(ch)
            log(f"  Chapter {ch}: TIMEOUT — killed")

    if failed:
        log(f"WARNING: {len(failed)} chapter(s) failed: {failed}")
        log("Continuing to packager with available chapters...")
        return len(failed) < num_chapters // 2  # tolerate up to half failing

    log(f"All {num_chapters} chapters completed")
    return True


def run_packager(workbook_dir: Path, dry_run: bool) -> bool:
    cmd = [PYTHON, str(PACKAGER), "--book-dir", str(workbook_dir)]
    if dry_run:
        log(f"[DRY RUN] Would run packager on {workbook_dir}")
        return True
    return run_step("Packager", cmd, timeout=300)


def run_cover_generator(workbook_dir: Path, dry_run: bool, niche: str = "") -> bool:
    cmd = [PYTHON, str(COVER_GENERATOR), "--book-dir", str(workbook_dir)]
    if niche:
        cmd += ["--niche", niche]
    if dry_run:
        log(f"[DRY RUN] Would run cover generator on {workbook_dir}")
        return True
    return run_step("Cover Generator", cmd, timeout=180)

def run_validator(workbook_dir: Path, dry_run: bool) -> bool:
    cmd = [PYTHON, str(VALIDATOR), "--book-dir", str(workbook_dir)]
    if dry_run:
        log(f"[DRY RUN] Would run validator on {workbook_dir}")
        return True
    log_section("Validator")
    log(f"Running: {' '.join(shlex.quote(c) for c in cmd)}")
    start = time.time()
    try:
        result = subprocess.run(cmd, timeout=300, check=False)
        elapsed = round(time.time() - start, 1)
        if result.returncode == 0:
            log(f"  PASS in {elapsed}s")
            return True
        elif result.returncode == 1:
            log(f"  WARN (validation warnings) after {elapsed}s")
            return True  # continue pipeline
        else:
            log(f"  FAIL (critical validation issues) after {elapsed}s")
            return False
    except subprocess.TimeoutExpired:
        log(f"  TIMEOUT after 300s")
        return False
    except Exception as e:
        log(f"  ERROR: {e}")
        return False

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Ebook Factory Production Orchestrator")
    parser.add_argument("--dry-run",  action="store_true", help="Show steps without running")
    parser.add_argument("--topic",    type=str, default="",  help="Override: specify topic directly")
    parser.add_argument("--niche",    type=str, default="self-help", help="Niche (with --topic)")
    parser.add_argument("--chapters", type=int, default=12,  help="Chapter count override")
    parser.add_argument("--list",     action="store_true", help="List approved queue and exit")
    args = parser.parse_args()

    if args.list:
        list_queue()
        return 0

    log_section("Ebook Factory — Production Orchestrator")

    # Acquire pipeline lock — prevents dual GPU usage
    acquire_pipeline_lock()

    # R6: Recover orphaned RUNNING topics from crashed pipeline runs
    recover_orphans()

    # Resolve topic
    if args.topic:
        topic = {
            "title":    args.topic,
            "niche":    args.niche,
            "chapters": args.chapters,
            "notes":    "",
            "raw":      "",
        }
        log(f"Topic (override): {topic['title']}")
    else:
        queue = parse_queue(APPROVED_TOPICS)
        if not queue:
            die(
                "No approved topics in queue.\n"
                f"Add topics to {APPROVED_TOPICS}\n"
                "Or use: python3 run_pipeline.py --topic 'Title' --niche productivity"
            )
        topic = queue[0]
        log(f"Topic (from queue): {topic['title']}")
        log(f"Queue depth: {len(queue)} topic(s) remaining")

    log(f"Niche: {topic['niche']} | Chapters: {topic['chapters']}")
    if topic.get("notes"):
        log(f"Notes: {topic['notes']}")

    # R6: Mark topic as RUNNING (crash-safe — orphan recovery on restart)
    mark_running(topic)

    start_time = time.time()
    notify(
        f"🏭 *Pipeline starting*\n"
        f"Book: _{topic['title']}_\n"
        f"Niche: {topic['niche']} | Chapters: {topic['chapters']}"
    )

    # ── Step 1: Outliner ──────────────────────────────────────────────────────
    if not run_outliner(topic, args.dry_run):
        die(f"Outliner failed for: {topic['title']}")

    # ── Locate workbook ───────────────────────────────────────────────────────
    workbook_dir = None
    if not args.dry_run:
        workbook_dir = find_workbook(topic["title"])
        if not workbook_dir:
            die(f"Could not find workbook directory after outliner ran.")
        log(f"Workbook: {workbook_dir}")

    # ── Step 2: Chapter Builder ───────────────────────────────────────────────
    if not run_chapter_builder(workbook_dir or Path("/tmp"), topic["chapters"], args.dry_run):
        die(f"Chapter builder critically failed — too many chapters missing.")

    # ── Auto‑promote drafts to w‑polished ───────────────────────────────────────
    if not args.dry_run and workbook_dir:
        drafts_dir   = workbook_dir / "w-drafts"
        polished_dir = workbook_dir / "w-polished"
        polished_dir.mkdir(parents=True, exist_ok=True)
        promoted = 0
        for draft in sorted(drafts_dir.glob("chapter-*.md")):
            dest = polished_dir / draft.name
            if not dest.exists():
                import shutil
                shutil.copy2(draft, dest)
                promoted += 1
        if promoted:
            log(f"Auto‑promoted {promoted} chapter(s) from w‑drafts/ to w‑polished/")

    # ── Chapter count gate ──────────────────────────────────────────────────────
    if not args.dry_run and workbook_dir:
        polished_dir = workbook_dir / "w-polished"
        polished_count = len(list(polished_dir.glob("chapter-*.md")))
        expected = topic["chapters"]
        if polished_count < expected:
            missing = []
            for ch in range(1, expected + 1):
                if not (polished_dir / f"chapter-{ch:02d}.md").exists():
                    missing.append(ch)
            log(f"WARNING: Only {polished_count}/{expected} chapters in w-polished. Missing: {missing}")
            log(f"Retrying missing chapters...")
            for ch in missing:
                cmd = [
                    PYTHON, str(CHAPTER_BUILDER),
                    "--chapter", str(ch),
                    "--book-dir", str(workbook_dir),
                    "--force",
                ]
                log(f"  Rebuilding chapter {ch}...")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
                if result.returncode != 0:
                    log(f"  WARNING: Chapter {ch} rebuild returned exit code {result.returncode}")
                # Promote the rebuilt chapter
                draft = workbook_dir / "w-drafts" / f"chapter-{ch:02d}.md"
                dest = polished_dir / f"chapter-{ch:02d}.md"
                if draft.exists():
                    import shutil
                    shutil.copy2(draft, dest)
                    log(f"  Chapter {ch} rebuilt and promoted")
                else:
                    log(f"  ERROR: Chapter {ch} draft still missing after rebuild")
            # Recheck
            polished_count = len(list(polished_dir.glob("chapter-*.md")))
            if polished_count < expected:
                die(f"Still missing {expected - polished_count} chapter(s) after retry. Cannot continue.")
            log(f"Chapter count gate passed: {polished_count}/{expected} chapters")

    # ── Step 3: Packager (must run before cover — creates kdp-metadata.json) ──
    if not run_packager(workbook_dir or Path("/tmp"), args.dry_run):
        log("WARNING: Packager failed — output may be incomplete. Continuing.")

    # ── Step 4: Cover Generator (needs kdp-metadata.json from packager) ──────
    if not run_cover_generator(workbook_dir or Path("/tmp"), args.dry_run,
                                niche=topic.get("niche", "")):
        log("WARNING: Cover generator failed — generate cover manually.")

    # ── Step 5: Validator ───────────────────────────────────────────────
    if not run_validator(workbook_dir or Path("/tmp"), args.dry_run):
        log("WARNING: Validator failed — output may have issues. Continuing.")
    # ── Done ──────────────────────────────────────────────────────────────────
    elapsed = round(time.time() - start_time)
    mins, secs = divmod(elapsed, 60)

    # Always release lock on completion
    release_pipeline_lock()

    if not args.dry_run and workbook_dir:
        mark_done(topic)
        append_to_produced(topic, workbook_dir)
        output_dir = workbook_dir / "output"

        log_section("PIPELINE COMPLETE")
        log(f"Book:    {topic['title']}")
        log(f"Time:    {mins}m {secs}s")
        log(f"Output:  {output_dir}")
        log(f"")
        log(f"Files ready for upload:")
        for f in sorted(output_dir.iterdir()):
            if f.suffix in (".docx", ".epub", ".pdf", ".jpg") or f.name == "kdp-upload-kit.txt":
                log(f"  ✓ {f.name}")

        # Build file list for Telegram notification
        file_list = ", ".join(
            f.name for f in sorted(output_dir.iterdir())
            if f.suffix in (".docx", ".epub", ".pdf", ".jpg") or f.name == "kdp-upload-kit.txt"
        )
        notify(
            f"✅ *Book complete!*\n"
            f"_{topic['title']}_\n\n"
            f"⏱ {mins}m {secs}s\n"
            f"📁 `{output_dir}`\n"
            f"📦 {file_list}\n\n"
            f"Open `kdp-upload-kit.txt` to upload."
        )
    else:
        log_section("DRY RUN COMPLETE — no files written")

    return 0


if __name__ == "__main__":
    sys.exit(main())
