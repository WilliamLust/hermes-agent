---
name: ebook-factory-self-improvement
category: ebook-factory
description: "Self-improvement agent — learns from every published book and research scan, continuously improving niche selection, chapter quality, and market timing. Five modules, runs weekly via cron."
tags: [ebook, self-improvement, learning, patterns, optimization, cron]
version: 1.0
---

# Ebook Factory — Self-Improvement Agent

The factory's brain. Learns from the catalog and market signals, improving
every other agent automatically over time.

## Location
`~/.hermes/ebook-factory/skills/self-improvement/self_improvement.py`

## Run Manually

```bash
source ~/hermes-agent/venv/bin/activate
cd ~/.hermes/ebook-factory/skills/self-improvement/

# Full cycle (all 5 modules)
python3 self_improvement.py --all

# Individual modules
python3 self_improvement.py --harvest        # Scrape live BSR for published books
python3 self_improvement.py --analyze        # Pattern analysis across catalog
python3 self_improvement.py --refine-prompts # Update chapter/outliner prompts
python3 self_improvement.py --scout          # Find next high-potential topics
python3 self_improvement.py --audit          # Retrospective on published books
python3 self_improvement.py --report         # Print current state, no writes

# Simulate without writing anything
python3 self_improvement.py --all --dry-run
```

## Cron Schedule

Runs every Sunday at 8:00 AM automatically (cron job ID: 35038329cd1a).
Sends Telegram summary to @Hermes_Ebook_Factory_Bot when complete.

## Five Modules

### Module 1: Performance Harvester
- Parses all book entries from LEARNING.md (title, ASIN, royalty, KENP)
- Scrapes live BSR + review counts from Amazon product pages (1 Firecrawl credit each)
- Appends dated performance snapshot to LEARNING.md

**Fires:** weekly, uses ~12 Firecrawl credits for 12 books

### Module 2: Pattern Analyzer
- Groups performance by niche (revenue, KENP/unit, royalty/unit)
- Detects scoring calibration issues (if low-score books outperform high-score ones)
- Identifies engaging vs thin-engagement books
- Outputs `patterns.json` with weight recommendations

**Learns:** which niches actually perform vs which research predicts well

### Module 3: Prompt Refiner
- Reads patterns.json to identify content quality issues
- Updates `prompt_overrides.json` with specific improvements:
  - Engagement requirements when KENP/unit is low
  - Specificity requirements when content is too generic
  - Niche-specific guidance based on what's working
  - Quality gates (rules every chapter must pass)
- **Patches chapter_builder.py** to load overrides at runtime
- Quality rules currently applied to every chapter:
  - Each chapter must have a concrete, specific example
  - Chapter conclusions must include one actionable takeaway
  - No "simply" or "just" without a specific process
  - Minimum 3 H2 headings per chapter

**Effect:** Chapter 50 is measurably better than Chapter 5

### Module 4: Topic Scout
- Generates adjacent topic candidates from catalog niches
- Scrapes Amazon Movers & Shakers for trending titles (1 credit)
- Checks Google Trends interest for top candidates
- Scores candidates by: trend interest, adjacency to best-performing niche, specificity
- Writes `topic_candidates.md` with ranked recommendations
- Sends weekly Telegram brief: top 3 topics to research

**Output: every Sunday you wake up to 3 researched topic suggestions**

### Module 5: Quality Auditor
- Audits all published books against performance benchmarks
- Flags: overestimated demand, low reader engagement (KENP), KDP Select inefficiency
- Identifies top performers for replication
- Appends to `audit_log.json`
- Sends Telegram alert for books needing attention

**Loop:** Auditor → Analyzer (next week) → Refiner → better books

## Output Files

```
~/.hermes/ebook-factory/skills/self-improvement/
├── patterns.json          ← Niche performance + scoring weights
├── prompt_overrides.json  ← Chapter-builder prompt additions
├── topic_candidates.md    ← This week's 5 top topics to research
├── audit_log.json         ← Per-book retrospective flags
└── improvement_report.md  ← Human-readable weekly summary
```

## Data Flow

```
LEARNING.md (published books + researcher scans)
    ↓ Module 1 (Harvester: adds live BSR)
    ↓ Module 2 (Analyzer: patterns.json)
    ↓ Module 3 (Refiner: prompt_overrides.json → chapter_builder.py)
    ↓ Module 4 (Scout: topic_candidates.md → Telegram Sunday brief)
    ↓ Module 5 (Auditor: audit_log.json)
    ↓ (next week: Module 2 reads audit_log for tighter patterns)
```

## The Feedback Loop (Why This Matters)

Month 1: Factory publishes books, collects sales data
Month 2: Harvester detects KENP/unit < 15 on 3 books → Refiner adds engagement rules
Month 3: New books using refined prompts show KENP/unit > 30
Month 4: Auditor flags productivity as top niche → Scout focuses adjacent topics
Month 6: Research score calibration has learned from 6+ books vs predictions

The factory gets smarter every week without you having to do anything.

## Known Limitations (First Cycle)

With 0 actual sales data flowing in yet, the first run shows $0 everywhere.
The agent is fully functional — it just needs real KDP sales data to produce
meaningful patterns. That data arrives naturally as books sell.

The LEARNING.md historical data has royalties populated but `$` values need
to be confirmed against KDP. Once KDP_EMAIL/KDP_PASSWORD are set, the Harvester
can be enhanced to pull the actual dashboard data rather than just BSR scraping.

## Credit Cost

Per weekly cycle:
- Module 1 (Harvester): ~12 Firecrawl credits (1 per published book)
- Module 4 (Scout, Movers & Shakers): 1 Firecrawl credit
- Total: ~13 credits/week, ~52/month

At the hobby plan (3,000 credits/month), self-improvement uses 1.7% of budget.
