#!/usr/bin/env python3
"""
Smart Topic Planner — Replaces the template-based planner.

Uses Qwen 35B to read your actual catalog (LEARNING.md) and generate
specific, differentiated, market-aware book topic recommendations.

This is NOT an algorithmic scorer. The LLM reads your real sales data,
understands what angles you've already covered, and suggests titles
that are both commercially viable and distinct from your existing books.

Usage:
    python3 smart_planner.py                        # 5 recommendations
    python3 smart_planner.py --count 3              # Fewer options
    python3 smart_planner.py --niche health         # Focus on a niche
    python3 smart_planner.py --idea "gut health"    # Explore a specific idea
"""

import os
import sys
import re
import json
import argparse
import requests
from pathlib import Path
from datetime import datetime

# ============================================================================
# CONFIG
# ============================================================================

HERMES_HOME    = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
LEARNING_FILE  = Path.home() / "books" / "factory" / "LEARNING.md"
OUTPUT_DIR     = HERMES_HOME / "output" / "planner"

OLLAMA_URL     = "http://localhost:11434/api/chat"
PLANNER_MODEL  = "qwen3.5:35b-a3b-q4_k_m"
REQUEST_TIMEOUT= 300

# ============================================================================
# LOGGING
# ============================================================================

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def die(msg):
    print(f"\n[ERROR] {msg}", file=sys.stderr, flush=True)
    sys.exit(1)

# ============================================================================
# CONTEXT LOADING
# ============================================================================

def load_learning_md() -> str:
    """Load full LEARNING.md — the LLM needs all of it to avoid duplication."""
    if not LEARNING_FILE.exists():
        log(f"WARNING: LEARNING.md not found at {LEARNING_FILE}")
        return ""
    content = LEARNING_FILE.read_text(encoding="utf-8")
    # Cap at 8000 chars — enough for 12+ books with metrics
    return content[:8000]

# ============================================================================
# LLM CALL
# ============================================================================

def call_ollama(prompt: str, system: str, num_predict: int = 4000) -> str | None:
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": PLANNER_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user",   "content": prompt},
                ],
                "stream": False,
                "think": False,
                "options": {
                    "temperature": 0.8,
                    "num_predict": num_predict,
                    "num_ctx": 16384,
                },
            },
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        raw = resp.json()["message"]["content"].strip()
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        return raw or None
    except requests.exceptions.ConnectionError:
        die("Ollama not reachable. Run: ollama serve")
    except Exception as e:
        die(f"Ollama call failed: {e}")

# ============================================================================
# TOPIC PLAN GENERATION
# ============================================================================

def generate_topic_plan(learning_md: str, count: int,
                         niche_focus: str, idea: str) -> str:
    """Ask Qwen 35B to generate a real topic plan from catalog data."""

    niche_instruction = ""
    if niche_focus:
        niche_instruction = f"\nFocus recommendations on the {niche_focus} niche specifically."
    idea_instruction = ""
    if idea:
        idea_instruction = f"\nThe user is particularly interested in exploring: '{idea}'. Include at least 2 angles on this idea."

    system = """You are a publishing strategist and nonfiction book market analyst.
You specialize in self-published Amazon KDP ebooks in the practical nonfiction space.

Your job: read a catalog's performance data and generate specific, commercially viable book topic recommendations that:
1. Don't duplicate what's already been published (different angle, not different title)
2. Target underserved pain points in niches that have proven demand
3. Have titles that are specific hooks, not generic labels
4. Show awareness of what positioning has worked vs. failed in this catalog

You think like a publisher, not a content farm. Quality matters. Specificity matters. Differentiation matters."""

    user = f"""Here is my complete published catalog with performance data:

{learning_md}

---

Based on this data, generate {count} specific book topic recommendations for my next publications.

For each recommendation provide:

### [N]. [Specific Book Title: Subtitle Hook]
**Niche:** [niche name]
**Viability Score:** [X.X/10]
**Target Reader:** [specific person with specific pain — not "busy professionals"]
**Core Angle:** [what makes this different from existing books on this topic]
**Why Now:** [why this topic is commercially viable in 2026]
**Gap It Fills:** [what's missing from the current catalog + market]
**Suggested Approach:** [1-2 sentences on the book's core framework or methodology]
**Catalog Fit:** [how it cross-sells with existing books]
**Risks:** [what could go wrong — low demand, oversaturation, etc.]

RULES:
- Titles must be real hooks. "Sleep Smarter After 50" beats "Sleep Optimization Guide"
- Never suggest a topic already well-covered in the catalog above
- Every "Target Reader" must have a specific, named situation: not "people who want to be healthier"
- Scores above 8.0 require explicit justification
- Include at least one unexpected/contrarian angle the market isn't crowded with
- Draw explicit lessons from which books in the catalog performed well vs. poorly and WHY{niche_instruction}{idea_instruction}

After all recommendations, add:

### Catalog Analysis
[3-5 bullet observations about what's working and not working in this catalog that should inform future books]

### Avoid These Angles
[3-5 specific angles/framings that are already saturated or that this catalog has covered]

Output clean Markdown only. No preamble."""

    log(f"Calling Qwen 35B for topic planning (~30-60 sec)...")
    return call_ollama(user, system, num_predict=4000)

# ============================================================================
# OUTPUT FORMATTING
# ============================================================================

def build_topic_plan_file(llm_output: str, count: int,
                           niche_focus: str, idea: str) -> str:
    """Wrap LLM output in the standard topic_plan file format."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Parse viability scores to build Top Priorities section
    # Pattern: ### N. Title — Score: X.X/10
    top_items = []
    for match in re.finditer(
        r"###\s+(\d+)\.\s+(.+?)\n.*?\*\*Viability Score:\*\*\s*(\d+\.?\d*)/10",
        llm_output, re.DOTALL
    ):
        num = match.group(1)
        title = match.group(2).strip()
        score = float(match.group(3))
        niche_m = re.search(r"\*\*Niche:\*\*\s*(\S+)", llm_output[match.start():match.start()+500])
        niche = niche_m.group(1).strip("`") if niche_m else "general"
        top_items.append((score, num, title, niche))

    top_items.sort(reverse=True)

    top3_lines = []
    for i, (score, _, title, niche) in enumerate(top_items[:3], 1):
        top3_lines.append(f"{i}. **{title}**")
        top3_lines.append(f"   - Niche: `{niche}`")
        top3_lines.append(f"   - Score: {score:.2f}/10")
        top3_lines.append("")

    top3 = "\n".join(top3_lines) if top3_lines else "(see recommendations below)"

    focus_note = f"\nFocus: {niche_focus}" if niche_focus else ""
    idea_note  = f"\nExploring: {idea}" if idea else ""

    header = f"""# Book Topic Plan — {timestamp}

Generated by Smart Planner (Qwen 35B)
{focus_note}{idea_note}

---

## Executive Summary

**{count} recommendations** generated from catalog analysis.

### Top 3 Priorities

{top3}
---

## Detailed Recommendations

"""
    return header + llm_output

# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Smart Topic Planner — LLM-driven")
    parser.add_argument("--count",  type=int, default=5,  help="Number of recommendations")
    parser.add_argument("--niche",  type=str, default="", help="Focus on a specific niche")
    parser.add_argument("--idea",   type=str, default="", help="Specific topic idea to explore")
    parser.add_argument("--dry-run",action="store_true",   help="Show prompt, don't call LLM")
    args = parser.parse_args()

    log("Smart Planner — starting")

    # Load catalog data
    log("Loading LEARNING.md...")
    learning_md = load_learning_md()
    if not learning_md:
        log("WARNING: No LEARNING.md found — planner will work from first principles only")
        learning_md = "(No catalog data available — this is a fresh start)"

    log(f"  Catalog: {len(learning_md)} chars")

    if args.dry_run:
        log("DRY RUN — not calling LLM")
        print("\nWould call Qwen 35B with:")
        print(f"  Model: {PLANNER_MODEL}")
        print(f"  Count: {args.count}")
        print(f"  Niche focus: {args.niche or 'none'}")
        print(f"  Idea: {args.idea or 'none'}")
        print(f"  LEARNING.md: {len(learning_md)} chars")
        return 0

    # Generate plan
    llm_output = generate_topic_plan(learning_md, args.count, args.niche, args.idea)
    if not llm_output:
        die("LLM returned empty output")

    # Build final document
    plan_content = build_topic_plan_file(llm_output, args.count, args.niche, args.idea)

    # Write outputs
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    latest_path = OUTPUT_DIR / "topic_plan_latest.md"
    dated_path  = OUTPUT_DIR / f"topic_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

    latest_path.write_text(plan_content, encoding="utf-8")
    dated_path.write_text(plan_content, encoding="utf-8")

    log(f"Plan written: {latest_path}")
    log(f"Archive:      {dated_path}")
    log("")
    log("=" * 50)
    log("TOP RECOMMENDATIONS:")
    # Print the first recommendation block
    first_rec = re.search(r"(### 1\..+?)(?=### 2\.|### Catalog Analysis|\Z)", llm_output, re.DOTALL)
    if first_rec:
        print(first_rec.group(1).strip())
    log("=" * 50)
    log(f"Full plan: {latest_path}")
    log("Next: run the outliner with your chosen topic")
    log("  python3 ~/.hermes/skills/ebook-factory/skills/outliner/orchestrator.py --topic 'Title Here'")

    return 0


if __name__ == "__main__":
    sys.exit(main())
