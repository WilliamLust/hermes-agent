#!/usr/bin/env python3
"""
Outliner Agent — Ebook Factory Phase 0.5

Generates a production-quality book outline using Qwen 35B (Ollama).
The LLM writes real chapter titles, specific section names, focused
examples, and concrete per-section guidance — not templates.

Usage:
    python3 orchestrator.py --topic "Stress Management for Nurses" --chapters 10
    python3 orchestrator.py   # Auto-selects top topic from latest topic_plan
    python3 orchestrator.py --chapters 12
"""

import os
import sys
import json
import re
import argparse
import requests
from pathlib import Path
from datetime import datetime

# ======================================================================
# CONFIGURATION
# ======================================================================

HERMES_HOME    = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
WORKBOOKS_DIR  = HERMES_HOME / "ebook-factory" / "workbooks"
TOPIC_PLANS_DIR= HERMES_HOME / "output" / "planner"
LEARNING_FILE  = Path.home() / "books" / "factory" / "LEARNING.md"
STYLE_GUIDE    = Path.home() / "books" / "factory" / "style-guide.md"

OLLAMA_URL     = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434") + "/api/chat"
OUTLINE_MODEL  = "qwen3.5:27b-16k"        # Unified model — same as chapter builder
COVER_MODEL    = "qwen3.5:27b-16k"        # Same model — cover prompt
REQUEST_TIMEOUT= 600   # 10 min max — outlining is a long single call

# ======================================================================
# LOGGING
# ======================================================================

def log(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def log_section(title: str) -> None:
    print(f"\n{'='*60}", flush=True)
    print(f"  {title}", flush=True)
    print(f"{'='*60}", flush=True)

def warning(msg: str) -> None:
    print(f"\n[WARN] {msg}", flush=True)

def error_exit(msg: str) -> None:
    print(f"\n[ERROR] {msg}", file=sys.stderr, flush=True)
    sys.exit(1)

# ======================================================================
# FILE I/O
# ======================================================================

def read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        error_exit(f"Cannot read {path}: {e}")

def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    log(f"Written: {path}")

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text[:80]

# ======================================================================
# TOPIC PLAN LOADING
# ======================================================================

def find_topic_plans() -> list:
    if not TOPIC_PLANS_DIR.exists():
        return []
    plans = list(TOPIC_PLANS_DIR.glob("topic_plan_*.md"))
    return sorted(plans, key=lambda p: p.stat().st_mtime, reverse=True)

def load_topic_plan(plan_path: Path) -> dict:
    content = read_file(plan_path)
    topics = []
    lines = content.split("\n")
    in_priorities = False
    current_topic = None

    for line in lines:
        if "Top 3 Priorities" in line:
            in_priorities = True
            continue
        if in_priorities and line.startswith("###") and "Top 3 Priorities" not in line:
            in_priorities = False
            continue
        if in_priorities:
            match = re.match(r"^\d+\.\s+\*\*(.+?)\*\*$", line.strip())
            if match:
                if current_topic:
                    topics.append(current_topic)
                current_topic = {"title": match.group(1).strip(), "viability_score": None, "niche": ""}
            elif current_topic and "score:" in line.lower():
                m = re.search(r"Score:\s*(\d+\.?\d*)/10", line)
                if m:
                    current_topic["viability_score"] = float(m.group(1))
            elif current_topic and "niche:" in line.lower():
                m = re.search(r"Niche:\s*`?(\w[\w-]*)`?", line)
                if m:
                    current_topic["niche"] = m.group(1).strip()

    if current_topic:
        topics.append(current_topic)

    topics.sort(key=lambda t: t.get("viability_score") or 0, reverse=True)
    return {"topics": topics, "file": str(plan_path)}

# ======================================================================
# CONTEXT LOADING
# ======================================================================

def load_learning_summary() -> str:
    """Load LEARNING.md and extract key catalog patterns (capped for prompt budget)."""
    if not LEARNING_FILE.exists():
        return ""
    content = LEARNING_FILE.read_text(encoding="utf-8")
    # Grab the Key Patterns section — most actionable for the outliner
    match = re.search(r"### Key Patterns Across Catalog.+?(?=\n---|\Z)", content, re.DOTALL)
    patterns = match.group(0).strip() if match else ""
    # Also grab top performers summary table
    table_match = re.search(r"\| Title \| Niche .+?(?=\n\n|\Z)", content, re.DOTALL)
    table = table_match.group(0).strip() if table_match else ""
    combined = f"{table}\n\n{patterns}".strip()
    return combined[:3000]

def load_style_guide() -> str:
    if not STYLE_GUIDE.exists():
        return ""
    return STYLE_GUIDE.read_text(encoding="utf-8")[:2000]

# ======================================================================
# QUALITY EXAMPLE — Book 13 outline excerpt as the gold standard
# ======================================================================

QUALITY_EXAMPLE = """
## Chapter 3: Environment Design — Make the Right Thing the Easy Thing

**Objective:** Teach readers to design their physical and digital environment to reduce friction on important tasks
**Target Audience:** ADHD adults who rely on willpower (and keep running out of it)
**Word Count Target:** 2800 words

### Sections

1. **[Chapter Introduction]** (~300 words)
   - **Focus:** Why ADHD productivity depends on environment 10x more than neurotypical productivity
   - **Keywords:** environment design ADHD, friction reduction, visual cues, external scaffolding
   - **Example:** "Your environment is your external prefrontal cortex."

2. **[The Friction Audit]** (~600 words)
   - **Focus:** Identifying what's making important tasks harder than they need to be
   - **Keywords:** task friction, ADHD task initiation, environment audit
   - **Example:** Step-by-step: for every task you regularly avoid, write down the first physical step required. If there are more than 3 steps before you start the actual work, the friction is too high.

3. **[Visual Cues and External Memory]** (~600 words)
   - **Focus:** ADHD working memory workarounds — making tasks visible so they can't be forgotten
   - **Keywords:** visual task management, ADHD reminders, external memory systems, sticky notes
   - **Example:** The rule: if it's not visible, it doesn't exist. Walk through how to design a workspace where current priorities are literally in your field of vision at all times.

4. **[The "Ready to Start" Setup]** (~600 words)
   - **Focus:** How to prep your environment the night before so tomorrow-you can start in under 60 seconds
   - **Keywords:** task initiation ADHD, evening routine, friction reduction, implementation intentions
   - **Example:** Specific setup: laptop open to the right file, coffee maker set, phone in another room, first task written on paper on the keyboard. Morning-you just sits down and starts.

5. **[Digital Environment: Taming the Chaos]** (~400 words)
   - **Focus:** App notifications, browser tabs, digital friction — specific rules for ADHD brains
   - **Keywords:** digital distraction ADHD, notification management, focus apps, browser extensions
   - **Example:** The Tab Rule: maximum 5 open browser tabs. Every tab over 5 is a commitment you made to your brain that you haven't kept.

6. **[Chapter Summary]** (~300 words)
   - **Focus:** Your environment is a productivity system — audit and design it intentionally
   - **Keywords:** environment design, friction audit, visual cues
   - **Example:** 3-point action plan the reader can do today.
"""

# ======================================================================
# LLM CALL — OUTLINE GENERATION (via shared ollama_client)
# ======================================================================

# Import shared Ollama client with retry + think:false + fallback
# ollama_client.py lives at ~/.hermes/ebook-factory/skills/ — find it
_HERMES_HOME = Path.home() / ".hermes"
_ollama_client_dirs = [
    _HERMES_HOME / "ebook-factory" / "skills",     # primary location
    Path(__file__).resolve().parent.parent,          # relative to this script
    Path(__file__).resolve().parent.parent.parent,   # one more level up
]
for _d in _ollama_client_dirs:
    if (_d / "ollama_client.py").exists():
        sys.path.insert(0, str(_d))
        break
from ollama_client import ollama_call_with_retry, ollama_call_with_fallback

# Keep OLLAMA_URL for backwards compat but all calls go through ollama_client
# No fallback chain needed — single model (27B) used throughout
FALLBACK_CHAIN = []  # Empty: if 27B fails, retry (not fall back to a different model)


def ollama_call(prompt: str, system: str, model: str, num_predict: int = 6000,
                temperature: float = 0.7) -> str | None:
    """Ollama API call with retry and model fallback. Returns content string or None on failure."""
    # Use fallback chain for outline generation (critical path)
    if model == OUTLINE_MODEL:
        result = ollama_call_with_fallback(
            prompt, system,
            preferred_model=model,
            fallback_chain=FALLBACK_CHAIN,
            max_retries=3,
            num_predict=num_predict,
            temperature=temperature,
            num_ctx=16384,
            timeout=REQUEST_TIMEOUT,
        )
    else:
        # Cover prompt / vague fix — simpler retry, no fallback
        result = ollama_call_with_retry(
            prompt, system,
            model=model,
            max_retries=3,
            num_predict=num_predict,
            temperature=temperature,
            num_ctx=16384,
            timeout=REQUEST_TIMEOUT,
        )
    return result


def generate_outline_llm(topic: dict, num_chapters: int,
                          learning_summary: str, style_guide: str) -> str | None:
    """
    Ask Qwen 35B to write a complete, production-quality book outline.
    Returns the full outline markdown string, or None on failure.
    """
    title = topic.get("title", "Unknown")
    niche = topic.get("niche", "general")
    score = topic.get("viability_score", 0)

    system = """You are a senior nonfiction editor and book architect. You create detailed, production-quality outlines for self-published ebooks that sell on Amazon KDP.

Your outlines are SPECIFIC, not generic:
- Chapter titles are hooks and promises, not category labels ("The Friction Audit" not "Core Concept 2")
- Section titles are specific angles on the topic, not placeholders
- Each example is a concrete scenario, real technique, or named framework — never "Key example" or "Success story"
- Each keyword cluster is tailored to actual Amazon search terms for this specific book
- Word counts are calibrated to the content density required for that section

You do not produce filler. Every chapter must earn its place in the book's argument.
Output ONLY the outline in Markdown. No preamble, no explanation, no meta-commentary."""

    user = f"""Write a complete, detailed book outline for this nonfiction ebook:

TITLE: {title}
NICHE: {niche}
CHAPTERS: {num_chapters}

CATALOG CONTEXT (what's worked in this catalog before):
{learning_summary}

STYLE GUIDE:
{style_guide}

QUALITY STANDARD — Study this chapter example carefully. Your output must match this level of specificity:
{QUALITY_EXAMPLE}

FORMAT REQUIREMENTS (follow exactly):
- Header: # Book Outline: [Title]
- Then: **Voice Style:** [1 sentence describing the book's specific voice]
- Then: **Core Promise:** [1 sentence — what specific transformation does the reader get?]
- Then: **Target Reader:** [1 sentence — who exactly is this for, with a specific pain point]
- Blank line then ---
- Each chapter as: ## Chapter N: [Specific Hook Title]
- Under each chapter:
  - **Objective:** [specific learning outcome for this chapter]
  - **Target Audience:** [who specifically needs this chapter]
  - **Word Count Target:** 2800 words
  - ### Sections
  - Numbered sections with: **[Section Title]** (~NNN words)
    - **Focus:** [specific angle]
    - **Keywords:** [Amazon search terms, comma separated]
    - **Example:** [concrete, specific example or scenario]
  - End with ---

CRITICAL RULES:
- Chapter titles must be HOOKS not labels. "The Willpower Myth" beats "Understanding Motivation"
- Section names must be SPECIFIC to this book's topic. No generic names like "Core Concept 1"
- Examples must be CONCRETE: name the technique, give the numbers, describe the exact scenario
- Keywords must be ACTUAL Amazon search terms someone would type
- Introduction chapter: hook into the reader's pain, promise the transformation, preview the system
- Conclusion chapter: synthesize the full system, give a 30-day action plan, forward momentum

Write all {num_chapters} chapters now. Be specific. Be concrete. Make every section title a reason to read."""

    log(f"Calling Qwen 35B for outline generation (~45-90 sec)...")
    result = ollama_call(user, system, OUTLINE_MODEL, num_predict=8000, temperature=0.75)

    if not result:
        return None

    # Validate we got something substantial
    chapter_count = len(re.findall(r"^## Chapter \d+:", result, re.MULTILINE))
    if chapter_count < num_chapters - 1:
        warning(f"Outline has only {chapter_count} chapters (expected {num_chapters}). "
                "Model may have cut off early.")
        if chapter_count < 5:
            return None

    log(f"Outline generated: {chapter_count} chapters, {len(result)} chars")
    return result


# ======================================================================
# COVER PROMPT GENERATION
# ======================================================================

COVER_PROMPT_EXAMPLES = """
EXAMPLE 1 (productivity niche — geometric/abstract):
Overhead view of a desk surface with clean geometric objects — a perfect cube, sphere, and pyramid — each casting a single sharp shadow in amber light. The objects are arranged in a spiral pattern converging on a bright focal point. Deep charcoal background with subtle warm gradient. Sharp, modern, minimalist. Cinematic lighting, photorealistic CGI. No text. Professional nonfiction book cover background.

EXAMPLE 2 (health niche — landscape/natural):
Wide aerial view of a calm mountain lake at dawn, perfectly still water reflecting a gradient sky from deep indigo to soft coral. Thin morning mist rising from the water surface. Pine forest silhouette framing both sides. Stillness, restoration, natural rhythm. Soft volumetric lighting, photorealistic. No text. Professional nonfiction book cover background.

EXAMPLE 3 (health niche — mechanical/metaphorical):
Close-up of an intricate golden clockwork mechanism floating in dark space, gears and springs interlocking with organic vine-like tendrils wrapping through the machinery. Warm amber and deep bronze tones. Each gear pulses with soft bioluminescent light suggesting living energy. Cinematic macro photography style, shallow depth of field. No text. Professional nonfiction book cover background.

EXAMPLE 4 (tech/security niche):
Dark control room perspective: glowing circuit board patterns recede into deep space. Bright green and cyan data streams flow along geometric pathways. Central lock symbol radiates light outward against midnight blue black background. High contrast, sleek, cinematic tech aesthetic. No text. Professional cybersecurity nonfiction book cover background.

EXAMPLE 5 (self-help niche):
Single beam of brilliant white-gold light breaking through dense storm clouds from above, illuminating a dramatic landscape below. Dark purple-blue storm above, warm golden light at the focal point. Rays radiating downward, volumetric god-rays effect. Inspiring, transformative, powerful visual metaphor for breakthrough. No text. Professional self-help nonfiction book cover background.

EXAMPLE 6 (business/AI niche — abstract flow):
Abstract visualization of human handwriting merging into digital light streams. Warm ink strokes on the left transition into clean luminous code particles on the right. Deep navy background with subtle grid lines fading into darkness. The merging point glows with soft white-gold energy. Cinematic, photorealistic CGI. No text. Professional nonfiction book cover background.

ANTI-PATTERNS — do NOT use these overused motifs:
- Translucent human head/brain/silhouette (overused across catalog)
- Split-hemisphere brain imagery (too similar between books)
- Glowing neural networks or "organized vs chaotic" brain splits
- Generic body outlines with internal glow

Instead, choose visual metaphors from: landscapes, architecture, natural objects, mechanical systems, abstract geometry, light/shadow play, aerial perspectives, macro details, weather phenomena, botanical elements.
"""


def generate_cover_prompt(topic: dict, outline_text: str) -> str | None:
    """Ask Qwen 35B to write a book-specific Ideogram background prompt."""
    title = topic.get("title", "Unknown Book")

    # Extract core promise from outline header if present
    promise_match = re.search(r"\*\*Core Promise:\*\*\s*(.+)", outline_text)
    promise = promise_match.group(1).strip() if promise_match else ""

    system = (
        "You are a professional book cover art director. "
        "You write precise, cinematic visual prompts for an AI image generator (Ideogram) "
        "that creates the BACKGROUND layer of a nonfiction ebook cover. "
        "The prompt describes ONLY the background image — no text, no title, no author name. "
        "Single paragraph, 2-4 sentences. Highly specific about colors, lighting, mood, and visual metaphor. "
        "No generic gradients. Be concrete and cinematic. "
        "Output ONLY the prompt — no preamble, no explanation."
    )

    user = (
        f"Write an Ideogram background prompt for this nonfiction ebook:\n\n"
        f"Title: {title}\n"
        f"Core promise: {promise}\n\n"
        f"Study these examples — match their specificity and cinematic quality:\n"
        f"{COVER_PROMPT_EXAMPLES}\n\n"
        f"Now write a single-paragraph Ideogram background prompt specifically for this book. "
        f"End with: No text. Professional nonfiction book cover background."
    )

    log("Generating cover prompt via Qwen 35B...")
    raw = ollama_call(user, system, COVER_MODEL, num_predict=300, temperature=0.8)
    if not raw or len(raw) < 50:
        warning("Cover prompt too short or failed.")
        return None

    if "No text." not in raw:
        raw += " No text. Professional nonfiction book cover background."

    log(f"Cover prompt: {raw[:80]}...")
    return raw


# ======================================================================
# VALIDATION
# ======================================================================

def validate_outline(outline: str, num_chapters: int) -> list:
    """Return list of issues. Empty list = pass."""
    issues = []
    chapter_count = len(re.findall(r"^## Chapter \d+:", outline, re.MULTILINE))
    if chapter_count < num_chapters - 1:
        issues.append(f"Chapter count {chapter_count} < expected {num_chapters}")

    if "Word Count Target:" not in outline:
        issues.append("Missing Word Count Target fields")

    if "Keywords:" not in outline:
        issues.append("Missing Keywords fields")

    # Check for template contamination — these generic names shouldn't appear
    generic_patterns = [
        r"Core Concept \d",
        r"Practical Application\b",
        r"Case Study\b.*?Focus.*?Real-world example",
        r"Chapter Summary & Preview",
    ]
    for pat in generic_patterns:
        if re.search(pat, outline):
            issues.append(f"Template contamination detected: '{pat}'")

    if len(outline) < 5000:
        issues.append(f"Outline suspiciously short ({len(outline)} chars) — likely incomplete")

    return issues


# Phrases that indicate a section example is a placeholder, not a real example
_VAGUE_EXAMPLE_PATTERNS = [
    r"\*\*Example:\*\*\s*Key example\b",
    r"\*\*Example:\*\*\s*Success story\b",
    r"\*\*Example:\*\*\s*Step-by-step\b",
    r"\*\*Example:\*\*\s*Case study\b",
    r"\*\*Example:\*\*\s*Real-world example\b",
    r"\*\*Example:\*\*\s*Industry example\b",
    r"\*\*Example:\*\*\s*Market data\b",
    r"\*\*Example:\*\*\s*Tool list\b",
    r"\*\*Example:\*\*\s*Synthesis\b",
    r"\*\*Example:\*\*\s*Transition hook\b",
    r"\*\*Example:\*\*\s*Opening scenario\b",
    r"\*\*Example:\*\*\s*Troubleshooting guide\b",
    r"\*\*Example:\*\*\s*Bridge to next\b",
    r"\*\*Example:\*\*\s*30-day plan\b",
    r"\*\*Example:\*\*\s*Call to action\b",
]


def find_vague_sections(outline: str) -> list[tuple[str, str]]:
    """
    Find sections with placeholder examples rather than specific scenarios.
    Returns list of (chapter_title, section_name) tuples for vague sections.
    """
    vague = []
    # Walk chapter by chapter
    chapters = re.split(r"(?=^## Chapter \d+:)", outline, flags=re.MULTILINE)
    for chapter_block in chapters:
        ch_title_m = re.search(r"^## Chapter \d+:\s*(.+)", chapter_block, re.MULTILINE)
        ch_title = ch_title_m.group(1).strip() if ch_title_m else "Unknown Chapter"

        # Walk section by section within the chapter
        sections = re.split(r"(?=^\d+\.\s+\*\*\[)", chapter_block, flags=re.MULTILINE)
        for section_block in sections:
            sec_title_m = re.search(r"\*\*\[(.+?)\]\*\*", section_block)
            sec_title = sec_title_m.group(1).strip() if sec_title_m else ""
            if not sec_title:
                continue
            for pat in _VAGUE_EXAMPLE_PATTERNS:
                if re.search(pat, section_block, re.IGNORECASE):
                    vague.append((ch_title, sec_title))
                    break  # one match per section is enough

    return vague


def regenerate_vague_sections(outline: str, vague: list[tuple[str, str]],
                               topic: dict) -> str | None:
    """
    Ask Qwen 35B to rewrite only the vague Example lines.
    Returns ONLY the replacement lines as JSON, then patches them in — never
    asks the model to return the full outline (too slow, too likely to timeout).
    """
    if not vague:
        return outline

    vague_list = "\n".join(
        f"  - Chapter '{ch}', Section '{sec}'" for ch, sec in vague
    )
    title = topic.get("title", "Unknown")

    system = (
        "You are a nonfiction book editor. "
        "You write specific, concrete example sentences for book outline sections. "
        "Output ONLY a JSON array of objects with 'chapter', 'section', and 'example' keys. "
        "No preamble. No explanation. JSON only."
    )

    user = (
        f"Book: '{title}'\n\n"
        f"These outline sections have placeholder examples that need to be specific:\n"
        f"{vague_list}\n\n"
        f"For each section, write a concrete example: a real scenario, named technique, "
        f"specific data point, or concrete before/after. 1-2 sentences max.\n\n"
        f"Output JSON array:\n"
        f'[{{"chapter": "...", "section": "...", "example": "..."}}]'
    )

    log(f"Regenerating {len(vague)} vague section(s) via Qwen 35B (targeted call)...")
    result = ollama_call(user, system, OUTLINE_MODEL, num_predict=600, temperature=0.7)

    if not result:
        log("WARNING: Vague section fix returned empty — keeping original outline")
        return outline

    # Parse the JSON replacements
    try:
        json_match = re.search(r"\[.*\]", result, re.DOTALL)
        if not json_match:
            log("WARNING: Could not parse replacement JSON — keeping original outline")
            return outline

        replacements = json.loads(json_match.group(0))
    except Exception as e:
        log(f"WARNING: JSON parse failed ({e}) — keeping original outline")
        return outline

    # Surgically patch each Example line in the outline
    patched = outline
    patch_count = 0
    for item in replacements:
        section = item.get("section", "")
        new_example = item.get("example", "").strip()
        if not section or not new_example:
            continue

        # Find the section block and replace just its Example line
        # Pattern: section title followed by lines until the next numbered section or chapter
        section_escaped = re.escape(section)
        pattern = rf"(\*\*\[{section_escaped}\]\*\*.*?- \*\*Example:\*\* )[^\n]+"
        replacement = rf"\g<1>{new_example}"
        new_patched = re.sub(pattern, replacement, patched, flags=re.DOTALL | re.IGNORECASE)

        if new_patched != patched:
            patched = new_patched
            patch_count += 1
            log(f"  Patched example in '{section}'")
        else:
            log(f"  WARNING: Could not locate section '{section}' for patching")

    log(f"  {patch_count}/{len(replacements)} section(s) patched")
    return patched


# ======================================================================
# MAIN
# ======================================================================

def main():
    parser = argparse.ArgumentParser(description="Generate LLM-driven book outline")
    parser.add_argument("--topic",    type=str, help="Topic title (or substring)")
    parser.add_argument("--chapters", type=int, default=12, help="Number of chapters")
    parser.add_argument("--niche",    type=str, default="", help="Override niche label")
    args = parser.parse_args()

    log_section("Outliner Agent — Starting")

    # Step 1: Find & load topic plan
    log("Step 1: Finding topic plan...")
    plans = find_topic_plans()
    if not plans:
        error_exit("No topic_plan_*.md files found. Run topic_planner first, "
                   "or use --topic 'Your Topic Title' with --niche 'productivity'")

    topic_data = load_topic_plan(plans[0])
    if not topic_data.get("topics"):
        error_exit("No valid topics found in topic_plan file")

    # Select topic
    if args.topic:
        selected = next(
            (t for t in topic_data["topics"] if args.topic.lower() in t.get("title", "").lower()),
            None,
        )
        if not selected:
            # Build a synthetic topic from CLI args
            log(f"Topic '{args.topic}' not in plan — using as-provided")
            selected = {
                "title": args.topic,
                "viability_score": 7.0,
                "niche": args.niche or "general",
            }
    else:
        selected = topic_data["topics"][0]

    if args.niche:
        selected["niche"] = args.niche

    log(f"Topic: {selected['title']} (niche: {selected.get('niche', '?')}, "
        f"score: {selected.get('viability_score', '?')})")

    viability = selected.get("viability_score") or 7.0
    if viability < 6.0:
        error_exit(f"Topic viability {viability:.1f} < 6.0 minimum. "
                   "Pick a stronger topic or override with --topic.")

    # Step 2: Load context
    log("Step 2: Loading catalog context & style guide...")
    learning_summary = load_learning_summary()
    style_guide = load_style_guide()
    if learning_summary:
        log(f"  Loaded LEARNING.md patterns ({len(learning_summary)} chars)")
    if style_guide:
        log(f"  Loaded style guide ({len(style_guide)} chars)")

    # Step 3: Generate outline via LLM
    log_section("Step 3: Generating outline via Qwen 35B")
    outline = generate_outline_llm(selected, args.chapters, learning_summary, style_guide)

    if not outline:
        error_exit("LLM failed to generate outline. Check Ollama is running: "
                   "`ollama list` and `ollama run qwen3.5:27b-16k`")

    # Step 4: Validate
    log_section("Step 4: Validating outline")
    issues = validate_outline(outline, args.chapters)
    if issues:
        for issue in issues:
            warning(f"  Issue: {issue}")
        if any("Template contamination" in i for i in issues):
            warning("Template contamination found — outline quality may be degraded.")
    else:
        log("  Structural validation PASSED")

    # Step 4b: Find and fix vague section examples
    log_section("Step 4b: Checking for placeholder examples")
    vague = find_vague_sections(outline)
    if vague:
        log(f"  Found {len(vague)} vague section(s):")
        for ch, sec in vague:
            log(f"    - '{sec}' in '{ch}'")
        outline = regenerate_vague_sections(outline, vague, selected)
        # Re-check after fix
        remaining = find_vague_sections(outline)
        if remaining:
            warning(f"  {len(remaining)} section(s) still vague after fix attempt — continuing anyway")
        else:
            log(f"  All {len(vague)} vague section(s) resolved")
    else:
        log("  No placeholder examples found — outline is specific throughout")

    # Step 5: Create workbook & write outline
    log_section("Step 5: Creating workbook")
    slug = slugify(selected["title"])
    workbook_dir = WORKBOOKS_DIR / f"book-{slug}"
    workbook_dir.mkdir(parents=True, exist_ok=True)
    log(f"  Workbook: {workbook_dir}")

    # Prepend metadata header if LLM didn't include it
    timestamp = datetime.now().isoformat(timespec="seconds")
    header = (
        f"<!-- AUTO-GENERATED: {timestamp} -->\n"
        f"<!-- Model: {OUTLINE_MODEL} -->\n\n"
    )
    if not outline.startswith("#"):
        outline = f"# Book Outline: {selected['title']}\n\n" + outline

    outline_path = workbook_dir / "01_outline.md"
    write_file(outline_path, header + outline)
    log(f"  Outline written: {outline_path}")

    # Step 6: Generate cover prompt
    log_section("Step 6: Generating cover prompt")
    cover_prompt = generate_cover_prompt(selected, outline)
    if cover_prompt:
        cp_path = workbook_dir / "cover_prompt.txt"
        write_file(cp_path, cover_prompt)
        log(f"  Cover prompt written: {cp_path}")
    else:
        warning("  Cover prompt failed — cover generator will use niche palette fallback.")

    # Done
    log_section("OUTLINER COMPLETE")
    log(f"Book:     {selected['title']}")
    log(f"Workbook: {workbook_dir}")
    log(f"Chapters: {len(re.findall(chr(10)+'## Chapter', outline))} detected")
    log(f"Outline:  {outline_path}")
    log("")
    log("Next step: run Chapter-Builder")
    log(f"  cd ~/.hermes/ebook-factory/skills/chapter-builder/")
    log(f"  for ch in 1 2 3 4 5 6 7 8 9 10; do")
    log(f"    python3 chapter_builder.py --chapter $ch --book-dir {workbook_dir} &")
    log(f"  done && wait")

    return 0


if __name__ == "__main__":
    sys.exit(main())
