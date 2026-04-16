# KDP Analyzer Module

Automated analysis pipeline for Amazon KDP (Kindle Direct Publishing) sales data.

## What It Does

Parses Amazon KDP Excel reports, calculates per-book metrics (royalty/unit, KENP/unit), detects patterns, and writes structured insights to `LEARNING.md` for future topic selection.

## Quick Start

```bash
# Basic usage
cd ~/.hermes/hermes_skills/analyzer
python3 orchestrator.py

# Override KDP directory
KDP_DIR=/path/to/KDP/files DRY_RUN=true python3 orchestrator.py

# Use wrapper script
./run_analysis.sh --kdp-dir /custom/path --learning /custom/path/LEARNING.md
./run_analysis.sh --dry-run  # Don't write to LEARNING.md
```

## Files

- `config.yaml` — Configuration (KDP path, LEARNING.md path)
- `parser.py` — Excel file parsing (openpyxl)
- `metrics.py` — Metric calculations & pattern detection
- `learner.py` — LEARNING.md writer
- `orchestrator.py` — Main pipeline orchestrator
- `run_analysis.sh` — Shell wrapper
- `__init__.py` — Package exports

## Configuration

Edit `config.yaml`:

```yaml
kdp_directory: /home/bookforge/Downloads
learning_md_path: /home/bookforge/books/factory/LEARNING.md
```

Or override via environment:

```bash
KDP_DIR=/custom/path
LEARNING_PATH=/custom/path/LEARNING.md
DRY_RUN=true
python3 orchestrator.py
```

## Metrics

**KENP/unit** — Kindle Edition Normalized Pages per unit sold (reader engagement)
**Royalty/unit** — Earnings per sale
**Niche Score** — Weighted composite of engagement, royalty efficiency, niche strength

## Pipeline

1. **Parse** KDP Excel files (dashboard, prior-month, KENP)
2. **Calculate** per-book metrics and niche aggregates
3. **Detect** patterns (high engagement, marketplace trends, pricing outliers)
4. **Write** structured entries to LEARNING.md

## Dependencies

- Python 3.10+
- `openpyxl`
- `PyYAML`

Install:
```bash
python3 -m pip install openpyxl PyYAML
```

## Troubleshooting

- "No book data found" — Check KDP_DIR points to folder with Excel files
- "Workbook contains no default style" warning — Harmless, ignore it
- 0 KENP/unit — Book may be new or readers haven't finished reading yet

## See Also

- `~/books/factory/LEARNING.md` — Output file for insights
- `~/hermes-agent/AGENTS.md` — Development guide
