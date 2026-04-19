---
name: factory-queue
description: "Show the approved topics queue for the ebook factory"
---

# Factory Queue

Display the current approved topics queue from `~/books/factory/approved_topics.md`.

## Steps

1. Parse and display the approved topics:
   ```bash
   python3 ~/.hermes/ebook-factory/skills/production/run_pipeline.py --list
   ```

2. Also show recently produced books:
   ```bash
   cat ~/books/factory/produced_topics.md 2>/dev/null | tail -20
   ```

3. If the user wants to add a topic, point them to `/factory-topics` to see candidates.

4. If the user wants to remove a topic, edit `~/books/factory/approved_topics.md` directly.

## Queue Format

Topics marked `status: PENDING` will be processed in order (FIFO).
Topics marked `status: DONE` have been produced and are logged in `produced_topics.md`.
