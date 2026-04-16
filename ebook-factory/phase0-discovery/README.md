# Phase 0: Discovery Agents

These agents run **before** the Outliner to identify high-potential book topics from KDP sales data.

## Flow

```
Amazon KDP Reports (.xlsx)
        ↓
    Analyzer    → reads KDP Dashboard + Royalties → appends to LEARNING.md
        ↓
    Planner     → reads LEARNING.md → scores niches → topic_plan_latest.md
        ↓
    Outliner    → reads topic_plan → generates 10-chapter book outline
```

---

## Analyzer

Parses Amazon KDP Excel reports and writes structured insights to LEARNING.md.

**Required input:** Download from KDP → Reports → Download report:
- `KDP_Dashboard-*.xlsx`
- `KDP_Prior_Month_Royalties-*.xlsx`

Place in `~/Downloads/` (configured in `analyzer/config.yaml`).

```bash
cd ~/.hermes/hermes_skills/analyzer/
source ~/hermes-agent/venv/bin/activate

# Dry run (see what would be written)
DRY_RUN=true python3 orchestrator.py

# Real run (writes to LEARNING.md)
python3 orchestrator.py
```

**Status:** Tested ✅ — parses real KDP data, correctly categorizes niches, writes to LEARNING.md.

---

## Planner

Reads LEARNING.md, scores niches by royalty/KENP performance, generates 5 topic recommendations.

```bash
cd ~/.hermes/hermes_skills/planner/
source ~/hermes-agent/venv/bin/activate

python3 orchestrator.py

# Output: ~/.hermes/output/planner/topic_plan_latest.md
```

**Status:** Tested ✅ — reads LEARNING.md, scores 6 niches, generates ranked topic plan.

**Known limitation:** Title templates are generic ("The X Blueprint: Building Mastery in 30 Days"). The niche scoring logic is correct; the title generation needs improvement. The Researcher agent provides better topic selection via BSR — use both for cross-validation.

---

## Dependencies

```bash
pip install openpyxl pyyaml  # already installed in venv
```
