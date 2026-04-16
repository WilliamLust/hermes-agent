---
name: ebook-factory-telegram-review
category: ebook-factory
description: "Telegram review workflow — sends chapter summaries, listens for approve/redo replies, moves chapters to w-polished/ automatically."
tags: [ebook, telegram, review, workflow, chapters]
version: 1.0
---

# Ebook Factory — Telegram Review Workflow

Sends chapter draft summaries to your Telegram bot for human review,
then listens for your approve/redo replies and acts on them.

## Location
`~/.hermes/ebook-factory/skills/telegram-review/review_workflow.py`

## Usage

```bash
source ~/hermes-agent/venv/bin/activate
cd ~/.hermes/ebook-factory/skills/telegram-review/

# Check what's ready
python3 review_workflow.py --status

# Send all pending chapters to Telegram
python3 review_workflow.py --send

# Listen for replies (1 hour timeout)
python3 review_workflow.py --listen --timeout 3600

# Full workflow: send then listen
python3 review_workflow.py --send --listen

# Target a specific workbook
python3 review_workflow.py --send --listen --book-dir ~/.hermes/ebook-factory/workbooks/book-slug/
```

## Telegram Commands (send from your phone)

| Command | Effect |
|---------|--------|
| `approve 1,2,3` | Move chapters 1,2,3 to w-polished/ |
| `approve all` | Move all pending chapters |
| `redo 4,6` | Flag chapters for regeneration |
| `status` | Bot replies with chapter-by-chapter status |

## What Gets Sent Per Chapter

- Chapter number and title
- Word count + validation pass/fail status
- First ~60 words as preview

## Pipeline Position

```
Chapter-Builder → w-drafts/ → [THIS SCRIPT] → w-polished/ → Packager
```

After all chapters approved, bot sends packager command automatically.

## Auto-Detection

If `--book-dir` not specified, auto-selects the most recently modified
workbook in `~/.hermes/ebook-factory/workbooks/`.

## State File

Writes `.review_state.json` in the workbook directory to track:
- Which chapters are pending/approved/redo
- Last Telegram update ID (prevents double-processing)
- When summaries were last sent

## Known Pitfalls

- Listener exits when all chapters are polished or timeout reached
  → Re-run with `--listen` after more chapters are drafted
- `last_update_id=0` on first run means it may see old messages from
  the chat — these are ignored if text doesn't match approve/redo/status
- The draft chapter file naming is flexible:
  `w-drafts/chapter-NN.md`, `02_chapter_NN.md`, `chapter-NN.md` all work
