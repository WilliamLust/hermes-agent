#!/usr/bin/env python3
"""
Chapter-Builder Agent — Ebook Factory Phase 1
==============================================

Reads one chapter section from 01_outline.md, calls Ollama directly to draft
2500-3000 words of polished content, self-validates, self-refines (max 3 loops),
and writes the final chapter to w-drafts/chapter-XX.md.

Designed to run in parallel: 3-5 instances at once, each targeting a different chapter.

Usage:
    python3 chapter_builder.py --chapter 1
    python3 chapter_builder.py --chapter 1 --book-dir /path/to/workbook/
    python3 chapter_builder.py --chapter 1 --force           # Overwrite existing
    python3 chapter_builder.py --chapter 1 --model qwen3.5:27b-8k  # Override model

    # Parallel (run from shell):
    for ch in 1 2 3 4 5; do
        python3 chapter_builder.py --chapter $ch &
    done
    wait

Reference: ~/hermes-agent/AGENTS.md section 5
"""

import os
import sys
import re
import json
import shutil
import argparse
import requests
from pathlib import Path
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================

HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
WORKBOOKS_DIR = HERMES_HOME / "ebook-factory" / "workbooks"
LEARNING_FILE_PATHS = [
    HERMES_HOME / "ebook-factory" / "working" / "chapters" / "LEARNING.md",
    HERMES_HOME / "hermes_skills" / "planner" / "learning_data" / "LEARNING.md",
    Path.home() / "books" / "factory" / "LEARNING.md",
]

VOICE_ANCHOR_PATH = Path.home() / "books" / "factory" / "voice-anchor.md"

DEFAULT_MODEL = "qwen3.5:27b-16k"
OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
API_CHAT = f"{OLLAMA_BASE}/api/chat"

WORD_COUNT_TARGET_DEFAULT = 3200
WORD_COUNT_TOLERANCE = 0.10      # ±10%
MAX_REFINEMENT_ITERATIONS = 3
REQUEST_TIMEOUT = 1800           # 30 min max per API call


# ============================================================================
# LOGGING
# ============================================================================

def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def log_section(title: str) -> None:
    print(f"\n{'='*60}", flush=True)
    print(f"  {title}", flush=True)
    print(f"{'='*60}", flush=True)


def error_exit(msg: str) -> None:
    print(f"\nERROR: {msg}", file=sys.stderr, flush=True)
    sys.exit(1)


# ============================================================================
# FILE I/O
# ============================================================================

def read_file(path: Path) -> str:
    """Read file content, raise on failure."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")
    except Exception as e:
        error_exit(f"Cannot read {path}: {e}")


def write_file_atomic(path: Path, content: str) -> None:
    """Write content atomically via temp file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(content, encoding="utf-8")
    shutil.move(str(tmp), str(path))
    log(f"Written: {path}")


def find_latest_workbook() -> Path:
    """Find the most recently modified workbook directory."""
    if not WORKBOOKS_DIR.exists():
        error_exit(f"Workbooks directory not found: {WORKBOOKS_DIR}\nRun outliner first.")
    books = [d for d in WORKBOOKS_DIR.iterdir() if d.is_dir() and d.name.startswith("book-")]
    if not books:
        error_exit("No workbooks found. Run outliner first.")
    return sorted(books, key=lambda d: d.stat().st_mtime, reverse=True)[0]


def load_learning_data() -> str:
    """Load LEARNING.md content from known locations."""
    for path in LEARNING_FILE_PATHS:
        if path.exists():
            log(f"Loaded LEARNING.md from: {path}")
            return path.read_text(encoding="utf-8")[:3000]  # Cap at 3000 chars
    log("WARNING: No LEARNING.md found. Drafting without historical context.")
    return ""


def load_voice_reference(workbook_dir: Path) -> str:
    """
    Load voice reference for chapter drafting.

    Priority:
      1. ~/books/factory/voice-anchor.md  — house style, always available,
                                            consistent across every book
      2. workbook/w-polished/chapter-01.md — approved chapter from this book
                                             (used as supplementary context if
                                             voice-anchor exists, primary if not)

    The voice anchor is the authoritative source. It captures the catalog-wide
    voice distilled from all published books. Chapter-01 supplements it with
    book-specific tone once chapter 1 has been approved.
    """
    anchor = ""
    chapter1 = ""

    if VOICE_ANCHOR_PATH.exists():
        anchor = VOICE_ANCHOR_PATH.read_text(encoding="utf-8")
        log(f"Loaded voice anchor: {VOICE_ANCHOR_PATH}")
    else:
        log(f"WARNING: voice-anchor.md not found at {VOICE_ANCHOR_PATH}")

    ref = workbook_dir / "w-polished" / "chapter-01.md"
    if ref.exists():
        chapter1 = ref.read_text(encoding="utf-8")[:1500]
        log(f"Loaded chapter-01 voice supplement: {ref}")

    if anchor and chapter1:
        # Both available: anchor sets the style, chapter-01 shows book-specific tone
        return anchor + "\n\n## Book-Specific Voice Sample (Chapter 1 of this book):\n" + chapter1
    elif anchor:
        return anchor
    elif chapter1:
        return chapter1
    else:
        log("WARNING: No voice reference available — drafting without style anchor")
        return ""


# ============================================================================
# OUTLINE PARSING
# ============================================================================

def extract_chapter_from_outline(outline_path: Path, chapter_num: int) -> dict:
    """
    Extract a specific chapter section from 01_outline.md.

    Returns:
        {
            "number": int,
            "title": str,
            "word_count": int,
            "keywords": list[str],
            "focus": str,
            "raw_content": str,
        }
    """
    content = read_file(outline_path)

    # Match "## Chapter N: Title" through next chapter or end
    pattern = rf'(##\s+Chapter\s+{chapter_num}:[^\n]+(?:\n(?!##\s+Chapter\s+\d).*)*)'
    match = re.search(pattern, content, re.DOTALL)

    if not match:
        # Try alternate format: "## N. Title"
        pattern2 = rf'(##\s+{chapter_num}\.\s+[^\n]+(?:\n(?!##\s+\d\.).*)*)'
        match = re.search(pattern2, content, re.DOTALL)

    if not match:
        error_exit(
            f"Chapter {chapter_num} not found in {outline_path}\n"
            f"Make sure outline uses '## Chapter {chapter_num}: Title' format."
        )

    section = match.group(0).strip()

    # Extract title
    title_match = re.search(rf'##\s+(?:Chapter\s+)?{chapter_num}[.:]\s*(.+)', section)
    title = title_match.group(1).strip() if title_match else f"Chapter {chapter_num}"

    # Extract word count
    wc_match = re.search(r'[Ww]ord\s+[Cc]ount[^:]*:\s*(\d[\d,]*)', section)
    word_count = int(wc_match.group(1).replace(",", "")) if wc_match else WORD_COUNT_TARGET_DEFAULT

    # Extract keywords (various formats)
    keywords = []
    kw_match = re.search(r'[Kk]eywords?[^:]*:\s*(.+)', section)
    if kw_match:
        raw = kw_match.group(1).strip()
        # Handle "['a', 'b', 'c']" or "a, b, c" or "- a\n- b"
        raw = re.sub(r"[\[\]'\"]", "", raw)
        # Strip markdown bold/italic markers
        raw = re.sub(r'\*+', '', raw)
        keywords = [k.strip() for k in re.split(r'[,\n•\-]+', raw) if k.strip() and len(k.strip()) > 1][:5]

    # Extract focus/objective
    focus = ""
    focus_match = re.search(r'(?:[Ff]ocus|[Oo]bjective|[Pp]urpose)[^:]*:\s*(.+?)(?:\n\n|\Z)', section, re.DOTALL)
    if focus_match:
        focus = focus_match.group(1).strip()[:300]
        # Strip markdown artifacts
        focus = re.sub(r'\*+', '', focus).strip()

    return {
        "number": chapter_num,
        "title": title,
        "word_count": word_count,
        "keywords": keywords,
        "focus": focus,
        "raw_content": section,
    }


# ============================================================================
# PROMPT BUILDING
# ============================================================================

SYSTEM_PROMPT = """You are an expert non-fiction author writing chapters for a commercial self-published ebook (Amazon KDP).

Your writing standards:
- Professional publishing tone: authoritative, clear, accessible (not academic, not casual)
- Concrete examples with specific details: dates, numbers, names, real scenarios
- No AI-sounding filler phrases ("it's worth noting", "in today's world", "delve into")
- No placeholders, no "TBD", no generic advice without specifics
- Active voice (≥90%)
- Clear section structure using ## and ### headings
- Every section earns its place — no padding

Write the full chapter as requested. Do not add meta-commentary. Do not explain what you are about to do. Just write the chapter."""

# ── Self-improvement prompt overrides (auto-loaded) ───────────────────────────
def _load_prompt_overrides() -> str:
    """Load any prompt additions from the self-improvement agent."""
    override_file = Path(__file__).parent.parent / "self-improvement" / "prompt_overrides.json"
    if not override_file.exists():
        return ""
    try:
        data = json.loads(override_file.read_text())
        additions = data.get("chapter_builder_additions", [])
        rules = data.get("quality_rules", [])
        if not additions and not rules:
            return ""
        extra = "\n\nFACTORY LEARNING (apply these insights from published catalog):\n"
        for a in additions:
            extra += f"- {a}\n"
        if rules:
            extra += "\nQUALITY GATES (each chapter must pass):\n"
            for r in rules:
                extra += f"- {r}\n"
        return extra
    except Exception:
        return ""

SYSTEM_PROMPT = SYSTEM_PROMPT + _load_prompt_overrides()



def build_draft_prompt(chapter: dict, learning_data: str, voice_ref: str) -> str:
    """Build the full drafting prompt."""

    voice_section = ""
    if voice_ref:
        voice_section = f"""
VOICE & STYLE REQUIREMENTS (this is non-negotiable — match exactly):
---
{voice_ref}
---
"""

    learning_section = ""
    if learning_data:
        learning_section = f"""
HISTORICAL RESEARCH & PATTERNS (use relevant data where appropriate):
---
{learning_data}
---
"""

    return f"""Write Chapter {chapter['number']}: {chapter['title']}

TARGET WORD COUNT: {chapter['word_count']} words (acceptable range: {int(chapter['word_count'] * 0.9)}-{int(chapter['word_count'] * 1.1)} words)

CHAPTER FOCUS:
{chapter['focus'] or 'Cover the topic thoroughly with practical, actionable guidance.'}

KEYWORDS TO INCLUDE (weave naturally into content):
{', '.join(chapter['keywords']) if chapter['keywords'] else 'N/A'}

CHAPTER OUTLINE SECTION (use as structural guide):
{chapter['raw_content']}
{voice_section}{learning_section}
STRUCTURE REQUIREMENTS:
- Opening hook (1-2 paragraphs that grab attention with a concrete scenario or surprising fact)
- Clear section headers (## for main sections, ### for subsections)
- At least one concrete example per major section with specific details
- Actionable takeaways readers can apply immediately
- Closing summary (key points + what's next)

OUTPUT FORMAT:
- Write ONLY the chapter content in Markdown
- Do NOT include any meta-commentary
- Do NOT include "Chapter N:" in your first line (the system adds that)
- Start directly with your opening hook

Begin writing the chapter now. Write {chapter['word_count']} words."""


def build_refinement_prompt(original: str, issues: list[str], chapter: dict) -> str:
    """Build the refinement prompt when validation fails."""
    issues_text = "\n".join(f"  - {issue}" for issue in issues)

    # Word count specific fix: simpler targeted instruction
    word_count_issues = [i for i in issues if "Word count" in i or "word count" in i]
    structural_issues = [i for i in issues if "Word count" not in i and "word count" not in i]

    if word_count_issues and not structural_issues:
        # Word count only: expand specific sections rather than full rewrite
        current_wc = len(original.split())
        needed = chapter['word_count'] - current_wc
        return f"""The chapter below is {current_wc} words but needs {chapter['word_count']} words (±10%).
Add approximately {needed} words by expanding the concrete examples and case studies with more specific detail.
Do NOT rewrite the whole chapter. Return the complete improved chapter.

CURRENT CHAPTER:
---
{original}
---

Return the expanded chapter now. Write approximately {chapter['word_count']} words total."""

    # Structural issues: targeted rewrite
    return f"""Fix these specific issues in the chapter below:
{issues_text}

CHAPTER:
---
{original}
---

Rewrite the chapter addressing each issue. Target: {chapter['word_count']} words (±10%).
Write ONLY the improved chapter."""


# ============================================================================
# OLLAMA API (via shared ollama_client with retry + think:false)
# ============================================================================

# Import shared Ollama client
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ollama_client import ollama_call_with_retry

def call_ollama(prompt: str, model: str, system: str = SYSTEM_PROMPT,
                num_predict: int = 6000) -> str:
    """Call Ollama API with retry. Returns the response text (empty string on failure)."""
    log(f"Calling Ollama ({model})... (may take 5-15 min)")
    result = ollama_call_with_retry(
        prompt, system, model,
        max_retries=3,
        num_predict=num_predict,
        temperature=0.7,
        timeout=REQUEST_TIMEOUT,
    )
    if result is None:
        log("WARNING: Ollama call failed after all retries — returning empty string")
        return ""
    word_count = len(result.split())
    log(f"Received {word_count} words from Ollama")
    return result

# ============================================================================
# VALIDATION
# ============================================================================

def validate_chapter(content: str, chapter: dict) -> list[str]:
    """
    Validate chapter content. Returns list of issues (empty = pass).
    """
    issues = []
    words = len(content.split())
    target = chapter["word_count"]
    low = int(target * (1 - WORD_COUNT_TOLERANCE))
    high = int(target * (1 + WORD_COUNT_TOLERANCE))

    if words < low:
        issues.append(f"Word count too low: {words} words (need at least {low})")
    # Note: too long is never flagged — a longer chapter is never a problem for the reader

    # Check for placeholder text
    if re.search(r'\btbd\b|\bto be determined\b|\bplaceholder\b|\b\[insert\b', content, re.I):
        issues.append("Contains placeholder text (tbd / to be determined / [insert...])")

    # Check for keywords — normalize hyphens so "30-day plan" matches "30 day plan"
    def normalize(s):
        return re.sub(r'[-–—]', ' ', s).lower()

    content_normalized = normalize(content)
    for kw in chapter.get("keywords", []):
        if kw and normalize(kw) not in content_normalized:
            issues.append(f"Missing keyword: '{kw}'")

    # Check for conclusion / summary section
    if not re.search(r'##.*(summary|conclusion|takeaway|key point)', content, re.I):
        issues.append("Missing closing summary or conclusion section (## Summary / ## Conclusion / ## Key Takeaways)")

    # Check for section structure
    h2_count = len(re.findall(r'^##\s', content, re.M))
    if h2_count < 3:
        issues.append(f"Too few sections: {h2_count} (need at least 3 ## headers)")

    return issues


# ============================================================================
# CHAPTER ASSEMBLY
# ============================================================================

def build_output(chapter: dict, content: str, iterations: int, issues_remaining: list) -> str:
    """Wrap content with header, metadata, and validation report."""
    ts = datetime.now().isoformat(timespec="seconds")
    status = "PASS" if not issues_remaining else "WARN (manual review recommended)"
    word_count = len(content.split())
    target = chapter["word_count"]
    wc_status = "✓" if abs(word_count - target) <= target * WORD_COUNT_TOLERANCE else "✗"

    issues_section = ""
    if issues_remaining:
        issues_section = "\n".join(f"  - {i}" for i in issues_remaining)
        issues_section = f"\nRemaining issues:\n{issues_section}"

    validation_report = f"""
## Validation Report
<!-- AUTO-GENERATED: {ts} -->

- Word count: {word_count} words {wc_status} (target: {target}, tolerance: ±{int(WORD_COUNT_TOLERANCE*100)}%)
- Refinement iterations: {iterations}
- Keywords: {', '.join(chapter['keywords']) if chapter['keywords'] else 'N/A'}
- Status: {status}{issues_section}

---
*Generated by Chapter-Builder agent. Review before moving to w-polished/*
"""

    return f"""# Chapter {chapter['number']}: {chapter['title']}
<!-- AUTO-GENERATED: {ts} -->

{content.strip()}

{validation_report}"""


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def build_chapter(chapter_num: int, workbook_dir: Path, model: str, force: bool,
                   critique: str = "") -> int:
    """
    Full chapter-building pipeline for one chapter.
    Returns 0 on success, 1 on failure.

    critique: optional human feedback string. When provided, the chapter is
              regenerated with this critique prepended to the first refinement
              prompt, forcing the model to address specific issues.
    """
    log_section(f"Chapter-Builder: Chapter {chapter_num}"
                + (" [CRITIQUE MODE]" if critique else ""))

    # --- Find outline ---
    outline_path = workbook_dir / "01_outline.md"
    if not outline_path.exists():
        error_exit(f"Outline not found: {outline_path}\nRun outliner first.")

    # --- Check output ---
    drafts_dir = workbook_dir / "w-drafts"
    output_path = drafts_dir / f"chapter-{chapter_num:02d}.md"

    if output_path.exists() and not force:
        log(f"Chapter {chapter_num} already exists: {output_path}")
        log("Use --force to overwrite.")
        return 0

    # --- Load data ---
    log("Loading outline...")
    chapter = extract_chapter_from_outline(outline_path, chapter_num)
    log(f"Chapter: {chapter['title']}")
    log(f"Target: {chapter['word_count']} words | Keywords: {chapter['keywords']}")

    learning_data = load_learning_data()
    voice_ref = load_voice_reference(workbook_dir)

    # --- Draft ---
    log_section(f"Phase 1: Drafting Chapter {chapter_num}")
    prompt = build_draft_prompt(chapter, learning_data, voice_ref)
    content = call_ollama(prompt, model)

    # --- Critique injection: treat human critique as the first refinement issue ---
    if critique and content:
        log_section(f"Phase 1b: Applying human critique")
        log(f"Critique: {critique}")
        critique_prompt = build_refinement_prompt(content, [f"HUMAN CRITIQUE: {critique}"], chapter)
        refined = call_ollama(critique_prompt, model, num_predict=8000)
        if refined:
            content = refined
            log("Critique applied successfully")
        else:
            log("WARNING: Critique refinement returned empty — using original draft")

    # --- Validate + Refine Loop ---
    iteration = 0
    issues = validate_chapter(content, chapter)

    while issues and iteration < MAX_REFINEMENT_ITERATIONS:
        iteration += 1
        log_section(f"Phase 2: Refinement iteration {iteration}/{MAX_REFINEMENT_ITERATIONS}")
        log(f"Issues found ({len(issues)}):")
        for issue in issues:
            log(f"  - {issue}")

        refine_prompt = build_refinement_prompt(content, issues, chapter)
        refined = call_ollama(refine_prompt, model, num_predict=8000)
        if refined:  # only replace if refinement returned content
            content = refined
        else:
            log(f"Refinement {iteration} returned empty — keeping prior content")
        issues = validate_chapter(content, chapter)

        if not issues:
            log(f"All issues resolved after {iteration} refinement(s)")
            break
        else:
            log(f"Refinement {iteration} complete. Remaining issues: {len(issues)}")

    # --- Final validation status ---
    if issues:
        log(f"WARNING: {len(issues)} issue(s) remain after {iteration} refinement(s).")
        log("Chapter written with WARN status. Manual review recommended.")
    else:
        log(f"PASS: All validations passed (refinements: {iteration})")

    # --- Write output ---
    log_section(f"Writing Chapter {chapter_num}")
    final_content = build_output(chapter, content, iteration, issues)
    write_file_atomic(output_path, final_content)

    word_count = len(content.split())
    log(f"\nChapter {chapter_num} complete:")
    log(f"  Output: {output_path}")
    log(f"  Words:  {word_count}")
    log(f"  Status: {'PASS' if not issues else 'WARN'}")

    return 0 if not issues else 1


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Chapter-Builder Agent — Ebook Factory Phase 1",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 chapter_builder.py --chapter 1
  python3 chapter_builder.py --chapter 1 --force
  python3 chapter_builder.py --chapter 3 --book-dir ~/.hermes/ebook-factory/workbooks/book-my-topic/
  python3 chapter_builder.py --chapter 5 --model qwen3.5:27b-8k
  python3 chapter_builder.py --chapter 4 --force --critique "Too abstract. Add real numbers and named studies."

Parallel execution:
  for ch in 1 2 3; do python3 chapter_builder.py --chapter $ch & done; wait
        """
    )
    parser.add_argument("--chapter", type=int, required=True,
                        help="Chapter number to build (1-12)")
    parser.add_argument("--book-dir", type=str, default=None,
                        help="Path to workbook directory (auto-detects latest if not set)")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL,
                        help=f"Ollama model name (default: {DEFAULT_MODEL})")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing chapter file without confirmation")
    parser.add_argument("--critique", type=str, default="",
                        help="Your critique of the existing chapter. Forces a rewrite "
                             "with this feedback prepended to the refinement prompt. "
                             "Implies --force.")

    args = parser.parse_args()

    # --critique implies --force (we need to overwrite to apply the critique)
    if args.critique:
        args.force = True

    # Determine workbook directory
    if args.book_dir:
        workbook_dir = Path(args.book_dir)
        if not workbook_dir.exists():
            error_exit(f"Book directory not found: {workbook_dir}")
    else:
        workbook_dir = find_latest_workbook()
        log(f"Auto-detected workbook: {workbook_dir.name}")

    log(f"Working in: {workbook_dir}")
    if args.critique:
        log(f"Critique mode: '{args.critique[:80]}{'...' if len(args.critique) > 80 else ''}'")

    try:
        exit_code = build_chapter(args.chapter, workbook_dir, args.model, args.force,
                                   critique=args.critique)
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nInterrupted by user.", flush=True)
        sys.exit(130)


if __name__ == "__main__":
    main()
