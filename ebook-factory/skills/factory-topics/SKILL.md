---
name: factory-topics
description: "Show current ebook topic candidates from the planner — send numbered list to Telegram"
---

# Factory Topics

Show the latest topic candidates from `~/.hermes/output/planner/topic_plan_latest.md`.

## Steps

1. Check if `~/.hermes/output/planner/topic_plan_latest.md` exists
2. If not, run the topic planner first:
   ```bash
   python3 ~/.hermes/hermes_skills/planner/topic_pipeline.py
   ```
3. Parse the topic plan and present a numbered list to the user
4. Tell the user to reply with a number to auto-queue and auto-start that topic

## Output Format

Present each topic as:
```
1. Title Here
   Niche: productivity | Score: 7.5/10
   Market signal: ...
```

If the user replies with a number, run:
```bash
python3 ~/.hermes/ebook-factory/skills/production/topic_approval.py --auto-pick <NUMBER>
```

This auto-queues the topic AND starts the pipeline. No separate "run" step needed.
