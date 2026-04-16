---
name: ebook-factory-config-pitfalls
category: ebook-factory
description: "Known pitfalls and fixes discovered during ebook factory pipeline build — Hermes config, agent parsing, EPUB generation, cleanup."
tags: [ebook, config, pitfalls, debugging, setup]
version: 1.0
---

# Ebook Factory — Config Pitfalls & Fixes

Lessons learned during the pipeline build. Check these before debugging.

## EPUB Validation — eBook-Standardization-Toolkit (REQUIRED)

Calibre's HTML→EPUB conversion creates invalid XHTML when it splits files mid-list.
`<p>` and `<h2>` appear directly inside `<ol>` tags without `<li>` wrappers.
KDP rejects these EPUBs with "couldn't convert your file" error.

**Fix: Always run eBook-Standardization-Toolkit after Packager.**

```bash
cd /home/bookforge/eBook-Standardization-Toolkit
source venv/bin/activate

INPUT=~/.hermes/ebook-factory/workbooks/book-SLUG/output/book-SLUG.epub
OUTPUT=~/.hermes/ebook-factory/workbooks/book-SLUG/output/book-SLUG-standardized.epub

python main.py "$INPUT" -o "$OUTPUT" --ai claude

# If residual <section> tag errors remain (EPUB2 doesn't support <section>):
# Replace <section> with <div> in the offending file using the zipfile approach

# Copy standardized epub over original when clean:
# epubcheck OUTPUT → 0 errors → cp OUTPUT INPUT
```

Tool location: `/home/bookforge/eBook-Standardization-Toolkit/`
Uses Anthropic API. Each run costs ~$0.10-0.30 in API calls (43 fixes × small prompts).

**Add to Packager pipeline:** After Calibre EPUB generation, before final output.

---

## Chapter-Builder Word Count Calibration

**Symptom:** `qwen3.5:35b-a3b-q4_k_m` consistently produces 2,400-2,600 words despite 2,800 target.

**Cause:** Qwen3 is a reasoning model. It burns context tokens on `<thinking>` chains before generating output. On refinement calls, this often exhausts `num_predict=6000` entirely on thinking, returning empty content.

**Fixes applied (all in `chapter_builder.py`):**

1. `/no_think` prefix on refinement prompts — suppresses extended reasoning:
```python
return f"""/no_think
The chapter below is {current_wc} words but needs {chapter['word_count']} words...
```

2. Separate `num_predict` for draft vs refinement:
```python
def call_ollama(prompt, model, system=SYSTEM_PROMPT, num_predict=6000):
# Draft calls: num_predict=6000
# Refinement calls: num_predict=8000  ← more headroom for thinking overhead
```

3. Graceful empty-response handling — keep prior content rather than crash:
```python
refined = call_ollama(refine_prompt, model, num_predict=8000)
if refined:
    content = refined
else:
    log("Refinement returned empty — keeping prior content")
```

4. Word-count-only refinements use targeted expansion, not full rewrite:
```python
# "Add 300 words by expanding examples" triggers less thinking than "rewrite chapter"
return f"""/no_think
The chapter below is {current_wc} words. Add approximately {needed} words by expanding
the concrete examples with more specific detail. Return the complete improved chapter."""
```

**Recommended:** Set outline word count targets to 3,000-3,200 so final polished
chapters reliably land in the 2,600-2,900 range after thinking overhead.

**When all 3 refinements fail** (model stuck in thinking loop): write the missing
section (summary/conclusion) directly in Python as editorial content rather than
burning more credits on generation. The chapter body is already good — just needs
the structural element to pass validation.

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

## Ideogram Cover Prompts — Specificity Is Everything

**Finding (2026-04-16):** Generic prompts produce generic covers. Specific visual metaphors produce 8.5/10 covers. The model isn't the bottleneck — the prompt is.

**Before (3/10 result):**
> "Deep warm orange gradient fading to near-black. Subtle geometric hexagon grid texture."

**After (8.5/10 result) for productivity/ADHD:**
> "Translucent human head shown front-facing, cool steel blue-gray tones. Brain visible inside skull split into two halves: left side chaotic tangled neural threads in dark muted colors, right side glowing organized orange geometric neural network with bright nodes. Orange energy sparks radiating outward. Deep black background. Cinematic lighting, photorealistic CGI render, dramatic contrast. No text."

**Rule:** The prompt must describe the visual metaphor specific to the book topic, not just a color palette. Think: what image would make a reader immediately understand what this book is about?

**Scoring reference from vision model:**
- Abstract gradient: 3/10
- Generic orange hexagon grid: 3/10
- Split brain chaos/order (ADHD book): 8.5/10
- Chaos vortex vs. geometric order (productivity): 8.5/10
- Beam of light through fog: 6/10 (too sci-fi, genre-ambiguous)

**Cover niche templates** are in `cover_generator.py` `NICHE_PALETTES` — updated with cinematic prompts for all 6 niches. Use `rendering_speed: "DEFAULT"` (not TURBO) when quality matters most ($0.06 vs $0.03).

---

## KDP Patching Existing Drafts — Use patch_kdp_book.py

When a KDP draft exists but is missing description/keywords/cover (e.g., after upload created the book but fields didn't fill), do NOT re-run `kdp_upload.py` (creates a duplicate draft). Use the patcher instead:

```bash
source ~/hermes-agent/venv/bin/activate
cd ~/.hermes/ebook-factory/skills/kdp-upload/
python3 patch_kdp_book.py --book-id BOOK_ID_FROM_KDP_URL
```

**Finding the book ID:** It's in the KDP URL when you click "Continue setup" on a draft — pattern `kdp.amazon.com/en_US/title-setup/kindle/A1CLFE136T01RN/details`

**What the patcher does:**
1. Loads the saved session (no re-login)
2. Navigates to the existing book's details page
3. Fills description via CKEditor API
4. Fills all 7 keywords
5. Navigates to content page and uploads cover
6. Saves as draft

**After patching**, always verify in browser — session may expire before the verify check runs. Trust the patcher log output (`✓ Keywords filled: 7/7`, `✓ Cover upload triggered`), then check the live KDP page.

---



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

---

## Model Benchmark: 27B-16k Beats 35B-A3B for Chapter Drafting

**Test (2026-04-16):** Both models given a 600-word chapter section prompt.

| Model | Words | Time | W/Min | Done |
|-------|-------|------|-------|------|
| qwen3.5:27b-16k | 595 | 64s | 557 | `stop` ✅ |
| qwen3.5:35b-a3b | 324 | 74s | 264 | `length` ❌ |

**Why 35B loses on drafting:** It's a reasoning model. The thinking phase consumes ~400-500 tokens before generating any output. With `num_predict=5000`, that leaves ~4500 for actual content. The 27B dense model has no thinking overhead and generates continuously.

**Rule:** Use 27B-16k for all chapter drafting. Use 35B-A3B for tasks where reasoning quality matters more than throughput (outlining, pattern analysis, structured planning).

**`chapter_builder.py` DEFAULT_MODEL = "qwen3.5:27b-16k"** — already updated.

Even with `/no_think` prefix, 35B still occasionally burns tokens on thinking. 27B-16k is the right tool for sustained writing.

---

## KDP Upload Automation — Real Form Selectors (2026-04-16)

Extensive trial and error revealed the actual KDP form structure. Old selectors (`#bookTitle`, `#authorFirstName` etc.) no longer exist. Real selectors:

```python
# Step 1: Book Details
"#data-title"                    # Book title
"#data-subtitle"                 # Subtitle
"#data-primary-author-first-name"  # Author first name
"#data-primary-author-last-name"   # Author last name
"#data-publisher-label"            # Publisher (NOTE: hidden field — skip gracefully)
"input[name='data[is_adult_content]-radio'][value='false']"  # Adult content = No
"#data-keywords-0" through "#data-keywords-6"  # Keywords

# Description: CKEditor rich text editor (NOT textarea, NOT Froala)
# iframe selector: "iframe[id^='cke_'], iframe.cke_wysiwyg_frame"
# Set via iframe frame.evaluate("document.body.innerHTML = ...")
# Fallback: JS on hidden input: "input[name='data[description]']"

# Save buttons (real KDP ids):
"#save-announce"                    # "Save as Draft"
"#save-and-continue-announce"       # "Save and Continue"

# Categories: React dropdown, name='react-aui-0' for main, name='react-aui-2' for sub
# BUT: subcategory options are sparse (Self-Help only has "Compulsive Behavior")
# SKIP categories automation — set manually in KDP dashboard after draft save
```

**Publisher field is hidden** (`class="lock-needs-hidden"`) — `wait_for_selector` times out. Use `safe_fill` which catches the timeout gracefully.

**Save and Continue sometimes blocked by modal overlay** — dismiss with JS before clicking:
```python
page.evaluate("document.querySelectorAll('.a-modal-scroller, [data-action=\"a-popover-floating-close\"]').forEach(el => el.style.display='none')")
```

**Categories validation blocks Step 2** unless adult content is set first. Order matters:
1. Set adult content radio = false
2. Click Save and Continue (categories left blank triggers error, but we skip for now)

The "Add a category" error from validation is acceptable — after saving, user sets categories manually in KDP dashboard. The draft saves successfully despite this error via the `#save-announce` button.

---

## KDP Session Setup — Required Before First Upload

Amazon blocks automated Chromium/Playwright login with verification challenges (URL pattern: `ap/signin/NNN-NNNNN-NNNNN`). **Camoufox (anti-detect Firefox) reduces but doesn't eliminate this.**

**Solution: one-time manual session save.**

```bash
source ~/hermes-agent/venv/bin/activate
cd ~/.hermes/ebook-factory/skills/kdp-upload/
python3 setup_kdp_session.py
# Firefox opens → log in manually → press Enter → cookies saved to ~/.kdp-session/
```

After this, `kdp_upload.py` restores the session and skips sign-in entirely:
```
[07:20:12] Restoring saved KDP session...
[07:20:17] Session restored — already signed in  ← cookies work
```

**Session lasts ~30 days.** After expiry, re-run `setup_kdp_session.py`.

**Password update:** If password changed since last session, update `.env`:
```bash
python3 -c "
path = '/home/bookforge/.hermes/.env'
lines = open(path).readlines()
new_lines = ['KDP_PASSWORD=NEWPASSWORD\n' if l.startswith('KDP_PASSWORD=') else l for l in lines]
open(path, 'w').writelines(new_lines)
print('Updated')
"
```
Do NOT use `sed` for this — if password contains special characters, sed interprets them.

**Telegram-based MFA pause:** If Amazon triggers verification mid-automation, the uploader sends a Telegram notification and polls for your "done" reply. Complete verification in the Firefox window, then reply "done" to @Hermes_Ebook_Factory_Bot.

**Session expires fast in practice** — despite cookies lasting ~30 days in theory, Camoufox sessions expire within minutes when switching between scripts. If you see `CKEDITOR is not defined` or a redirect to sign-in, re-run `setup_kdp_session.py`. Don't try to verify fields after upload — just go look at the live KDP page in your browser.

---

## KDP Description/Keywords — Hidden Input Won't Work

**Symptom:** Description and keywords appear empty in KDP after upload even though the script reported "Description set via JS" and "Keywords filled: 7/7".

**Root cause:** KDP's description uses CKEditor, which maintains its own internal state separate from the underlying hidden `input[name='data[description]']`. Setting the hidden input value via JavaScript doesn't update CKEditor's state, so KDP ignores it on save.

**Fix — use the CKEditor JavaScript API directly:**
```python
# CORRECT: use CKEditor's own API
result = page.evaluate("""
    (function() {
        for (var id in CKEDITOR.instances) {
            CKEDITOR.instances[id].setData(DESCRIPTION_TEXT_HERE);
            return 'set: ' + id;
        }
        return 'no instance';
    })()
""")

# OR: write to the iframe body directly
cke_iframe = page.query_selector("iframe.cke_wysiwyg_frame")
frame = cke_iframe.content_frame()
frame.evaluate(f"document.body.innerHTML = {repr(description[:3900])}")
```

**Keywords** fill correctly via `#data-keywords-0` through `#data-keywords-6` selectors — these work as normal inputs.

**patcher script** (`patch_kdp_book.py`) has the correct implementation for patching an existing draft without creating a new one.

---

## KDP Cover Upload — Content Page File Inputs

The content page (`/title-setup/kindle/BOOK_ID/content`) has **3 file inputs**:
1. Manuscript upload (EPUB)
2. Cover image upload  
3. A third input (unknown purpose — possibly audio/enhanced)

The `accept` attribute doesn't reliably distinguish them. When the uploader iterates file inputs and looks for `"image"` in the accept attribute, it may not find it. Fallback: use the second file input by position (index 1) for cover.

```python
file_inputs = page.query_selector_all("input[type='file']")
# Try by accept attr first
for fi in file_inputs:
    if "image" in (fi.get_attribute("accept") or ""):
        fi.set_input_files(str(cover_path))
        break
# If not found by accept, try index 1 (second input = cover)
elif len(file_inputs) > 1:
    file_inputs[1].set_input_files(str(cover_path))
```

If cover still shows "No Cover Uploaded" after upload: go to KDP dashboard Step 2 and upload manually — it's a one-click process.
