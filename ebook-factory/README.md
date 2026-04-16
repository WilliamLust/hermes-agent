# Ebook Factory — Pipeline Overview

Automated pipeline for producing commercial nonfiction ebooks for Amazon KDP.
Built on top of [Hermes Agent](https://github.com/NousResearch/hermes-agent).

**Architecture:** Claude Sonnet (orchestration) + Qwen 35B-A3B (local drafting via Ollama)  
**Cost per book:** ~$1-2 orchestration + $0.09 cover = under $2/book  
**Time per book:** ~90 minutes unattended after outline approval

---

## Pipeline Stages

```
Phase 0: DISCOVERY
  Researcher  → scrapes Amazon BSR + competitor data → LEARNING.md
  Outliner    → generates 10-chapter book outline from topic plan

Phase 1: CHAPTER FACTORY  
  Chapter-Builder × 10 → drafts 2800-word chapters via local Ollama
                        → self-validates, self-refines (3 iterations max)

Phase 2: HUMAN REVIEW
  Telegram Review Workflow → sends chapter summaries to phone
                           → approve/redo via Telegram reply

Phase 3: ASSEMBLY
  Packager → EPUB + PDF + KDP metadata JSON

Phase 4: COVER
  Cover Generator → Ideogram API background + Pillow text compositing
                 → $0.09/cover, 1600×2560 KDP-compliant JPEG

Phase 5: UPLOAD
  KDP Uploader → Playwright automation fills all KDP form fields
               → saves as draft, never auto-publishes
               → Telegram notification for human final review

Phase 6: LEARNING (continuous)
  Self-Improvement Agent → weekly cron (Sundays 8AM)
                         → harvests live BSR from published books
                         → updates chapter prompts from catalog patterns
                         → scouts next topics via Google Trends
```

---

## Agent Scripts

| Agent | Script | Description |
|-------|--------|-------------|
| Researcher | `skills/researcher/researcher.py` | Amazon niche analysis with BSR. Firecrawl→Scrapling→Camoufox fallback |
| Outliner | `skills/outliner/orchestrator.py` | Generates 10-chapter outline from topic plan |
| Chapter-Builder | `skills/chapter-builder/chapter_builder.py` | Drafts + validates + refines chapters via Ollama |
| Telegram Review | `skills/telegram-review/review_workflow.py` | Phone-based approve/redo workflow |
| Packager | `skills/packager/packager.py` | Assembles EPUB + PDF + KDP metadata |
| Cover Generator | `skills/cover-generator/cover_generator.py` | Ideogram API + Pillow compositing |
| KDP Uploader | `skills/kdp-upload/kdp_upload.py` | Playwright browser automation for KDP form |
| Self-Improvement | `skills/self-improvement/self_improvement.py` | Weekly learning cycle, 5 modules |

---

## Quick Start

```bash
# 1. Research a niche
cd skills/researcher/
python3 researcher.py --niche "productivity for ADHD adults"

# 2. Generate outline (after creating topic_plan file)
cd skills/outliner/
python3 orchestrator.py --chapters 10

# 3. Draft all chapters (parallel-safe)
cd skills/chapter-builder/
for ch in 1 2 3 4 5 6 7 8 9 10; do
  python3 chapter_builder.py --chapter $ch &
done
wait

# 4. Review via Telegram
cd skills/telegram-review/
python3 review_workflow.py --send --listen

# 5. Package
cd skills/packager/
python3 packager.py

# 6. Generate cover
cd skills/cover-generator/
python3 cover_generator.py --niche productivity --variations 3

# 7. Upload to KDP (dry run first)
cd skills/kdp-upload/
python3 kdp_upload.py --dry-run
python3 kdp_upload.py --visible  # watch automation, then publish manually
```

---

## Environment Setup

Required in `~/.hermes/.env`:
```
ANTHROPIC_API_KEY=...
FIRECRAWL_API_KEY=...        # Hobby plan, 3000 credits/month
IDEOGRAM_API_KEY=...         # ~$0.09/cover
TELEGRAM_BOT_TOKEN=...       # @Hermes_Ebook_Factory_Bot
TELEGRAM_CHAT_ID=...
KDP_EMAIL=...
KDP_PASSWORD=...
```

Local model: `qwen3.5:35b-a3b-q4_k_m` via Ollama at `localhost:11434`

---

## Published Catalog

12 books published as of April 2026. Niches: productivity, health-wellness, tech-security, AI-productivity.

Book 13 in output: *Productivity for ADHD Adults: The No-BS System That Actually Works* (26,694 words, April 2026)

---

## Key Design Decisions

- **Never auto-publish.** KDP uploader always saves as draft. Human publishes.
- **Firecrawl → Scrapling → Camoufox** tiered fallback for Amazon scraping
- **BSR is 40% of niche score** — proven sales velocity outweighs review count
- **Ideogram for background art, Pillow for text** — font control beats AI text rendering
- **Self-improvement agent patches chapter_builder.py** — the factory literally gets smarter each week

See `skills-meta/` for full architecture decisions and known pitfalls.
