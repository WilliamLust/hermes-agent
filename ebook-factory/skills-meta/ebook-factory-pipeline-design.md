---
name: ebook-factory-pipeline-design
category: ebook-factory
description: "Architecture decisions, missing agents, model strategy, and integration design for the ebook factory. Load this before planning any new factory work."
tags: [ebook, pipeline, architecture, design, telegram, researcher, upload, model-strategy]
version: 1.0
---

# Ebook Factory — Pipeline Design & Architecture Decisions

Reference this before starting new build work. Records confirmed decisions and known gaps.

---

## Model Strategy: Anthropic/Qwen Hybrid

The factory is designed for local execution but the right split is:

```
Orchestration (deciding what to run):    Claude Sonnet (Anthropic) — reliability, complex DOM/decisions
Chapter Drafting (10 chapters × 2800w): qwen3.5:35b-a3b-q4_k_m (local, free, MoE = fast + smart)
Chapter Refinement:                      qwen3.5:35b-a3b-q4_k_m
Outlining:                               qwen3.5:35b-a3b-q4_k_m (262k ctx handles full LEARNING.md)
Topic Research synthesis:                qwen3.5:9b (fast, structured JSON output, no prose needed)
Packaging:                               Pure Python — no LLM needed
Browser/upload tasks:                    Claude (complex DOM reasoning)
```

Why: 28,000 tokens of output per book at Sonnet pricing ≈ $0.84/book. On local Qwen it's free.
At 5 books/month, total orchestration cost ≈ $1-2/month. Total pipeline cost < $4/book.

**Primary local model: qwen3.5:35b-a3b-q4_k_m**
- MoE architecture: 36B total parameters, only 3B active per inference pass
- Faster than the dense 27B at same or lower VRAM usage
- 262k context window — can ingest full LEARNING.md + outline in one pass
- On disk: 23GB at Q4_K_M quantization

**Fallback chain:**
1. qwen3.5:27b-16k  — if 35B shows VRAM pressure
2. qwen3.5:27b-8k   — speed-critical tasks
3. qwen3.5:9b       — research/planning structured output only

**Design constraints:**
- Loses context in long multi-step reasoning chains → solve with standalone scripts, not LLM orchestration
- Occasionally stops early below word count → `num_predict: 6000` + explicit "write exactly N words"
- Generic chapter titles on outliner → always manually review 01_outline.md before Chapter-Builder

---

## Researcher Agent — BUILT ✓

**Status:** Complete with BSR enrichment. Script at `~/.hermes/ebook-factory/skills/researcher/researcher.py`

**Scoring model (BSR-integrated):**
- BSR signal: 40% weight (fetches top 3 competitor product pages)
- Demand (review counts): 30%
- Price signal: 20%
- Competition: 10%

**Credit cost per scan:** ~4 Firecrawl credits (1 search + 3 product pages). Use `--no-bsr` to save credits (1 credit, less accurate).

**BSR interpretation:**
- BSR ≤ 5,000 → proven demand, proceed
- BSR 5,000–20,000 → active market, strong angle needed
- BSR > 100,000 → thin demand, pivot to sub-niche The `ebook-project/agents/research/` directory was empty.

**What it should do:**
1. Take a niche keyword (e.g. "productivity", "home security")
2. Scrape Amazon search results for competitor titles, review counts, BSR
3. Scrape Google Trends or related keyword data
4. Score market opportunity (demand vs competition)
5. Append enriched findings to `~/books/factory/LEARNING.md`

**Build approach:**
- Primary: Firecrawl API (`FIRECRAWL_API_KEY` in ~/.hermes/.env, hobby plan 3000 credits/month)
  - Use `hybrid-web-extraction` Hermes skill as reference
  - Amazon product pages, search results, reviews
- Fallback: browser-use (Python Playwright) for pages Firecrawl can't reach
  - `uv add browser-use && uvx browser-use install` to get Chromium
  - Useful for KDP category browsing, login-gated pages
- Do NOT use Browserbase (requires paid API key not configured)

**Location when built:**
`~/.hermes/hermes_skills/researcher/orchestrator.py`

**Pipeline position:** Runs after Analyzer, feeds into Planner.
```
Analyzer → LEARNING.md ← Researcher  →  Planner  →  Outliner
```

---

## KDP Upload Agent — BUILT ✓

**Status:** Complete. Script at `~/.hermes/ebook-factory/skills/kdp-upload/kdp_upload.py`

**Setup required:** Add `KDP_EMAIL` and `KDP_PASSWORD` to `~/.hermes/.env`

**Usage:**
```bash
python3 kdp_upload.py --dry-run          # preview what would be filled
python3 kdp_upload.py --visible          # watch automation run
python3 kdp_upload.py                    # headless run
```

**Safety guarantee:** Publish button is NEVER clicked. Always saves as draft.
Sends Telegram notification when draft is ready for human review.

**Critical fact: Amazon KDP has NO public API.** There is no KDP API. Any claim of one is
scraping, Selenium, or internal tooling.

**Chosen approach: Telegram gate + browser semi-automation**
1. Packager finishes → sends Telegram notification with cover image + metadata preview
2. William approves via Telegram reply
3. Hermes opens KDP in browser session (browser-use or Hermes browser tool)
4. Pre-fills form fields from kdp-metadata.json
5. William does final review + submit (keeps human judgment at the money step)

This is resilient to Amazon UI changes — only the field selectors need updating, not the whole flow.

**Why not full automation:**
- Amazon TOS grey area
- UI changes break hard automation routinely
- The upload itself takes <5 min manually — not the bottleneck

**Dependencies to install when building:**
```bash
uv init && uv add browser-use
uvx browser-use install  # downloads Chromium/Playwright
```

**Or use Hermes built-in browser tool** — requires Browserbase API key (not currently configured).

---

## Telegram Human Review Workflow — BUILT ✓

**Status:** Complete. Script at `~/.hermes/ebook-factory/skills/telegram-review/review_workflow.py`

**Usage:**
```bash
python3 review_workflow.py --send --listen --book-dir PATH
```

**Telegram commands:** `approve 1,2,3` / `approve all` / `redo 4,6` / `status`

Bot auto-suggests packager command when all chapters approved.

**Setup:**
```bash
# 1. Create bot: message @BotFather on Telegram → /newbot
# 2. Get chat ID: message the bot, hit https://api.telegram.org/bot<TOKEN>/getUpdates
# 3. Add to ~/.hermes/.env:
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_id

# 4. config.yaml:
telegram:
  enabled: true
```

**Designed review flow for chapters:**
- After all chapters drafted → Hermes sends summary per chapter (word count, validation status, first 100 words)
- William replies: "approve 1,2,3,5,7,8,9,10" and "redo 4,6"
- Hermes moves approved to w-polished/, re-runs Chapter-Builder on rejected with --force
- When all approved → triggers Packager automatically

**Designed review flow for new books:**
- Planner generates topic_plan_latest.md → Hermes sends top 3 topics to Telegram
- William picks one (replies "1" or topic name)
- Hermes runs Outliner with that topic

This flow requires a small message handler wrapper on top of the existing Telegram gateway.

---

## Cover Generation — BUILT ✓

Script at `~/.hermes/ebook-factory/skills/cover-generator/cover_generator.py`

Architecture: Ideogram API (background art, $0.03-$0.06) + Pillow (text compositing, free)
Cost: $0.09/cover (TURBO + upscale). 5 books/month = $0.45.
Output: 1600x2560 JPEG, KDP-compliant, thumbnail sent to Telegram.

Niche palettes: productivity (orange/black), health (teal/green), tech-security (navy/green),
parenting (warm yellow/coral), business (navy/blue), self-help (purple).

IDEOGRAM_API_KEY set in ~/.hermes/.env.

Archived from `ebook-project/agents/cover/`:
- `generate_cover_flux1.py` — uses local ComfyUI FLUX workflow
- `flux_schnell_workflow.json` — ComfyUI workflow definition
- `generate_cover_falai.py` — fal.ai API fallback

ComfyUI is already running at `~/ComfyUI/`. The cover agent code needs to be moved to
`~/.hermes/ebook-factory/skills/cover-generator/` and wired into the packager.

Current packager produces a placeholder `cover.jpg` path in kdp-metadata.json.

---

## Pipeline Phases — Complete Status Map

```
Phase 0: DISCOVERY
  ✓ Analyzer     — ~/.hermes/hermes_skills/analyzer/orchestrator.py
  ✗ Researcher   — NOT BUILT (Firecrawl + Amazon scraping)
  ✓ Planner      — ~/.hermes/hermes_skills/planner/orchestrator.py
  ✓ Outliner     — ~/.hermes/skills/ebook-factory/skills/outliner/orchestrator.py

Phase 1: CHAPTER FACTORY
  ✓ Chapter-Builder — ~/.hermes/ebook-factory/skills/chapter-builder/chapter_builder.py
    (built, verified logic, NOT yet live-tested with Ollama drafting real content)

Phase 2: HUMAN REVIEW
  ✗ Telegram gate  — not enabled (needs bot token)
  ✗ Review handler — not built (approve/reject message loop)

Phase 3: ASSEMBLY
  ✓ Packager — ~/.hermes/ebook-factory/skills/packager/packager.py
    HTML + PDF (WeasyPrint 68.1) + EPUB (Calibre fallback) + KDP metadata
    Cover generation NOT integrated (placeholder only)

Phase 4: UPLOAD (not in original plan, needs design + build)
  ✗ KDP browser automation — not built
  ✗ Telegram approval gate — not built

Phase 5: COVER (exists in archive, not wired in)
  ~ generate_cover_flux1.py archived at ~/books/factory/archive-cleanup-2026-04/ebook-project-agents/cover/
```

---

## Self-Improvement Agent — BUILT ✓

**Status:** Complete. Cron: every Sunday 8AM (job ID: 35038329cd1a).
Script: `~/.hermes/ebook-factory/skills/self-improvement/self_improvement.py`

**Five modules:**
- Harvester: scrapes live BSR for every published book (~12 Firecrawl credits)
- Analyzer: cross-references research predictions vs actual performance
- Refiner: patches chapter_builder.py SYSTEM_PROMPT with learned improvements
- Scout: finds top 5 next topics via Google Trends + Movers & Shakers → Telegram Sunday brief
- Auditor: flags underperforming books, identifies top performers to replicate

**The loop:** Book sells → Harvester captures it → Analyzer finds patterns →
Refiner improves prompts → Scout targets better niches → Better books → repeat.
2. Live test Chapter-Builder with Ollama on 1 chapter
3. Build Researcher agent (Firecrawl → Amazon scraping)
4. Build Telegram chapter review handler
5. Wire in cover generator from archive
6. Build KDP browser upload helper
