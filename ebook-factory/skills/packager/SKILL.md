---
name: ebook-packager
category: ebook-factory
description: "Packager agent SKILL.md — load this to get the packager.py script path and usage. Assembles EPUB, PDF, HTML, KDP metadata from approved chapters."
tags: [ebook, packager, epub, pdf, phase-3]
version: 1.0
---

# Packager Agent — SKILL.md

**Script:** `~/.hermes/ebook-factory/skills/packager/packager.py`

## Quick Start
```bash
source ~/hermes-agent/venv/bin/activate
cd ~/.hermes/ebook-factory/skills/packager/
python3 packager.py
```

## Prerequisites
All chapters must be approved and in `w-polished/`:
```bash
ls ~/.hermes/ebook-factory/workbooks/book-*/w-polished/
```

## See Also
- Full usage: load skill `ebook-agent-packager`
- Pipeline overview: load skill `walnut-agent-orchestrator`
- Master reference: `~/hermes-agent/AGENTS.md` section 6
