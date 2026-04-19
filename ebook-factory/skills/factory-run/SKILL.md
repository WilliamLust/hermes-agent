---
name: factory-run
description: "Start the ebook factory pipeline on the next queued topic"
---

# Factory Run

Start the ebook factory pipeline. Processes the next approved topic from the queue.

## Steps

1. Check if a pipeline is already running:
   ```bash
   ps aux | grep run_pipeline.py | grep -v grep
   ```
   If running, report status and do NOT start another.

2. Check the queue:
   ```bash
   python3 ~/.hermes/ebook-factory/skills/production/run_pipeline.py --list
   ```

3. If queue is empty, tell the user to pick a topic first using `/factory-topics`.

4. If queue has items, start the pipeline in background:
   ```bash
   nohup python3 ~/.hermes/ebook-factory/skills/production/run_pipeline.py > /tmp/factory-pipeline.log 2>&1 &
   ```

5. Report to user: "Pipeline started. Book: [title]. I'll notify you when it's done."

## Override Options

To run a specific topic (bypassing the queue):
```bash
python3 ~/.hermes/ebook-factory/skills/production/run_pipeline.py --topic "Title Here" --niche health
```

## Monitoring

Check progress with `/factory-status` or read the log:
```bash
tail -20 /tmp/factory-pipeline.log
```
