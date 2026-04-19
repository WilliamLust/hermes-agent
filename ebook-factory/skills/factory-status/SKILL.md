---
name: factory-status
description: "Show ebook factory pipeline status — running jobs, chapter progress, queue depth"
---

# Factory Status

Check the current state of the ebook factory pipeline.

## Steps

1. Check for running pipeline processes:
   ```bash
   ps aux | grep run_pipeline.py | grep -v grep
   ```

2. Check the approved topics queue:
   ```bash
   python3 ~/.hermes/ebook-factory/skills/production/run_pipeline.py --list
   ```

3. Check the most recent workbook for progress:
   ```bash
   ls -la ~/.hermes/ebook-factory/workbooks/ | tail -5
   ```
   Then for the latest workbook:
   ```bash
   ls ~/.hermes/ebook-factory/workbooks/book-*/w-drafts/ 2>/dev/null | wc -l
   ls ~/.hermes/ebook-factory/workbooks/book-*/w-polished/ 2>/dev/null | wc -l
   ls ~/.hermes/ebook-factory/workbooks/book-*/output/ 2>/dev/null
   ```

4. Check Ollama GPU status:
   ```bash
   nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader
   ```

## Report Format

```
Pipeline: [running|idle]
Current book: [title or "none"]
Chapters drafted: X/12
Chapters polished: X/12
Output files: [list]
Queue depth: N topics remaining
GPU: XX% util, XX/XX MB VRAM
```
