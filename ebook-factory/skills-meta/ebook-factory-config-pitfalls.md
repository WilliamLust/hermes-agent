---
name: ebook-factory-config-pitfalls
category: ebook-factory
description: "Known pitfalls and fixes discovered during ebook factory pipeline build — Hermes config, agent parsing, EPUB generation, cleanup."
tags: [ebook, config, pitfalls, debugging, setup]
version: 1.0
---

# Ebook Factory — Config Pitfalls & Fixes

Lessons learned during the pipeline build. Check these before debugging.

## Chapter-Builder Word Count Calibration

**Symptom:** 35B-A3B-Q4_K_M consistently produces 2,400-2,600 words despite 2,800 target.

**Cause:** Qwen3 reasoning model burns context tokens on thinking during refinement calls, leaving fewer tokens for actual output. Refinement prompts that request "rewrite the whole chapter" trigger extended thinking chains.

**Fixes applied (all in chapter_builder.py):**
- `/no_think` prefix on refinement prompts suppresses reasoning mode
- Word-count-only refinements use targeted expansion (not full rewrite)
- `num_predict=8000` on refinement calls (vs 6000 for drafts)
- Graceful empty-response handling — keeps prior content if model returns nothing

**Recommended:** Set outline word count targets to 3000-3200 so final polished chapters reliably land in 2600-2900 range after refinement overhead.

---

## Hermes config.yaml Issues

### WeasyPrint PDF (confirmed working)
`pip install weasyprint` in the hermes-agent venv works without any apt dependencies — system libs (cairo, pango) already present on this machine. Version 68.1. Packager uses it automatically when available.

---

### Bug: `model.api_key: ollama`
Setting `api_key: ollama` in the model stanza causes provider confusion — Hermes tries to use "ollama" as an API key.
```yaml
# WRONG:
model:
  default: claude-sonnet-4-6
  provider: anthropic
  api_key: ollama   # ← DELETE THIS

# CORRECT:
model:
  default: claude-sonnet-4-6
  provider: anthropic
```

### Bug: `max_iterations: 20`
Default is 20 — far too low for pipeline work. Chapter generation alone can take 10+ turns.
```yaml
agent:
  max_iterations: 60   # Was 20, set to 60+ for factory work
```

### Missing toolsets
Factory work requires file, terminal, and web access. Default only had hermes-cli.
```yaml
toolsets:
- hermes-cli
- topic-research
- file
- terminal
- web
```

---

## Chapter-Builder Parsing Issues

### Outline keyword artifacts
The outliner wraps keywords in `**bold**` markdown. Raw parsing gives `['** introduction', 'overview']`.

Fix already in chapter_builder.py:
```python
raw = re.sub(r'\*+', '', raw)  # Strip markdown bold markers
keywords = [k.strip() for k in re.split(...) if k.strip() and len(k.strip()) > 1]
```
The `len > 1` filter also drops lone punctuation artifacts.

### Focus/objective artifacts
Same issue — focus text may start with `** ` from `**Objective:** text` format.
Fix: `focus = re.sub(r'\*+', '', focus).strip()` after extraction.

---

## Packager (EPUB) Issues

### ebooklib nav crash
ebooklib crashes with `lxml.etree.ParserError: Document is empty` when building the nav for any chapter whose HTML body is empty. Root cause: empty content field on `EpubHtml` before setting `.content` attribute.

Fix in packager.py:
1. Set `.content` as attribute after construction, not as constructor kwarg
2. Guard: `if not html_content.strip(): html_content = f"<p>{ch['title']}</p>"`
3. Wrap `epub.write_epub()` in try/except to fall back to Calibre

### EPUB fallback chain
ebooklib (best quality) → Calibre `ebook-convert` (reliable fallback) → skip with warning
Calibre is installed at `/usr/bin/ebook-convert` on this machine.

### PDF generation
WeasyPrint not installed. Calibre fallback works for PDF too.
To install WeasyPrint: `pip install weasyprint` (requires system cairo/pango libs).

---

## Phase 0 Path Alignment (Analyzer → LEARNING.md → Planner)

All three Phase 0 agents must point to the same canonical LEARNING.md. Default configs had them pointing to three different locations.

**Canonical path (single source of truth):**
```
~/books/factory/LEARNING.md
```

**analyzer/config.yaml** — already correct:
```yaml
learning_md_path: "/home/bookforge/books/factory/LEARNING.md"
```

**planner/config.yaml** — output path was wrong:
```yaml
# WRONG (was writing to books/factory/topic_plan.md):
output_path: /home/bookforge/books/factory/topic_plan.md

# CORRECT (outliner looks here):
output_path: /home/bookforge/.hermes/output/planner/topic_plan_latest.md
```

**analyzer/orchestrator.py `__main__`** — LEARNING_PATH defaulted to empty → wrote to `.` (cwd):
```python
# WRONG:
learning_path = Path(os.environ.get('LEARNING_PATH', ''))
if not learning_path or str(learning_path) == '':
    learning_path = None  # → used config, but config path was wrong

# CORRECT:
learning_path_env = os.environ.get('LEARNING_PATH', '')
learning_path = Path(learning_path_env) if learning_path_env else Path('/home/bookforge/books/factory/LEARNING.md')
```

**planner/orchestrator.py `__main__`** — resolved relative path broken:
```python
# WRONG (relative path broke at runtime):
learning_md_path = Path(config_path.parent / '../../../../books/factory/LEARNING.md')

# CORRECT (absolute, explicit):
learning_md_path = Path('/home/bookforge/books/factory/LEARNING.md')
output_path = Path('/home/bookforge/.hermes/output/planner/topic_plan_latest.md')
```

---

## KDP XLSX Parser — Prior Month File Structure

The `KDP_Prior_Month_Royalties-*.xlsx` file has a non-standard 2-row header structure that broke positional column indexing:

```
Row 0: ['Sales Period', 'March 2026', NaN, NaN, ...]   ← period header, NOT data
Row 1: ['Title', 'Author', 'ASIN', 'Marketplace', ...]  ← actual column names
Row 2+: real data rows
```

The old parser skipped row 0 and treated row 1 (the column headers) as data, then tried `int(row[7])` on a string like "Units Sold" → crash caught silently as `Error parsing prior month file: 0`.

**Fix — read with `header=None`, treat row 1 as headers, data from row 2:**
```python
raw = pd.read_excel(xl, sheet_name='eBook Royalty', header=None)
# Period info
period_val = raw.iloc[0, 1]  # 'March 2026'
# Actual headers at row 1
headers = [str(h) for h in raw.iloc[1]]
data = raw.iloc[2:].copy()
data.columns = headers
data = data.reset_index(drop=True)
# Now use named columns safely
for _, row in data.iterrows():
    units = int(float(row.get('Units Sold', 0) or 0))
```

**Dashboard file** (`KDP_Dashboard-*.xlsx`) does NOT have this issue — it uses a normal single header row. Only the prior month file uses the 2-row format.

**Also:** always cast through `float()` before `int()` — some numeric cells come in as floats (`1.0`) or pandas NA, so `int(float(val or 0))` is safer than `int(val)`.

---

## Planner Niche Scorer — Royalty Parsing Bugs

### Bug 1: Comma in dollar amounts breaks regex
LEARNING.md entries written with commas in royalty figures (`$2,760.00`) silently parsed as `$0` because the original regex `\$([\d]+\.?[\d]*)` doesn't match commas.

```python
# WRONG:
match = re.search(r'- \*\*Royalty:\*\*\s*\$(\d+\.?\d*)', body)

# CORRECT — handle commas and trailing (USD):
match = re.search(r'- \*\*Royalty:\*\*\s*\$([\d,]+\.?[\d]*)', body)
if match:
    metrics['royalty'] = float(match.group(1).replace(',', ''))
```

### Bug 2: Zero KENP treated as poor engagement
When KENP/unit = 0 it typically means no Kindle Unlimited readers yet — not that readers disengaged. The original scorer gave 0/10 engagement score, tanking all early-catalog niches below the viability threshold.

```python
# CORRECT — treat missing data as neutral, not zero:
if data.avg_kenp_per_unit > 0:
    engagement_score = min(data.avg_kenp_per_unit / 25 * 10, 10)
else:
    engagement_score = 5.0  # Neutral — no KU data yet
```

### Bug 3: Filter thresholds too high for early catalog
Default `min_kenp_per_unit: 20` and `min_market_size: 1000` filtered out ALL niches when catalog is small.

```yaml
# planner/config.yaml — realistic thresholds for early/growing catalog:
filters:
  min_roi_per_unit: 2.50
  min_kenp_per_unit: 5          # Was 20 — too aggressive for sparse data
  min_market_size: 100          # Was 1000 — bootstrapping threshold
```

---

## Fake Planner LEARNING.md

`~/.hermes/hermes_skills/planner/learning_data/LEARNING.md` contains synthetic data (ASINs like `2768467778`) generated by a previous local model session. It is NOT real sales data. Ignore it — the real file is `~/books/factory/LEARNING.md`.

If the planner reports "2 niches" or generic topic names, check which LEARNING.md it's actually reading.

---

## Directory Cleanup Notes

Abandoned directories found during build (can be deleted after archiving unique content):
```
~/hermes/              — empty "tools" dir
~/hermes-venv/         — old venv, superseded by ~/hermes-agent/venv/
~/bookforge-factory/   — old factory attempt (LEARNING.md archived)
~/ebook-project/       — old project structure (agents archived)
~/planner/             — one program.md (archived)
~/fast-drafter/        — CFS book chapters (already published as book #12)
~/deep-polisher/       — CFS book polished (same as above)
~/skills/              — single orchestration.md (archived)
~/bookforge/           — single content file (archived)
~/the-ai-revolution/   — empty config/status dirs (content lives in ~/books/the-ai-revolution/)
```

Archive command before deleting:
```bash
mkdir -p ~/books/factory/archive-cleanup-$(date +%Y%m%d)
# Copy anything unique, then:
rm -rf ~/hermes ~/hermes-venv ~/bookforge-factory ~/ebook-project ~/planner \
       ~/fast-drafter ~/deep-polisher ~/skills ~/bookforge ~/the-ai-revolution
```

## Amazon BSR Scraping via Firecrawl — Correct Approach

Firecrawl renders Amazon search pages with titles as **image alt-text links**, NOT H2 headings.
The parser went through 4 rewrites before landing on the correct pattern:

```python
# CORRECT — image alt-text (works across all Amazon page variants):
img_alt_pat = re.compile(
    r'\[!\[([^\]]{8,160})\]\(https://m\.media-amazon\.com[^\)]+\)\]'
    r'\(https://www\.amazon\.com[^\)]+\)'
)

# SUPPLEMENTAL — bold links (only some page variants):
bold_link_pat = re.compile(
    r'\[\*\*(.+?)\*\*\]\(https://www\.amazon\.com[^\)]+\)'
)
```

**Key pitfall:** `includeTags` in Firecrawl must include `li` and `ul` for product pages (BSR data is in a `<ul><li>` structure). Search pages use `div`/`a`. Use separate scraper configs:

```python
# For search result pages:
"includeTags": ["h1","h2","h3","span","div","a","p"]

# For product pages (BSR extraction):
"includeTags": ["h1","h2","h3","p","li","ul","span","div","a","table","td","th"]
```

**BSR location on product pages:** `Best Sellers Rank: #N in Kindle Store` appears at char ~82,000 in a 100K+ page. Some books only have subcategory ranks (no overall Kindle Store rank). Use best subcategory × 10 as proxy when overall rank is missing.

**Review counts format:** `[(147.6K)](https://amazon.com/...)` — the number is inside a markdown link. Pattern:
```python
reviews_pat = re.compile(r'\[\(?([0-9,]+(?:\.[0-9]+)?[Kk]?)\)?\]\(https?://')
```

**Amazon URL structure:** Force US store to avoid GBP prices:
```
https://www.amazon.com/s?k={q}+kindle+ebook&i=digital-text
&rh=n%3A133140011%2Cp_n_feature_nine_browse-bin%3A3291437011
&gl=us&language=en_US&page=1
```

**ASIN extraction from search results:** Use `sr_1_N` positional marker; prefer ASINs starting with `B` (Kindle) over 10-digit ISBNs (paperback):
```python
asin_pat = re.compile(r'https://www\.amazon\.com/[^/\s\)]+/dp/([A-Z0-9]{10})/ref=sr_1_(\d+)')
kindle_asins = [a for a, _ in matches if a.startswith("B")]
```

---

## Ideogram API — Correct Endpoint Usage for Book Covers

Discovered through trial and error. Working configuration:

**Generate (9x16 aspect ratio, DESIGN style):**
```python
resp = requests.post(
    "https://api.ideogram.ai/v1/ideogram-v3/generate",
    headers={"Api-Key": KEY},
    json={
        "prompt": "...",
        "rendering_speed": "TURBO",   # not "PORTRAIT" — that's wrong
        "aspect_ratio": "9x16",       # valid values: 9x16, 10x16, 2x3, etc.
        "style_type": "DESIGN",
        "num_images": 1,
        "magic_prompt": "OFF",
        "negative_prompt": "text, letters, words, watermark",
    },
    timeout=90,
)
# Returns 736x1312 at TURBO
```

**Upscale (multipart/form-data, NOT JSON body):**
```python
resp = requests.post(
    "https://api.ideogram.ai/upscale",   # NOT /v1/ideogram-v3/upscale
    headers={"Api-Key": KEY},
    data={"image_request": json.dumps({"resemblance": 80, "detail": 70})},
    files={"image_file": ("bg.png", img_bytes, "image/png")},
    timeout=120,
)
# Returns 1472x2624
```

**Critical pitfalls:**
- Upscale endpoint is `/upscale` not `/v1/ideogram-v3/upscale`
- Upscale requires `multipart/form-data`, NOT `application/json`
- `image_request` must be a JSON string in the form data field, not a nested dict
- `aspect_ratio` values are `"9x16"` format, not `"PORTRAIT"`
- `rendering_speed` options: `TURBO` ($0.03), `DEFAULT` ($0.06), `QUALITY` ($0.09)

**Architecture insight from vision analysis:** Do NOT put title text in the Ideogram prompt. Generate background art only, composite title/subtitle/author via Pillow. Reasons:
- No font control (Ideogram chooses style, not you)
- Can't update text without regenerating the expensive background
- Top KDP nonfiction covers use clean typography, not AI-rendered text
- Pillow gives exact pixel placement, consistent catalog branding

**KDP compliance:** Generate at 9x16 → upscale to 1472x2624 → Pillow pads/crops to exact 1600x2560. File size typically 200-600 KB (well under 5MB limit).

---

## Outliner Agent — Topic Plan Format Requirements

The outliner parses topic plans with a very specific format. Wrong format = "No valid topics found" error with no useful message.

**Required format:**
```markdown
### Top 3 Priorities

1. **Exact Book Title Here**
   - Niche: `niche-slug`
   - Expected ROI: $3.80/unit
   - Score: 8.20/10
```

**Critical requirements:**
- Section heading must be exactly `### Top 3 Priorities` (not "Top Priority", "Top Topics", etc.)
- Title must be `1. **Title**` — bold, numbered, on its own line
- Score line must match `Score: X.XX/10` — the outliner regex: `re.search(r'Score:\s*(\d+\.?\d*)/10', line)`
- Niche category in LEARNING.md entries gets `**` bold markers prepended — strip them with `re.sub(r'\*+', '', niche_str)` when parsing

**Also:** The outliner's LEARNING_FILE path points to a non-canonical location. Canonical LEARNING.md is at `~/books/factory/LEARNING.md`. If outliner says "LEARNING.md not found", the path in orchestrator.py needs updating.

---

## Two Venvs in hermes-agent
`~/hermes-agent/` has both `venv/` and `.venv/`. The active one is `venv/` — that's what `which hermes` points to.
Always use: `source ~/hermes-agent/venv/bin/activate`
