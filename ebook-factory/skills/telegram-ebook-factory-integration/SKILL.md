---
name: telegram-ebook-factory-integration
category: ebook-factory
description: "Telegram integration patterns for ebook factory — topic approval vs chapter approval, command parsing, and session history verification."
tags: [telegram, ebook-factory, approval, human-in-loop]
version: 1.0
---

# Telegram Ebook Factory Integration

## Core Lesson
**Always check session history before implementing Telegram integration.** The user has expressed clear preferences across sessions:
- **Topic-level approval**: "I want to approve topics, and have that start the pipeline… finishing with a completed product waiting to be uploaded." (Session 20260416_125510)
- **Not chapter summaries**: "I don't want chapter summaries." (Current session)

Verify the user's desired workflow via `session_search("Telegram approval topics")` before building.

## Two Implementation Patterns

### Pattern 1: Topic Approval (User's Preference)
**Goal**: User sends a simple Telegram command (e.g., "topic approved, please proceed") to add a topic to the queue and trigger autonomous pipeline.

**Implementation outline**:
1. Bot listens for `/approve_topic` or keyword "topic approved"
2. Reads next candidate from `topic_plan_latest.md` (or accepts title/niche as arguments)
3. Appends to `~/books/factory/approved_topics.md` with `status: PENDING`
4. Spawns `run_pipeline.py --auto` for that topic
5. Notifies on completion (cover thumbnail + alert)

**Key decisions**:
- Single command triggers full pipeline (outline → chapters → packaging)
- No per‑chapter review gate unless explicitly requested
- Pipeline runs autonomously with `--auto` flag

### Pattern 2: Chapter‑Level Human Review Gate (Built but Misaligned)
**Goal**: Batch approval/rejection of individual chapters after drafting.

**Implementation**: `~/.hermes/ebook‑factory/skills/production/telegram_approval.py`
- Sends chapter summaries (word count, validation status)
- Waits for `approve 1,2,3` or `redo 4,6` commands
- 24h timeout → auto‑approves all
- Re‑runs redos via chapter‑builder subprocesses

**Integration**: Called from `run_pipeline.py` after chapter‑builder, before cover‑generator. Controlled by `--auto` flag (skip) vs default (enable).

## Environment Setup
Credentials in `~/.hermes/.env`:
```
TELEGRAM_BOT_TOKEN=8751204976:AAFD-TrlLbZY0IkiY4vAQZwg0Eg6esDFWiw
TELEGRAM_CHAT_ID=1851466851
```

Bot: `@Hermes_Ebook_Factory_Bot`

## Command Parsing Examples
```python
# Topic approval
if "topic approved" in message.lower():
    approve_topic_and_start_pipeline()

# Chapter approval
approve_match = re.search(r'approve\\s+([\\d,\\s]+)', text)
redo_match = re.search(r'redo\\s+([\\d,\\s]+)', text)

# Auto command
if text.lower() == "auto":
    auto_approve_all()
```

## Pipeline Integration Points
1. **Topic selection** → After Planner generates candidates, send top 3 via Telegram for user choice
2. **Chapter review** → After chapter‑builder completes, send summaries for batch approval (optional)
3. **KDP upload** → Send cover+metadata preview for final approval before browser automation

## Current State (April 2026)
- ✅ Bot configured for outbound notifications (covers, completion alerts)
- ✅ Chapter‑level approval gate implemented (`telegram_approval.py`)
- ❌ **Missing**: Topic‑level approval command listener
- ❌ **Missing**: Telegram‑triggered pipeline start

## Next Steps
1. Remove or flag chapter‑review gate as optional (`--chapter‑review`)
2. Build topic‑approval listener that reads from `topic_plan_latest.md`
3. Integrate with `run_pipeline.py` to spawn autonomous runs on command
4. Consider menu‑style interaction: bot sends "Next 3 topics:", user replies "2"