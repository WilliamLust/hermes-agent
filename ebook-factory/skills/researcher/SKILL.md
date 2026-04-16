---
name: ebook-factory-researcher
category: ebook-factory
description: "Researcher agent — scrapes Amazon Kindle market data for a niche keyword, scores opportunity, appends to LEARNING.md, notifies via Telegram."
tags: [ebook, research, amazon, firecrawl, scrapling, camoufox, market-analysis]
version: 1.0
---

# Ebook Factory — Researcher Agent

Scrapes Amazon Kindle Store competitor data for a niche keyword and appends
market intelligence to ~/books/factory/LEARNING.md.

## Location
`~/.hermes/ebook-factory/skills/researcher/researcher.py`

## Usage

```bash
source ~/hermes-agent/venv/bin/activate
cd ~/.hermes/ebook-factory/skills/researcher/

# Standard run (writes to LEARNING.md + Telegram notification)
python3 researcher.py --niche "home organization"

# Dry run (prints output, doesn't write)
python3 researcher.py --niche "sleep health" --dry-run

# Force a specific tier
python3 researcher.py --niche "gut health" --tier 2   # Force Scrapling
python3 researcher.py --niche "gut health" --tier 3   # Force Camoufox

# JSON output
python3 researcher.py --niche "productivity" --json
```

## Tiered Fallback Strategy

```
Tier 1 → Firecrawl API       (fast, $0.003/credit, handles most pages)
Tier 2 → Scrapling Stealth   (Cloudflare bypass, headless browser)
Tier 3 → Camoufox            (anti-detect Firefox, nuclear option)
```

## Output

Appends a section to ~/books/factory/LEARNING.md:

```
## [YYYY-MM-DD] Researcher: Niche Analysis — Topic Name
Market Score: X.X/10 — verdict
| Demand | Competition | Avg Reviews | Avg Price | ...
Top Competitor Titles Found: (up to 5 real titles)
Recommendations: proceed/avoid guidance
```

Also sends Telegram notification to @Hermes_Ebook_Factory_Bot.

## Pipeline Position

```
Analyzer → LEARNING.md ← Researcher → Planner → Outliner → Chapter-Builder
```

Run researcher before Planner when starting a new topic to enrich LEARNING.md
with live market data.

## Parser Notes

- Extracts titles from Amazon image alt-text links (most reliable across page variants)
- Supplements with bold markdown links where available
- Uses bold link positions for rating/price data windows (data appears near bold links)
- Handles page variants: US store, UK redirects, format differences
- Review counts may be 0 if page variant doesn't show them inline — this is non-blocking

## Known Pitfalls

- Amazon occasionally routes to UK store (GBP prices) even with gl=us param — prices
  will be in GBP but scoring still works; note in LEARNING.md entry
- Firecrawl caches pages — running twice within ~5min returns same content
- If Firecrawl credits exhausted (402), Scrapling auto-activates
- Review counts sometimes 0 due to page layout variance — not blocking, score still valid
- `scrapling install` needed once after pip install (installs Playwright browsers)

## Dependencies (already installed)

```bash
pip install "scrapling[fetchers]" camoufox
scrapling install          # Playwright browsers
python3 -m camoufox fetch  # Camoufox Firefox binary
```
