---
name: ebook-analyzer
category: ebook-factory
description: Parse KDP sales data, extract patterns, and write insights to LEARNING.md
---

# Ebook Analyzer Agent

Analyzes KDP sales data (XLSX files from Amazon Dashboard) to extract patterns, calculate metrics, and generate actionable insights for future book topics.

---

## Purpose

The Analyzer is the **intelligence core** of the factory. It:
1. Parses raw KDP sales reports (Dashboard and Prior Month Royalties XLSX)
2. Extracts per-book metrics (royalties, units, KENP, CTR proxies)
3. Detects patterns across niches, pricing, word counts, keywords
4. Appends structured insights to `~/books/factory/LEARNING.md`
5. Informs the Planner agent (Phase 1) about which topics work best

**Without Analyzer:** Planner guesses topics blindly
**With Analyzer:** Planner selects topics based on historical success patterns

---

## Architecture

### Phase 1 (Current) — Own Sales Data Only

```
KDP XLSX Files
     │
     ▼
┌───────────────┐
│  Data Parser  │ ← Parse April Dashboard + March Prior Month
├───────────────┤
│  Metrics Calc │ ← Per-book: ROI, KENP ratio, niche score
├───────────────┤
│  Pattern Eng. │ ← Compare across books, find winners/losers
├───────────────┤
│  LEARNING.md  │ ← Append structured insights
└───────────────┘
```

**Outputs:**
- LEARNING.md entry with:
  - Book performance summary
  - Patterns detected
  - Recommendations for next topics

**Testing:** Run on existing data:
- Home Network Security (April: £2.60, 1 unit, 28 KENP)
- Second Brain (March: $3.48, 1 unit, 3 KENP)
- 80/20 Guide (March: $3.47, 1 unit)
- Weekly Review Systems (March: $3.48, 1 unit)

---

### Phase 2 (Future) — Competitor Intelligence

After Phase 1 is stable:
- Add `browser_tool` scraping for competitor data (review counts, rankings)
- Track competitor book covers, pricing, keyword strategies
- Integrate with BookBeam.io API if cost-effective
- Enhance pattern detection with market-wide data

**Not built now** — need more sales volume first

---

## Data Sources

### KDP Dashboard XLSX (April Data)

**Structure:**
- `Summary` sheet: Total units, KENP, royalties by currency
- `Combined Sales` sheet: Per-book breakdown (ASIN, marketplace, royalty type, units, price)
- `KENP Read` sheet: Per-book Kindle Edition Normalized Pages read

**Example row (Combined Sales):**
```
Title: The No-BS Guide to Home Network Security
ASIN: B0GS55C2B4
Marketplace: Amazon.co.uk
Units Sold: 1
Avg. List Price: £3.72
Royalty: £2.60 (70%)
Currency: GBP
```

### KDP Prior Month Royalties XLSX (March Data)

**Structure:**
- `eBook Royalty` sheet: Per-book royalties, units, file size
- `KENP Read` sheet: Per-book KENP pages read
- `Total Earnings` sheet: Combined view of all royalties

**Example row (eBook Royalty):**
```
Title: The 80/20 Guide to Getting More Done
ASIN: B0GRQFX2TZ
Marketplace: Amazon.com
Units Sold: 1
Royalty: $3.47 (70%)
Avg. File Size: 0.17 MB
```

---

## Metrics Calculated

### Per-Book Metrics

| Metric | Calculation | Purpose |
|--------|-------------|---------|
| **Royalty per unit** | `royalty / units_sold` | Price performance check |
| **KENP per unit** | `kenp_pages / units_sold` | Reader engagement proxy |
| **Niche score** | `weighted(royalty, units, keng)` | Overall performance |
| **ROI estimate** | `(royalty - write_cost) / write_cost` | Profitability |
| **Conversion proxy** | `units / impressions_estimate` | CTR estimate (later) |

### Cross-Book Patterns

- **Niche comparison:** Which topics perform better?
- **Pricing analysis:** $3.99 vs $4.99 vs £3.72 conversion
- **Marketplace effect:** Amazon.com vs Amazon.co.uk vs Amazon.de
- **File size correlation:** Does book length affect KENP?
- **Timing patterns:** Do certain months sell better?

---

## LEARNING.md Format

**Append-only entries** (never overwrite past lessons):

```markdown
## [YYYY-MM-DD] Book: <Title> (ASIN: <asin>)

### Performance Summary
- **Royalty:** $X.XX (<currency>)
- **Units Sold:** N
- **KENP Pages:** N
- **Marketplace:** Amazon.<region>
- **Price:** $X.XX (<currency>)
- **Royalty Tier:** 70%

### Metrics
- **Royalty/unit:** $X.XX
- **KENP/unit:** N pages
- **Niche Score:** X/10

### Patterns Observed
- ✅ [What worked: e.g., "Cybersecurity niche shows early traction"]
- ⚠️ [Concerns: e.g., "Only 1 sale in 30 days — need more exposure"]
- 🔍 [Insights: e.g., "UK marketplace converts at £2.60/unit"]

### Recommendations
1. [Actionable insight: "Similar tech topics likely to convert"]
2. [Pricing recommendation: "$4.99 optimal for US market"]
3. [Keyword suggestion: "Include 'family' + 'protection'"]

---
```

---

## Execution Workflow

### 1. Discover KDP Files

```python
# Find all XLSX files in ~/Downloads/
# Match patterns:
#   - KDP_Dashboard-*.xlsx (current month)
#   - KDP_Prior_Month_Royalties-*.xlsx (previous month)
```

### 2. Parse Each File

```python
# For each XLSX:
#   - Check date range (March 2026, April 2026)
#   - Extract Summary + Combined Sales + KENP sheets
#   - Normalize field names (handle "Unnamed: N" columns)
#   - Calculate per-book metrics
```

### 3. Detect Patterns

```python
# Compare across all books:
#   - Group by niche/category
#   - Compare royalty performance
#   - Compare KENP engagement
#   - Flag outliers (high/low performers)
```

### 4. Write LEARNING.md Entry

```python
# For each book analyzed:
#   - Append structured markdown to LEARNING.md
#   - Include metrics, patterns, recommendations
#   - Add date, ASIN for reference
```

### 5. Update Planner Input

```python
# Analyzer output feeds into Planner:
#   - Planner reads LEARNING.md before selecting next topic
#   - Planner scores topics against historical patterns
#   - Planner avoids failed niches, duplicates winners
```

---

## Code Structure

```
~/.hermes/hermes_skills/analyzer/
├── SKILL.md              # This file
├── config.yaml           # Parser configurations
├── parser.py             # XLSX parsing logic (Phase 1)
├── metrics.py            # Metrics calculation engine
├── patterns.py           # Pattern detection & comparison
├── learner.py            # LEARNING.md writer
└── analyzer.py           # Main execution entry point
```

---

## Phase 1 Testing

**Test with existing data:**

1. **Run Analyzer** on April + March KDP files
2. **Verify outputs:**
   - Parses all 4 books correctly
   - Calculates accurate metrics (royalty, KENP, units)
   - Detects niche patterns (tech vs productivity)
3. **Check LEARNING.md:**
   - Contains structured entries for each book
   - Recommendations are actionable
   - Format matches specification

**Expected Insights from Test Data:**

- **Home Network Security** (April, UK): £2.60, 28 KENP → Tech niche performs, high engagement
- **Second Brain** (March, US): $3.48, 3 KENP → Productivity niche, lower engagement but steady
- **80/20 Guide** (March, US): $3.47 → Business strategy niche, 1 sale
- **Weekly Review** (March, US): $3.48 → Productivity niche, 1 sale

**Pattern to detect:**
- Tech/Security niche: Higher KENP (more pages read) → better Amazon ranking
- Productivity/Business: Consistent $3.47-$3.48 per sale → predictable revenue

---

## Future Enhancements (Phase 2)

**Competitor Intelligence:**
- `browser_tool` scraping of Amazon book pages
- Extract: review count, ratings, price history, keyword rankings
- BookBeam.io API integration (if cost-effective)
- Cover style analysis (what colors/styles convert?)

**Advanced Metrics:**
- CTR (click-through rate) estimation from impressions data
- ROI per hour written (if write-time tracking exists)
- Seasonal trend analysis (holiday spikes, etc.)

**Cross-Platform Tracking:**
- Book sales on other platforms (Gumroad, Leanpub)
- Newsletter signups per book (if tracked)
- Email list growth correlation

---

## Known Limitations

**Phase 1 (Current):**
- Only tracks own sales data (no competitor insights)
- No CTR data (Amazon doesn't expose impressions)
- Manual keyword tracking (no automated rank monitoring)
- Limited to XLSX format (no API streaming yet)

**Solutions:**
- Phase 2 adds competitor data
- CTR estimation via sales / search volume ratio
- Keyword tracking via browser tool scraping

---

## Integration Points

### Feeds To:
- **Planner Agent:** Reads LEARNING.md before selecting topics
- **Researcher Agent:** Validates topics against historical success patterns
- **Orchestrator:** Can query LEARNING.md for progress reports

### Feeds From:
- **KDP Exports:** XLSX files from Amazon Dashboard
- **User Manual Input:** Can append notes to LEARNING.md if needed
- **Book Metadata:** `~/books/<BOOKTITLE>/config.yaml` for book details

---

## Error Handling

**Missing data:**
- If XLSX has no sales → report "No activity detected"
- If KENP sheet missing → estimate 0 KENP
- If currency mismatch → convert to USD standard

**Parsing errors:**
- Log warning, skip malformed rows
- Continue processing other books

**LEARNING.md write errors:**
- Retry with temp file, then atomic move
- Log failure, notify user

---

## Usage

**Manual trigger:**
```bash
hermes run ebook-analyzer
```

**Automatic (future):**
- Cron job runs Analyzer weekly
- Triggers Planner if LEARNING.md has new insights
- Notifies Orchestrator of pattern changes

**Configurable:**
- `~/.hermes/config.yaml` → `analyzer.kdp_directory`
- `analyzer.learning_md_path`
- `analyzer.numeric_thresholds` (min sales, min royalty)

---

## Quick Reference

**Key Files:**
- Input: `~/Downloads/KDP_*.xlsx`
- Output: `~/books/factory/LEARNING.md`
- Config: `~/.hermes/hermes_skills/analyzer/config.yaml`

**Metrics to Watch:**
- Royalty/unit > $3.00 (target price performance)
- KENP/unit > 20 pages (engagement target)
- Niche score > 7/10 (good topic)

**Success Criteria:**
- Planner selects topics with ≥60% match to high-performing niches
- Analyzer detects patterns BEFORE publishing next book
- LEARNING.md entries are actionable (not just data dumps)
