# Hermes Agent — Development Guide & Ebook Factory Operations Manual

**Last Updated:** 2026-04-15
**Status:** Active — Pipeline Build Phase
**Owner:** bookforge (William Archer)

---

## CRITICAL: READ THIS FIRST (Every Session)

This file is the master reference for EVERYTHING on this machine. Before doing anything, read this file completely. If you are a local model (Qwen, etc.) running Hermes, you must follow this document precisely. Do not improvise. Do not create new directories. Do not install new tools. Follow the established patterns.

**The Goal:** Finish building the Ebook Factory pipeline so it can run autonomously on a local model (qwen3.5:35b-a3b-q4_k_m via Ollama). The pipeline is designed to generate, validate, and package commercial ebooks for Amazon KDP with minimal human intervention.

---

## 1. MACHINE & ENVIRONMENT

```
OS:         Linux Mint (x86_64)
User:       bookforge
Home:       /home/bookforge/
GPU:        NVIDIA (runs ComfyUI + Ollama)
Hermes:     v0.9.0 at ~/hermes-agent/ (venv at ~/hermes-agent/venv/)
Config:     ~/.hermes/config.yaml
Keys/Env:   ~/.hermes/.env
```

### Active Binary
```
hermes = ~/hermes-agent/venv/bin/hermes
```
Always activate before running Python scripts that use hermes internals:
```bash
source ~/hermes-agent/venv/bin/activate
```

### Local Models (Ollama at http://localhost:11434)
```
qwen3.5:35b-a3b-q4_k_m ← PRIMARY (drafting, outlining, refining — MoE, fast, 262k ctx)
qwen3.5:27b-16k    ← FALLBACK (if 35B too slow or VRAM pressure)
qwen3.5:27b-8k     ← FALLBACK-2 (speed-critical tasks only)
qwen3.5:27b-q4_K_M ← ALTERNATE name for 27b dense model
qwen3.5:9b         ← Fast/light tasks only
```

### API Keys (.env)
```
ANTHROPIC_API_KEY     — Claude (primary for orchestration + building)
FIRECRAWL_API_KEY     — Web research (hobby plan, 3000 credits/month)
TELEGRAM_BOT_TOKEN    — @Hermes_Ebook_Factory_Bot (bot ID: 8751204976)
TELEGRAM_CHAT_ID      — 1851466851 (William / @williamlust) — CONFIRMED WORKING
IDEOGRAM_API_KEY      — Cover generation (sign up pending)
KDP_EMAIL             — Amazon KDP login email (NOT YET SET)
KDP_PASSWORD          — Amazon KDP login password (NOT YET SET)
```

---

## 2. EBOOK FACTORY — SYSTEM OVERVIEW

### Purpose
Automated pipeline to produce commercial ebooks (2500-3000 words/chapter, 10-12 chapters) for Amazon KDP. The factory takes a validated topic idea and produces a KDP-ready ebook package (EPUB, PDF, cover, metadata).

### Published Books (12 completed — in ~/books/factory/references/published-books/)
```
1. Time Blocking For Remote Workers
2. The 80-20 Guide to Getting More Done
3. Weekly Review Systems for Busy People
4. Building a Second Brain on a Budget
5. Gut Health Basics Without the Pseudoscience
6. Walking for Weight Loss: The Underrated Strategy
7. AI Tools for Everyday Productivity
8. Protecting Your Digital Privacy Without Going Off-Grid
9. The No-BS Guide to Home Network Security
10. The Procrastination Fix
11. Sleep Well Tonight
12. Low-Income Chronic Fatigue Management
```

### Pipeline State Machine
```
PHASE 0: DISCOVERY         PHASE 1: CHAPTER FACTORY      PHASE 2: HUMAN REVIEW    PHASE 3: ASSEMBLY
─────────────────────      ──────────────────────────     ─────────────────────    ─────────────────
marketplace_analyzer   →   Outliner (01_outline.md)   →  Human approves        →  Packager
topic_planner              Chapter-Builder x3-5           w-drafts → w-polished     final book + KDP
topic_plan_*.md            (parallel agents)              (manual gate)             output/*
[DONE]                     [OUTLINER DONE]                [MANUAL]                  [NEEDS BUILD]
                           [CHAPTER-BUILDER NEEDS BUILD]
```

### Agent Roles & Handoff Contracts
```
Agent           | Script Location                                    | Input                           | Output                    | Gate
────────────────|────────────────────────────────────────────────────|─────────────────────────────────|───────────────────────────|─────────────────────────
Outliner        | ~/.hermes/skills/ebook-factory/skills/outliner/    | topic_plan_*.md + LEARNING.md   | workbook/01_outline.md    | viability ≥6.0, 10-12 chapters
                | orchestrator.py                                    |                                 |                           |
Chapter-Builder | ~/.hermes/ebook-factory/skills/chapter-builder/    | 01_outline.md + LEARNING.md     | w-drafts/chapter-XX.md    | word count ±10%, all points covered
                | chapter_builder.py                                 |                                 |                           |
Human Review    | (manual)                                           | w-drafts/*                      | w-polished/* (approved)   | manual quality gate
Packager        | ~/.hermes/ebook-factory/skills/packager/           | w-polished/* + metadata         | output/* (EPUB/PDF/KDP)   | format compliance
                | packager.py                                        |                                 |                           |
```

---

## 3. FILE STRUCTURE (CANONICAL — DO NOT DEVIATE)

```
~/.hermes/                              ← HERMES_HOME (use get_hermes_home() in code)
├── config.yaml                         ← Hermes configuration
├── .env                                ← API keys
├── skills/                             ← All Hermes skills (auto-loaded)
│   └── ebook-factory/                  ← Factory-specific skills
│       ├── skills/outliner/            ← Outliner agent code
│       │   ├── orchestrator.py         ← Main outliner script [DONE]
│       │   └── SKILL.md                ← How to use the outliner
│       ├── skills/chapter-builder/     ← Chapter-Builder code [NEEDS BUILD]
│       │   ├── chapter_builder.py
│       │   └── SKILL.md
│       ├── skills/packager/            ← Packager code [NEEDS BUILD]
│       │   ├── packager.py
│       │   └── SKILL.md
│       ├── outliner/SKILL.md           ← Outliner skill definition
│       ├── ebook-agent-drafter/SKILL.md
│       ├── ebook-agent-validator/SKILL.md
│       ├── ebook-agent-refiner/SKILL.md
│       ├── ebook-agent-packager/SKILL.md
│       └── FACTORY-PIPELINE-PLAN4.md   ← Architecture document
│
└── ebook-factory/                      ← Factory working data
    ├── workbooks/                      ← One dir per book project
    │   └── book-<topic-slug>/
    │       ├── 01_outline.md           ← Outliner output
    │       ├── w-drafts/               ← Chapter-Builder writes here
    │       │   ├── chapter-01.md
    │       │   └── ...
    │       ├── w-polished/             ← Human-approved chapters
    │       │   └── chapter-01.md
    │       └── output/                 ← Packager output
    │           ├── manuscript.epub
    │           ├── manuscript.pdf
    │           ├── cover.jpg
    │           └── kdp-metadata.json
    └── skills/                         ← Agent scripts (working copies)
        ├── draft-chapter/orchestrator.py   ← OLD drafter (reference only)
        └── refiner-chapter/refiner.py      ← OLD refiner (reference only)

~/books/                                ← Book content and references
├── factory/
│   ├── config.yaml                     ← Universal factory config
│   ├── style-guide.md                  ← Writing standards
│   ├── LEARNING.md                     ← Historical performance data
│   └── references/published-books/     ← 12 published books (voice reference)
└── the-ai-revolution/                  ← AI Revolution book (in-progress, post-pipeline)
    ├── w-drafts/                       ← Draft chapters
    ├── w-polished/                     ← Polished chapters
    └── w-chapters-recovered/           ← Recovered content

~/hermes-agent/                         ← Hermes codebase (DO NOT MODIFY casually)
└── AGENTS.md                           ← THIS FILE (canonical master reference)
```

### CRITICAL PATH RULES
1. NEVER hardcode `~/.hermes` — always use `get_hermes_home()` from `hermes_constants`
2. Always include `<!-- AUTO-GENERATED: {timestamp} -->` at top of output files
3. Add `## Validation Report` section at end of output showing pass/fail status
4. Pass `w-polished/chapter-01.md` as voice reference to ALL Chapter-Builder agents
5. Each Chapter-Builder writes to a SEPARATE file — no shared state

---

## 4. HOW TO RUN THE PIPELINE

### Phase 0: Generate Outline (WORKING)
```bash
cd ~/.hermes/skills/ebook-factory/skills/outliner/
source ~/hermes-agent/venv/bin/activate
python3 orchestrator.py --chapters 10
# Output: ~/.hermes/ebook-factory/workbooks/book-<topic>/01_outline.md
```

### Phase 1: Generate Chapters (BUILD IN PROGRESS)
```bash
cd ~/.hermes/ebook-factory/skills/chapter-builder/
source ~/hermes-agent/venv/bin/activate

# Single chapter:
python3 chapter_builder.py --chapter 1

# Parallel (3 at once):
python3 chapter_builder.py --chapter 1 &
python3 chapter_builder.py --chapter 2 &
python3 chapter_builder.py --chapter 3 &
wait
# Output: ~/.hermes/ebook-factory/workbooks/book-<topic>/w-drafts/chapter-XX.md
```

### Phase 2: Human Review (MANUAL)
```
1. Read each chapter in w-drafts/
2. Approve: move to w-polished/
3. Reject: leave in w-drafts/ and re-run chapter_builder.py --chapter N --force
```

### Phase 3: Package (BUILD IN PROGRESS)
```bash
cd ~/.hermes/ebook-factory/skills/packager/
source ~/hermes-agent/venv/bin/activate
python3 packager.py --book-dir ~/.hermes/ebook-factory/workbooks/book-<topic>/
# Output: ~/.hermes/ebook-factory/workbooks/book-<topic>/output/
```

---

## 5. CHAPTER-BUILDER AGENT SPEC (WHAT TO BUILD)

### Location
`~/.hermes/ebook-factory/skills/chapter-builder/chapter_builder.py`

### API Call Pattern (Ollama direct — NOT subprocess CLI)
```python
import requests

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL = "qwen3.5:35b-a3b-q4_k_m"

response = requests.post(OLLAMA_URL, json={
    "model": MODEL,
    "messages": [{"role": "user", "content": prompt}],
    "stream": False,
    "options": {"temperature": 0.7, "num_predict": 5000}
})
content = response.json()["message"]["content"]
```

### Self-Validation Loop
```
Draft → validate (word count ±10%, keywords present, no placeholders, has conclusion)
  → if issues: refine (LLM call with issues list)
  → re-validate (max 3 iterations)
  → write to w-drafts/chapter-XX.md
```

### Output Format
```markdown
# Chapter N: Title
<!-- AUTO-GENERATED: 2026-04-15T14:00:00 -->

[2500-3000 words of content]

---

## Validation Report
- Word count: 2847 ✓ (target: 2800)
- Keywords: all present ✓
- Conclusion: present ✓
- Refinement iterations: 1
- Status: PASS
```

### CLI Interface
```bash
python3 chapter_builder.py --chapter 3
python3 chapter_builder.py --chapter 3 --book-dir /path/to/workbook/
python3 chapter_builder.py --chapter 3 --force   # Overwrite existing
python3 chapter_builder.py --chapter 3 --model qwen3.5:27b-16k  # Override to fallback
```

---

## 6. PACKAGER AGENT SPEC (WHAT TO BUILD)

### Location
`~/.hermes/ebook-factory/skills/packager/packager.py`

### Tools Required
- `ebook-convert` (Calibre CLI) — for EPUB/MOBI conversion
- `weasyprint` — for PDF generation from HTML
- Python `ebooklib` — for EPUB construction

### Inputs
```
w-polished/chapter-*.md    ← All approved chapters
01_outline.md              ← For TOC and metadata
books/factory/style-guide.md ← For consistent formatting
```

### Outputs
```
output/
├── manuscript.epub
├── manuscript.pdf
├── cover.jpg              (via ComfyUI or placeholder)
└── kdp-metadata.json      (title, author, keywords, BISAC category)
```

### Tasks
1. Assemble chapters in order
2. Generate front matter (title page, copyright, TOC)
3. Generate back matter (author bio, CTA to other books)
4. Convert to EPUB via ebooklib
5. Convert to PDF via weasyprint
6. Write kdp-metadata.json
7. Validate output files (epubcheck if available)

---

## 7. PERFORMANCE TARGETS

```
Metric                  | Target        | How to Verify
────────────────────────|───────────────|──────────────────────────────
Outliner gen time       | < 3 min       | Log start/end timestamps
Chapters total          | 10-12         | Count H2 headers in 01_outline.md
Chapter-Builder time    | ~6 min each   | Parallel: 10 chapters ~30 min
Validation pass rate    | ≥90% first try| Check Validation Reports
Human edit rate         | < 20%         | Count w-drafts rejections
Word count accuracy     | ±10% of target| Validation Report
```

---

## 8. HERMES CONFIGURATION (CURRENT)

```yaml
# ~/.hermes/config.yaml (key settings)
model:
  default: claude-sonnet-4-6
  provider: anthropic           # Change to local-localhost:11434 for local mode

providers:
  local-localhost:11434:
    api: http://localhost:11434/v1
    default_model: qwen3.5:35b-a3b-q4_k_m

agent:
  max_iterations: 60            # 60 for pipeline work (was 20, too low)
  timeout_seconds: 600

toolsets:                       # Enabled toolsets
  - hermes-cli
  - topic-research
  - file
  - terminal
  - web
```

### To Switch to Local Model Mode
```bash
hermes /model local-localhost:11434/qwen3.5:35b-a3b-q4_k_m
# OR edit config.yaml: model.provider: local-localhost:11434
```

---

## 9. WHAT STILL NEEDS TO BE BUILT

### Priority Order
```
1. Chapter-Builder agent (chapter_builder.py)       ← NEXT
2. Packager agent (packager.py)                     ← AFTER
3. End-to-end smoke test (outline → chapters → package)
4. Update all SKILL.md files for local model operation
5. Switch default model to qwen3.5:35b-a3b-q4_k_m
```

### What Is Done (as of 2026-04-16)
```
✓ Outliner agent — ~/.hermes/skills/ebook-factory/skills/outliner/orchestrator.py
✓ Analyzer agent — ~/.hermes/hermes_skills/analyzer/orchestrator.py (NOT on GitHub yet)
✓ Planner agent  — ~/.hermes/hermes_skills/planner/orchestrator.py (NOT on GitHub yet)
✓ Chapter-Builder — ~/.hermes/ebook-factory/skills/chapter-builder/chapter_builder.py
✓ Packager — ~/.hermes/ebook-factory/skills/packager/packager.py
✓ Researcher v2 (BSR-integrated) — ~/.hermes/ebook-factory/skills/researcher/researcher.py
✓ Telegram Review Workflow — ~/.hermes/ebook-factory/skills/telegram-review/review_workflow.py
✓ Cover Generator (Ideogram+Pillow) — ~/.hermes/ebook-factory/skills/cover-generator/cover_generator.py
✓ KDP Upload Helper (Playwright) — ~/.hermes/ebook-factory/skills/kdp-upload/kdp_upload.py
✓ Self-Improvement Agent (weekly cron) — ~/.hermes/ebook-factory/skills/self-improvement/self_improvement.py
✓ 12 published books — voice reference at ~/books/factory/references/published-books/
✓ Book 13 complete — Productivity for ADHD Adults (26,694 words, packaged, ready for KDP upload)
✓ GitHub checkpoint — https://github.com/WilliamLust/hermes-agent (commit aa9caea2)
✓ Ollama running with qwen3.5:35b-a3b-q4_k_m (MoE, 23GB, 262k ctx)

### Known Issues / Next Session TODO
- Analyzer + Planner not committed to GitHub yet — add in next session
- Test Analyzer + Planner end-to-end (status uncertain from prior sessions)
- Chapter-Builder word count: 35B model lands 5-10% short; set outline targets to 3100 words
- Consider testing qwen3.5:27b-16k for chapter drafting — may be faster/more consistent
- KDP credentials set in ~/.hermes/.env — password was recently changed
- NVIDIA persistence mode: run `sudo nvidia-smi -pm 1` after each reboot
- Cover generator: parenting palette needs work (too generic/abstract background)
```
✓ Refiner agent (refiner.py) — iterative refinement loop
✓ Old drafter (orchestrator.py in draft-chapter/) — superseded by new Chapter-Builder
✓ 12 published books — voice reference material exists
✓ Hermes v0.9.0 installed and working
✓ Ollama running with qwen3.5:35b-a3b-q4_k_m (MoE, 23GB, 262k context)
✓ LEARNING.md with historical performance data
```

---

## 10. COMMON PROBLEMS & SOLUTIONS

### Hermes doesn't know what it's working on (session amnesia)
- Root cause: Local model has no cross-session memory
- Solution: Always start sessions with: `cat ~/hermes-agent/AGENTS.md`
- Then run: `cat ~/.hermes/ebook-factory/workbooks/book-<topic>/01_outline.md`

### Chapter-Builder produces < 2000 words
- Increase `num_predict` to 6000 in API call options
- Add explicit word count to prompt: "Write exactly 2800 words. Do not stop early."
- Use 16k context model, not 8k

### Outliner finds no topic plans
- Run topic_planner first: `~/.hermes/hermes_skills/planner/`
- OR manually create a topic_plan file in `~/.hermes/output/planner/`

### Packager can't find ebook-convert
- Install Calibre: `sudo apt install calibre`
- Verify: `which ebook-convert`

### Ollama times out during generation
- Increase timeout to 1800 seconds (30 min)
- Use 8k context model for speed
- Check GPU memory: `nvidia-smi`

---

## 11. DEVELOPMENT ENVIRONMENT (hermes-agent codebase)

```
Always activate venv before running Python:
source ~/hermes-agent/venv/bin/activate

Key files:
run_agent.py          ← AIAgent class, core loop
model_tools.py        ← Tool orchestration
toolsets.py           ← Toolset definitions
cli.py                ← HermesCLI class
hermes_cli/config.py  ← DEFAULT_CONFIG, config migration
tools/registry.py     ← Central tool registry
```

### Adding New Tools (3-step)
1. Create `tools/your_tool.py` with `registry.register()`
2. Add import in `model_tools.py` `_discover_tools()` list
3. Add to `toolsets.py`

### Testing
```bash
source ~/hermes-agent/venv/bin/activate
python -m pytest tests/ -q   # ~3000 tests, ~3 min
```

---

## 12. KNOWN PITFALLS

- DO NOT hardcode `~/.hermes` paths — use `get_hermes_home()` (breaks profiles)
- DO NOT use `simple_term_menu` (tmux/iTerm2 ghosting)
- DO NOT use subprocess `hermes` CLI for chapter generation — use direct Ollama API
- DO NOT run `args = parser.parse_args()` twice in the same script (existing bug in draft-chapter/orchestrator.py line 516/523)
- The `draft-chapter/orchestrator.py` has a double `parse_args()` bug — do NOT copy this pattern into new agents
- model.api_key field in config.yaml should NOT be set to "ollama" — leave it empty or use proper key

---

## 13. SESSION STARTUP CHECKLIST (For Local Model Sessions)

When starting a new Hermes session with the local model, do this:

```
1. Read this file: cat ~/hermes-agent/AGENTS.md
2. Check current workbook: ls ~/.hermes/ebook-factory/workbooks/
3. Check what's already drafted: ls ~/.hermes/ebook-factory/workbooks/book-<topic>/w-drafts/
4. Check what's approved: ls ~/.hermes/ebook-factory/workbooks/book-<topic>/w-polished/
5. If no workbook: run Outliner first
6. If workbook exists: run Chapter-Builder for next chapter
7. If all chapters approved: run Packager
```

---

*This file is the single source of truth for the bookforge ebook factory system.*
*Keep it updated as agents are built and the pipeline evolves.*
*Every session — human or AI — should start by reading this file.*
