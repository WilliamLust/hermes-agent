# KDP Non-Fiction DOCX Generation: Comprehensive Formatting Specification

**Version:** 1.0  
**Date:** 2026-04-20  
**Purpose:** Canonical reference spec for a DOCX generation pipeline targeting Amazon KDP non-fiction ebooks and paperbacks.

---

## Table of Contents

1. [Amazon KDP Formatting Requirements](#1-amazon-kdp-formatting-requirements)
2. [Chicago Manual of Style — Front Matter Order](#2-chicago-manual-of-style--front-matter-order)
3. [Typography Standards (Bringhurst)](#3-typography-standards-bringhurst)
4. [TOC Best Practices](#4-toc-best-practices)
5. [Cover Page Embedding](#5-cover-page-embedding)
6. [Common DOCX Pitfalls on KDP](#6-common-docx-pitfalls-on-kdp)
7. [Page Structure for Non-Fiction](#7-page-structure-for-non-fiction)
8. [Font / Size / Spacing Defaults](#8-font--size--spacing-defaults)

---

## 1. Amazon KDP Formatting Requirements

### 1.1 General

KDP accepts DOCX files for ebook upload and PDF files for paperback upload. When a DOCX is uploaded for an ebook, KDP converts it to a reflowable Kindle format (KF8/AZW3). For paperbacks, the DOCX is converted to a print-ready format internally, but KDP strongly recommends authors submit PDFs for paperback to maintain precise control.

### 1.2 Margin Requirements (Paperback)

Margins vary by page count. KDP mandates **Mirror Margins** (inside/gutter + outside).

| Page Count | Inside (Gutter) | Outside (No Bleed) | Outside (With Bleed) |
|------------|-----------------|---------------------|----------------------|
| 24–150     | 0.375" (9.6mm)  | 0.25" (6.4mm)       | 0.375" (9.6mm)       |
| 151–300    | 0.500" (12.7mm) | 0.25" (6.4mm)       | 0.375" (9.6mm)       |
| 301–500    | 0.625" (15.9mm) | 0.25" (6.4mm)       | 0.375" (9.6mm)       |
| 501–700    | 0.750" (19.1mm) | 0.25" (6.4mm)       | 0.375" (9.6mm)       |
| 701–828    | 0.875" (22.3mm) | 0.25" (6.4mm)       | 0.375" (9.6mm)       |

**Professional recommendation (exceeds KDP minimums):**
- Inside margin: 0.75"–1.0" for books under 150 pages; 1.0" for 150–400 pages; 1.25" for 400+ pages
- Outside margins: 0.625"–0.75" minimum for comfortable reading
- Top margin: 0.75"–1.0"
- Bottom margin: 0.75"–1.0" (slightly larger than top for visual balance)

### 1.3 Trim Size

- Standard US non-fiction: **6" x 9"** (152.4 x 228.6mm)
- Alternative non-fiction sizes: 5.5" x 8.5", 5.25" x 8"
- Workbooks/technical: 8.5" x 11"
- Minimum page count: 24 pages (paperback)

### 1.4 Bleed

- Bleed adds **0.125"** (3.2mm) to the top, bottom, and outside edges
- A 6"x9" book with bleed becomes **6.125" x 9.25"**
- Bleed is **mandatory for covers** but optional for interiors
- Interior bleed only supported for PDF submissions, not DOCX
- Any image or background reaching the page edge requires bleed

### 1.5 Font Requirements

- **Minimum font size:** 7pt (KDP requirement); professional minimum is 10pt
- **All fonts must be embedded** in the final file (critical for PDF)
- Use fonts licensed for commercial publishing and embedding
- KDP recommends: Garamond, Palatino Linotype, Centaur, Hightower Text
- KDP proprietary font: **Amazon Endure** (space-saving, reduces page count/cost)
- Avoid Type 1 (PostScript) fonts — no longer supported by Adobe
- Supported formats: OpenType (OTF), TrueType (TTF)
- 22% of indie submissions fail due to unlicensed fonts

### 1.6 What KDP Strips/Converts (Ebook)

When a DOCX is uploaded as an ebook, KDP's conversion process:

**Stripped/Removed:**
- Page numbers, headers, and footers
- Custom page dimensions/margins (reflowable)
- Forced font colors on body text (normalized)
- Background colors on body text
- Manual line breaks used for spacing
- Multiple consecutive paragraph returns
- Tab-key indents

**Preserved/Converted:**
- Word Heading styles (Heading 1, Heading 2, etc.) → Kindle navigation
- Bold, italic, underline formatting
- Hyperlinks (become clickable)
- Images (must be inserted via Insert > Image, not copy-pasted)
- Footnotes (converted to clickable endnotes)
- Page breaks (converted to Kindle page breaks)
- The "toc" bookmark (enables HTML TOC detection)

**Normalized:**
- Body text font size → normalized to 1em
- Primary font-family → moved to root tag
- Forced colors on body text → removed
- Font sizes specified in absolute units → converted to relative

### 1.7 File Format

- Ebook: Upload as .docx (KDP converts internally)
- Paperback: Submit as **print-ready PDF** with embedded fonts (PDF/A preferred)
- Cover image: Uploaded **separately** — never embedded inside the manuscript DOCX
- Cover format: JPEG, minimum 1000px on longest side, 625px minimum; recommended 2500px+ for quality

### 1.8 Page Breaks

- Use `Insert > Page Break` — NEVER use multiple Enter/Return keys
- Hard returns at end of every line cause reflow errors
- Must use page break at the end of every chapter

---

## 2. Chicago Manual of Style — Front Matter Order

The Chicago Manual of Style (17th ed., Chapter 1) defines the canonical order of front matter for non-fiction books. Each numbered item typically gets its own page (recto/odd-numbered page when appropriate).

### 2.1 Standard Front Matter Order

| Order | Element | Page | Content | Alignment |
|-------|---------|------|---------|-----------|
| 1 | **Half-title page** | Recto (right/odd) | Book title only (no author, no subtitle, no publisher) | Centered |
| 2 | **Series title / Also by / Frontispiece / Blank** | Verso (left/even) | List of other books by author, OR series title, OR frontispiece illustration, OR blank | Centered or blank |
| 3 | **Full title page** | Recto (right/odd) | Title, subtitle, author name, publisher name/imprint | Centered |
| 4 | **Copyright page** | Verso (left/even) — back of title page | Copyright notice, edition, ISBN, legal disclaimers, credits, permissions | Left-aligned or centered |
| 5 | **Dedication** | Recto (right/odd) | Brief dedication text (1–3 lines) | Centered, lower third of page |
| 6 | **Epigraph** | Recto or Verso | Quotation relevant to the work | Centered, often italic |
| 7 | **Table of Contents** | Recto (right/odd) | Chapter titles with page numbers / links | Left-aligned with dot leaders |
| 8 | **List of Illustrations** | Recto or Verso | Optional, for image-heavy books | Left-aligned |
| 9 | **List of Tables** | Recto or Verso | Optional, for data-heavy books | Left-aligned |
| 10 | **Foreword** | Recto (right/odd) | Written by someone OTHER than the author | Left-aligned body, centered title |
| 11 | **Preface** | Recto (right/odd) | Written BY the author, explains why/how the book was written | Left-aligned body, centered title |
| 12 | **Acknowledgments** | Recto or Verso | Can be part of preface or separate | Left-aligned body, centered title |
| 13 | **Introduction** | Recto (right/odd) | Written by author; introduces the subject matter (part of the text, not front matter if numbered in Arabic) | Left-aligned body, centered title |
| 14 | **List of Abbreviations / Chronology** | Verso or Recto | Optional reference aids | Left-aligned |

### 2.2 Key Rules

- **Half-title page:** Title only. No author, no subtitle, no publisher, no date. Often in a smaller or lighter font than the full title page.
- **Title page:** Title (large), subtitle (smaller), author (medium), publisher (small, bottom). All centered vertically and horizontally.
- **Copyright page:** Always on the **verso** (left/even page) opposite the title page. Contains: copyright notice, edition info, ISBN, legal disclaimers, credits. 8–10pt font.
- **Dedication:** Very brief. Usually 1–3 lines centered on a recto page. White space above.
- **Epigraph:** A quote. Usually italicized. Attribution on next line (usually em-dash + author name). Often placed on its own page.
- **Foreword vs. Preface:** Foreword is by someone else (always name the writer). Preface is by the author. Both get their own recto page.
- **Introduction:** If part of the body text, starts Arabic numbering. If front matter, uses Roman numerals.
- **Front matter page numbering:** Uses lowercase Roman numerals (i, ii, iii...) starting with the title page. The half-title and its verso are traditionally not numbered but count.

### 2.3 Simplified Order for KDP Self-Published Non-Fiction

For self-published KDP non-fiction, the front matter is typically simplified:

1. **Title page** (recto) — title, subtitle, author
2. **Copyright page** (verso) — copyright notice, ISBN, disclaimers
3. **Dedication** (recto) — optional
4. **Table of Contents** (recto)
5. **Preface / Foreword** (recto) — optional
6. **Introduction** (recto)
7. **Chapter 1** (recto)

The half-title page is often omitted in self-published books to save pages and reduce cost.

---

## 3. Typography Standards (Bringhurst)

Robert Bringhurst's *The Elements of Typographic Style* is the definitive reference for book typography. Below are the principles most relevant to DOCX generation for KDP non-fiction.

### 3.1 Font Selection

**Body Text (Bringhurst Principles):**
- Use **serif** faces for extended reading — they guide the eye along the line
- Bringhurst favors humanist and old-style faces: **Garamond**, **Caslon**, **Jenson/Centaur**, **Bembo**
- For non-fiction specifically: **Caslon** (carries "bookish authority"), **Garamond** (classic, efficient), **Minion Pro** (modern, clean)
- Avoid Times New Roman for final books — it reads as an office document, not a book
- Avoid sans-serif for body text (15–20% less legible in extended reading)

**Headings:**
- Can use sans-serif for contrast: **Franklin Gothic**, **Futura**, **Montserrat**
- Or stay within the serif family at larger sizes/bolder weights
- Limit to **2–3 fonts total** per book (body, heading, optional accent)

### 3.2 Type Size and Leading

**Bringhurst's Leading Rule:**
- Leading should be **120–145% of the type size**
- Example: 11pt type → leading of 13.2pt to 16pt (14pt is common)
- Serif faces need less leading than sans-serif
- Faces with small x-height need more leading

**Specific Recommendations for 6"×9" Non-Fiction:**
- Body text: 10.5–11pt with 13–14pt leading
- Chapter titles: 16–20pt with 18–24pt leading
- Subheadings (H2): 13–14pt with 16–17pt leading
- Subheadings (H3): 12pt with 14–15pt leading
- Copyright page: 8–9pt with 10–11pt leading

### 3.3 Line Length (Characters per Line)

**Bringhurst's Ideal:**
- Optimal: **66 characters per line**
- Acceptable range: 45–75 characters per line
- For 6"×9" with 0.75" margins, text block width ≈ 4.5"
- 11pt Garamond typically yields 65–75 characters per line at this width

### 3.4 Margin Ratios

**Bringhurst's Classical Proportions (for printed books):**
- The text block should be positioned with larger inner (gutter) margin and larger bottom margin
- Traditional ratio: **Inside : Outside : Top : Bottom ≈ 2 : 1 : 1 : 2** (Van de Graaf canon)
- Another classical ratio: **1 : 1.5 : 2 : 3** (inside : outside : top : bottom)
- The gutter must accommodate the binding — typically 0.75"–1.0" for a standard non-fiction paperback
- Bottom margin should be largest to balance the visual weight of the page
- **Page proportions:** The 2:3 ratio (e.g., 6"×9") is considered one of the most harmonious

**Practical margins for 6"×9" non-fiction paperback:**
- Inside (gutter): 0.75" (short books) to 1.0" (300+ pages)
- Outside: 0.625"
- Top: 0.75"
- Bottom: 1.0"

### 3.5 Paragraph Treatment

- **First-line indent:** Traditional for prose; 0.2"–0.3" (one em to half an em)
- **Block style** (no indent, space between paragraphs): Preferred for technical/non-fiction reference works
- **First paragraph of a chapter:** No indent (flush left) — a typographic convention
- **Widows and orphans:** Never allow a single line at the top or bottom of a page

### 3.6 Justification

- **Print:** Full justification (flush left and right) with proper hyphenation
- **Ebook:** Flush left (ragged right) is safer to avoid rivers of white space, though justified is acceptable with good hyphenation
- Bringhurst: "Word spacing should be neither so wide that the fabric of the text is torn apart, nor so tight that the words are forced into a solid bar."

---

## 4. TOC Best Practices

### 4.1 Two TOC Types Required for KDP Ebooks

KDP recognizes two distinct types of TOC, both of which should be present:

1. **HTML TOC (TOC Page):** A physical page in the book with clickable links to chapters
2. **Kindle Interactive TOC (NCX):** The digital menu accessible from the Kindle interface

### 4.2 Word Styles for TOC Generation

**Mandatory:** Use Word's built-in heading styles for KDP to detect chapter structure.

| Style | Use For | Level |
|-------|---------|-------|
| Heading 1 | Chapter titles | TOC Level 1 |
| Heading 2 | Major sections within chapters | TOC Level 2 |
| Heading 3 | Subsections | TOC Level 3 |

**Requirements:**
- Every chapter title MUST be styled as **Heading 1**
- For non-fiction, Heading 2 and Heading 3 create a multi-level TOC
- Do NOT use manually formatted text (bold, large font) in place of heading styles
- Custom styles will NOT generate a Kindle Interactive TOC

### 4.3 Creating the TOC Page in Word (for Ebook)

**Step-by-step:**
1. Place cursor where the TOC should appear (after copyright/dedication, before Chapter 1)
2. Go to **References > Table of Contents > Custom Table of Contents**
3. **Uncheck "Show page numbers"** (ebooks don't have fixed pages)
4. Set **Show levels** to 2 or 3 (depending on heading depth)
5. Click OK to insert

### 4.4 The "toc" Bookmark (Critical for Kindle)

KDP requires a bookmark named exactly `toc` to identify the HTML TOC location:

1. Highlight the TOC title text (e.g., "Table of Contents" or "Contents")
2. Go to **Insert > Links > Bookmark**
3. Enter `toc` (lowercase, no quotes) as the bookmark name
4. Click **Add**
5. Insert a **Page Break** immediately after the TOC

**Without this bookmark, KDP cannot detect the HTML TOC**, and readers won't be able to navigate from the Kindle menu.

### 4.5 TOC Page Design (Paperback)

**For print, the TOC should include:**
- Title: "Contents" or "Table of Contents" (centered, Heading 1 style)
- Chapter titles with page numbers
- **Dot leaders** connecting title to page number
- Left-aligned entries, right-aligned page numbers
- Consistent indentation for sub-levels
- Font: same as body text or one size smaller

**Word settings for dot-leader TOC:**
- In Custom Table of Contents dialog, check **"Show page numbers"** and **"Right align page numbers"**
- Tab leader: select the dot leader option (......)
- For non-fiction with sub-sections: Show levels = 2 or 3

### 4.6 TOC Alignment

- **Ebook TOC:** Simple list of chapter titles as hyperlinks, left-aligned, no page numbers
- **Print TOC:** Chapter titles left-aligned, page numbers right-aligned, dot leaders between
- **Sub-levels:** Indented 0.3"–0.5" from the left margin per level

---

## 5. Cover Page Embedding

### 5.1 Critical KDP Rule

**For ebooks:** The cover image is uploaded SEPARATELY during KDP title setup. It must NOT be included inside the manuscript DOCX file.

**For paperbacks:** The cover is also uploaded separately. However, for interior design purposes, some authors embed a cover-style image as the first interior page.

### 5.2 Embedding Cover as First Interior Page (Paperback Only)

If you want a cover image as the first page of the interior DOCX:

1. **First page of document:** Insert image at full page width
2. **Image sizing:**
   - Without bleed: Image width = Trim Width − Inside Margin − Outside Margin
     - Example: 6" − 0.75" − 0.625" = 4.625"
   - With bleed: Image width = Trim Width + 0.125"
     - Example: 6" + 0.125" = 6.125" (and extend 0.125" beyond top and bottom)
3. **Resolution:** Minimum 300 DPI at print size
4. **Format:** JPEG, RGB color space (converted to CMYK at press)
5. **Placement:** Use **Insert > Pictures** (never copy-paste). Set text wrapping to **"In Line with Text"** for ebooks, or **"In Front of Text"** with manual positioning for print.
6. **Follow with a page break** to start the title page on the next page

### 5.3 Full-Page Bleed Image

For images that must extend to the page edge:
- Page size must include bleed (6.125" × 9.25" for a 6"×9" book)
- Image must extend 0.125" beyond the trim line on top, bottom, and outside edge
- In Word: Position image at 0,0 with size = page size with bleed
- Critical: KDP only supports interior bleed in **PDF submissions**, not DOCX
- For DOCX: Keep images within margins (no true bleed possible)

### 5.4 Image Technical Requirements

| Parameter | Requirement |
|-----------|-------------|
| Resolution | 300 DPI minimum at print size |
| Format | JPEG (preferred) or PNG |
| Color space | RGB for ebook; CMYK for print PDF |
| Max file size | 5MB per image (KDP recommendation) |
| Text wrapping | "In Line with Text" for ebook compatibility |
| Insertion method | Always Insert > Pictures, never copy-paste |

---

## 6. Common DOCX Pitfalls on KDP

### 6.1 Causes of Manuscript Rejection

| Issue | Description | Fix |
|-------|-------------|-----|
| **Broken/non-functional TOC** | Headings not using Word styles; missing "toc" bookmark | Use Heading 1/2/3 styles; add `toc` bookmark |
| **Narrow margins/gutter** | Inside margin too small for page count | Follow KDP margin table; increase gutter for thicker books |
| **Missing bleed on edge images** | Images extend past trim without bleed settings | Enable bleed or keep images within margins |
| **Unembedded fonts** | Fonts not embedded in PDF | Enable "Embed fonts in file" in Word Options |
| **Unlicensed fonts** | Commercial fonts without embedding rights | Use freely embeddable fonts (Google Fonts, Adobe Fonts) |
| **Corrupt data** | Corrupt images, strange characters, or malformed XML | Use Insert > Pictures; avoid unusual Unicode; save as DOCX (not DOC) |
| **File too large** | Uncompressed images | Compress to 300 DPI; use JPEG not PNG |
| **Wrong file format** | Uploaded .doc instead of .docx | Always save as .docx for ebook; PDF for paperback |
| **Page count too low** | Under 24 pages | Add front/back matter or adjust formatting |
| **Track Changes left ON** | KDP sees tracked changes as errors | Accept all changes and turn off Track Changes |

### 6.2 Causes of Formatting Corruption During Conversion

| Issue | What Happens | Prevention |
|-------|-------------|------------|
| **Tab-key indents** | Converted to inconsistent spacing | Use paragraph style first-line indent (0.2"–0.3") |
| **Multiple Enter/Return for spacing** | Creates blank pages, wrong reflow | Use Page Breaks; set spacing via paragraph settings |
| **Manual line breaks (Shift+Enter)** | Break mid-sentence across devices | Let text flow naturally; only use for intentional breaks |
| **Text boxes/shapes** | Stripped or rendered as images | Convert to images before inserting; avoid text boxes |
| **Copy-pasted images** | Corrupt low-res images | Always Insert > Pictures |
| **Drop caps in Word** | Often break in conversion | Use Kindle Create for drop caps, or skip them |
| **Custom or manually-formatted headings** | No TOC navigation generated | Always use Word Heading styles |
| **Headers/footers in ebook** | Stripped entirely | Remove for ebook; keep for print PDF only |
| **Page numbers in ebook** | Stripped (reflowable format) | Remove; KDP auto-handles page numbers |
| **Non-breaking spaces** | Can cause reflow issues in paragraphs | Use sparingly; never between all words |
| **Forced font colors** | Normalized/removed by KDP | Use default colors; gray only in #666–#999 range |
| **Absolute font sizes in CSS** | Overridden by device defaults | Use relative units (em, %) in any custom CSS |

### 6.3 Common Quality Issues (Not Rejection, But Bad Experience)

- **Widows and orphans:** Single lines isolated at page tops/bottoms
- **Rivers of white space:** From poor justification without hyphenation
- **Inconsistent spacing:** Mixed spacing between paragraphs
- **Missing chapter breaks:** Chapters running together without visual separation
- **Broken hyperlinks:** Links that don't work on Kindle devices
- **Blurry images:** Below 300 DPI
- **Wrong trim size:** A4/Letter instead of 6"×9"

---

## 7. Page Structure for Non-Fiction

### 7.1 Complete Book Order

Below is the recommended page structure for a KDP non-fiction book, indicating what gets its own page, what type of break to use, and alignment:

| # | Page | Break Before | Own Page? | Alignment | Notes |
|---|------|-------------|-----------|-----------|-------|
| 1 | **Cover image** (optional, paperback interior) | — | Yes | Full-page image | Omit for ebook; upload separately |
| 2 | **Half-title page** | Page break | Yes | Centered | Title only; often omitted for KDP |
| 3 | **Also by / Series / Blank** | Page break | Yes | Centered or blank | Verso of half-title |
| 4 | **Full title page** | Page break | Yes | Centered | Title, subtitle, author, publisher |
| 5 | **Copyright page** | Page break | Yes | Left-aligned or centered | Verso of title page |
| 6 | **Dedication** | Page break | Yes | Centered, lower third | 1–3 lines |
| 7 | **Epigraph** (optional) | Page break | Yes | Centered, italic | With attribution |
| 8 | **Table of Contents** | Page break | Yes | Left-aligned entries, centered title | Include `toc` bookmark for ebook |
| 9 | **Foreword** | Section break (Next Page) | Yes | Body left-aligned, title centered | By someone else |
| 10 | **Preface** | Section break (Next Page) | Yes | Body left-aligned, title centered | By the author |
| 11 | **Acknowledgments** | Page break | Yes | Body left-aligned, title centered | Can follow preface |
| 12 | **Introduction** | Section break (Next Page) | Yes | Body left-aligned, title centered | Starts Arabic numbering |
| 13 | **Chapters 1–N** | Section break (Next Page, Odd Page) | Yes | Title centered; body left-aligned | Each chapter on a recto page |
| 14 | **Conclusion / Afterword** | Section break (Next Page) | Yes | Title centered; body left-aligned | |
| 15 | **Appendices** | Section break (Next Page) | Yes | Title centered; body left-aligned | Optional |
| 16 | **Bibliography / References** | Section break (Next Page) | Yes | Title centered; entries left-aligned | Optional |
| 17 | **About the Author** | Page break | Yes | Body left-aligned, title centered | Include photo, bio, CTA |
| 18 | **CTA / Newsletter Signup** | Page break | Yes | Centered | URL + invitation text |
| 19 | **Other Books / Back Ad** | Page break | Yes | Centered | Promote other works |

### 7.2 Page Break vs Section Break

**Page Break** (`Ctrl+Enter` / `Insert > Page Break`):
- Use for simple page transitions where no formatting changes between sections
- Appropriate for: dedication → epigraph → TOC → acknowledgments → about author → CTA

**Section Break — Next Page** (`Layout > Breaks > Next Page`):
- Use when formatting needs to change between sections (headers, footers, page numbering, margins)
- Appropriate for: end of front matter → Chapter 1, between chapters if headers change

**Section Break — Odd Page** (`Layout > Breaks > Odd Page`):
- Use when a section must start on a recto (right-hand/odd) page
- Appropriate for: chapter openings in professional non-fiction paperback
- This may insert a blank verso page automatically

**For KDP ebook:** Page breaks only. Section breaks are ignored/stripped during conversion. Use simple page breaks between all major sections.

**For KDP paperback:** Use section breaks (Next Page or Odd Page) between chapters and major sections. This enables:
- Independent headers/footers per section
- Roman numerals for front matter, Arabic for body
- "Different first page" for chapter opening pages (no header)
- Mirrored headers: Author name (even/verso), Chapter title (odd/recto)

### 7.3 Alignment Rules

| Element | Alignment | Rationale |
|--------|-----------|-----------|
| Chapter titles | **Centered** | Standard convention; Heading 1 style |
| Section headings (H2) | **Left-aligned** or centered | Left-aligned is more common for non-fiction |
| Sub-headings (H3) | **Left-aligned** | Consistent with body text flow |
| Body text | **Justified** (print) / **Left-aligned** (ebook) | Justified requires good hyphenation; ebook left-aligned safer |
| Block quotes | **Left-aligned** with left indent (0.5"–1.0") | Indented from body text margin |
| Copyright page text | **Left-aligned** or **centered** | Either is acceptable; left-aligned is more common |
| Dedication | **Centered** | Lower third of page |
| Epigraph | **Centered** or right-aligned | With attribution on next line |
| TOC title | **Centered** | Heading 1 style |
| TOC entries | **Left-aligned** with right-aligned page numbers | Dot leaders between |
| About the Author | Body **left-aligned**, title **centered** | Standard body treatment |
| CTA / Newsletter | **Centered** | Promotional, stands out |
| Lists / bullet points | **Left-aligned** with hanging indent | Standard list formatting |

---

## 8. Font / Size / Spacing Defaults

### 8.1 Body Text

| Parameter | Ebook (DOCX Upload) | Paperback (PDF Export) |
|-----------|--------------------|-----------------------|
| **Font family** | Garamond, Bookerly, or Times New Roman | Garamond, Caslon, Minion Pro, or Palatino Linotype |
| **Font size** | 11pt (KDP normalizes to 1em) | 10.5–11pt |
| **Line spacing** | Single (1.0) | 1.15–1.3 (13–14pt leading for 11pt type) |
| **Paragraph spacing before** | 0pt | 0pt |
| **Paragraph spacing after** | 0pt | 0pt–6pt (for block-style non-fiction) |
| **First-line indent** | 0.2" (5mm) | 0.25"–0.3" (6–8mm) |
| **First paragraph of chapter** | Flush left (0 indent) | Flush left (0 indent) |
| **Alignment** | Left-aligned (ragged right safer) | Justified (with hyphenation enabled) |
| **Word style** | Normal (modified) | Normal (modified) |

**Indent vs Block Style for Non-Fiction:**
- **Traditional non-fiction (narrative):** First-line indent, no space between paragraphs
- **Technical/instructional non-fiction:** Block style (no indent, 6–12pt space after paragraphs)
- **Hybrid approach (recommended):** First-line indent with 0pt after spacing; first paragraph of each section flush left

### 8.2 Chapter Titles (Heading 1)

| Parameter | Ebook | Paperback |
|-----------|-------|-----------|
| **Font family** | Same as body (or sans-serif contrast) | Same as body or contrasting serif/sans-serif |
| **Font size** | 18–24pt | 16–20pt |
| **Font weight** | Bold | Bold |
| **Alignment** | Centered | Centered |
| **Spacing before** | 0pt (KDP pushes to new page via page break) | 60pt (pushes title ~1/3 down the page) |
| **Spacing after** | 24pt | 24–36pt |
| **All caps** | Optional | Optional (common for non-fiction) |
| **Page break before** | Yes | Yes (section break, odd page for print) |
| **First paragraph after** | Flush left, no indent | Flush left, no indent |
| **Headers/footers** | N/A (ebook) | None on chapter opening pages |

### 8.3 Subheadings — Heading 2

| Parameter | Ebook | Paperback |
|-----------|-------|-----------|
| **Font family** | Same as body | Same as body or slightly contrasting |
| **Font size** | 14–16pt | 13–14pt |
| **Font weight** | Bold | Bold |
| **Alignment** | Left-aligned | Left-aligned |
| **Spacing before** | 24pt | 18–24pt |
| **Spacing after** | 12pt | 12–18pt |
| **Style options** | Bold + italic optional | Bold; optional rule line below |

### 8.4 Subheadings — Heading 3

| Parameter | Ebook | Paperback |
|-----------|-------|-----------|
| **Font family** | Same as body | Same as body |
| **Font size** | 12–13pt | 12pt |
| **Font weight** | Bold italic or bold | Bold italic |
| **Alignment** | Left-aligned | Left-aligned |
| **Spacing before** | 18pt | 12–18pt |
| **Spacing after** | 6pt | 6–12pt |

### 8.5 Copyright Page

| Parameter | Specification |
|-----------|--------------|
| **Font family** | Same as body text |
| **Font size** | 8–9pt |
| **Line spacing** | Single (1.0) or 1.15 |
| **Alignment** | Left-aligned (most common) or centered |
| **Spacing before** | 0pt |
| **Spacing after** | 0pt |
| **Content order** | Copyright notice → Edition notice → Credits → ISBN → Legal disclaimers → Permissions |

**Copyright page template:**
```
Copyright © 2026 by Author Name
All rights reserved.

First Edition

ISBN-13: 978-X-XXXXXXX-X

Cover Design: Designer Name
Interior Layout: Designer Name
Editor: Editor Name

Printed in the United States of America

No part of this publication may be reproduced, distributed,
or transmitted in any form or by any means without the prior
written permission of the publisher.

For information about special discounts for bulk purchases,
please contact: email@example.com

The information in this book is provided for general
informational purposes only. The author and publisher make
no representations or warranties...
```

### 8.6 Dedication Page

| Parameter | Specification |
|-----------|--------------|
| **Font family** | Same as body or italic variant |
| **Font size** | Same as body (10.5–11pt) or slightly larger (12pt) |
| **Alignment** | Centered |
| **Vertical position** | Lower third of page (~60% from top) |
| **Spacing before** | 200–240pt (to push to lower third) |
| **Style** | Italic optional |

### 8.7 Block Quotes

| Parameter | Specification |
|-----------|--------------|
| **Font family** | Same as body, italic variant |
| **Font size** | Same as body or 0.5–1pt smaller |
| **Left indent** | 0.5"–1.0" from body text margin |
| **Right indent** | 0.5" (optional, for visual balance) |
| **Spacing before** | 12pt |
| **Spacing after** | 12pt |
| **Line spacing** | Same as body or slightly tighter |
| **Alignment** | Left-aligned (ragged right preferred for quotes) |

### 8.8 Running Headers/Footers (Paperback Only)

| Position | Content | Font | Size |
|----------|---------|------|------|
| Even (left/verso) header | Book title or Author name | Same as body, italic | 9–10pt |
| Odd (right/recto) header | Chapter title | Same as body, regular | 9–10pt |
| Chapter opening pages | No header | — | — |
| Footer | Page number | Same as body | 9–10pt |
| Front matter | Lowercase Roman numerals (i, ii, iii) | Same as body | 9–10pt |
| Body matter | Arabic numerals (1, 2, 3) | Same as body | 9–10pt |

---

## Appendix A: Word Style Configuration Summary

Below is the complete style configuration to be applied in the DOCX generation pipeline:

### Normal Style (Body Text)
```
Font:           Garamond (ebook: Bookerly/Garamond)
Size:           11pt
Color:          Automatic (Black)
Bold:           No
Italic:         No
Alignment:      Justified (paperback) / Left (ebook)
First line:     0.25" indent
Spacing Before: 0pt
Spacing After:  0pt
Line Spacing:   Single (ebook) / 1.15 (paperback) / Multiple 1.2 (paperback alternative)
Widows/Orphans: Control (enabled)
```

### Heading 1 Style (Chapter Titles)
```
Font:           Garamond Bold (or contrasting sans-serif)
Size:           18pt (ebook) / 16pt (paperback)
Color:          Automatic (Black)
Bold:           Yes
Italic:         No
Alignment:      Centered
First line:     0"
Spacing Before: 60pt (paperback) / 0pt (ebook, page break handles it)
Spacing After:  24pt
Line Spacing:   Single
Page Break Before: Yes
Outline Level:  Level 1
```

### Heading 2 Style (Section Headings)
```
Font:           Garamond Bold
Size:           14pt (ebook) / 13pt (paperback)
Color:          Automatic (Black)
Bold:           Yes
Italic:         No
Alignment:      Left
First line:     0"
Spacing Before: 24pt (ebook) / 18pt (paperback)
Spacing After:  12pt
Line Spacing:   Single
Keep with next: Yes
Outline Level:  Level 2
```

### Heading 3 Style (Subsection Headings)
```
Font:           Garamond Bold Italic
Size:           12pt
Color:          Automatic (Black)
Bold:           Yes
Italic:         Yes
Alignment:      Left
First line:     0"
Spacing Before: 18pt (ebook) / 12pt (paperback)
Spacing After:  6pt
Line Spacing:   Single
Keep with next: Yes
Outline Level:  Level 3
```

### Quote Style (Block Quotes)
```
Font:           Garamond Italic
Size:           10.5pt
Color:          Automatic (Black)
Bold:           No
Italic:         Yes
Alignment:      Left
Left indent:    0.5"
Right indent:   0.5"
Spacing Before: 12pt
Spacing After:  12pt
Line Spacing:   Single
```

### Copyright Style
```
Font:           Garamond
Size:           8pt
Color:          Automatic (Black)
Bold:           No
Italic:         No
Alignment:      Left
First line:     0"
Spacing Before: 0pt
Spacing After:  0pt
Line Spacing:   Single
```

---

## Appendix B: Ebook vs Paperback Configuration Matrix

| Parameter | Ebook (DOCX) | Paperback (PDF) |
|-----------|-------------|-----------------|
| File format | .docx | PDF (PDF/A preferred) |
| Trim size | N/A (reflowable) | 6" × 9" |
| Margins | N/A (reflowable) | Mirror: inside 0.75"–1.0", outside 0.625", top 0.75", bottom 1.0" |
| Body font | Garamond / Bookerly | Garamond / Caslon / Minion Pro |
| Body size | 11pt (normalized to 1em) | 10.5–11pt |
| Line spacing | Single | 1.15–1.3 |
| First-line indent | 0.2" | 0.25"–0.3" |
| Paragraph spacing | 0 before, 0 after | 0 before, 0–6pt after |
| Chapter title spacing before | 0pt (page break handles) | 60pt |
| Alignment | Left-aligned body | Justified body |
| TOC page numbers | No (uncheck Show page numbers) | Yes with dot leaders |
| Headers/footers | None | Author (even), chapter (odd), page# (footer) |
| Page breaks | Page break only | Section break (Next Page or Odd Page) |
| Cover image | Uploaded separately | Uploaded separately (optional interior first page) |
| Font embedding | Not required (reflowable) | Required (all fonts must be embedded) |
| Images | In Line with Text, JPEG, 300 DPI | In Line or In Front, JPEG/PNG, 300 DPI, CMYK |
| `toc` bookmark | Required | Not required (but doesn't hurt) |
| Bleed | Not supported in DOCX | Supported in PDF only |
| Page numbering | N/A | Roman (front matter), Arabic (body) |
| Drop caps | Avoid in Word (use Kindle Create) | Use Word's Insert > Drop Cap feature |

---

## Appendix C: Quick-Reference Checklist for DOCX Pipeline

### Before Generation
- [ ] Confirm trim size (6"×9" default for non-fiction)
- [ ] Set mirror margins per page count
- [ ] Select fonts: body (Garamond/Caslon), headings (same or contrasting)
- [ ] Verify font licensing for embedding

### During Generation
- [ ] Apply Heading 1 to all chapter titles (centered)
- [ ] Apply Heading 2 to section headings (left-aligned)
- [ ] Apply Heading 3 to subsection headings (left-aligned)
- [ ] Set Normal style: justified/left, 0.25" first-line indent, 0pt before/after
- [ ] First paragraph of each chapter: flush left (no indent)
- [ ] Insert page break at end of every chapter/section
- [ ] Insert TOC using Word's auto-TOC feature
- [ ] Add `toc` bookmark to TOC title
- [ ] Insert all images via Insert > Pictures (never copy-paste)
- [ ] Set images to "In Line with Text"
- [ ] Build copyright page at 8pt, left-aligned
- [ ] Build dedication page centered, lower third
- [ ] No headers/footers/page numbers for ebook version
- [ ] Add mirrored headers/footers for paperback version

### After Generation
- [ ] Embed all fonts (File > Options > Save > Embed fonts)
- [ ] Set image quality to 330 PPI (do not compress)
- [ ] Turn off Track Changes
- [ ] Check for tabs (Find ^t, replace with paragraph indent)
- [ ] Check for double spaces (Find "  ", replace with " ")
- [ ] Check for manual line breaks (Find ^l, fix)
- [ ] Check for multiple paragraph returns
- [ ] Save as .docx (ebook upload)
- [ ] Export as PDF/A (paperback upload)
- [ ] Test in Kindle Previewer (ebook)
- [ ] Order proof copy (paperback)

---

*End of specification. This document serves as the canonical reference for the DOCX generation pipeline.*
