#!/usr/bin/env python3
"""
Topic Pipeline — Two-pass planner + live market research.

Pass 1 (Qwen 27B):  Read LEARNING.md → generate 3-5 candidate topics
                    with catalog-aware differentiation and creative angles.

Pass 2 (Researcher): Scrape live Amazon data for each candidate —
                     BSR, review counts, price points, competitor titles.

Pass 3 (Qwen 27B):  Re-rank candidates using live market scores,
                     output final justified topic_plan.md.

Usage:
    python3 topic_pipeline.py                        # full auto
    python3 topic_pipeline.py --count 3              # fewer candidates
    python3 topic_pipeline.py --niche health         # focus a niche
    python3 topic_pipeline.py --idea "gut reset"     # explore an idea
    python3 topic_pipeline.py --skip-research        # planner only (no scraping)
    python3 topic_pipeline.py --dry-run              # show what would run
"""

import os
import sys
import re
import json
import argparse
import requests
from pathlib import Path
from datetime import datetime

# ── Paths ──────────────────────────────────────────────────────────────────────

HERMES_HOME   = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
LEARNING_FILE = Path.home() / "books" / "factory" / "LEARNING.md"
OUTPUT_DIR    = HERMES_HOME / "output" / "planner"

RESEARCHER_DIR = HERMES_HOME / "ebook-factory" / "skills" / "researcher"

OLLAMA_URL    = "http://localhost:11434/api/chat"
PLANNER_MODEL = "qwen3.5:27b-16k"   # Creative/generative — best for idea gen
TIMEOUT       = 300

# ── Logging ────────────────────────────────────────────────────────────────────

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def log_section(title):
    print(f"\n{'='*60}\n  {title}\n{'='*60}", flush=True)

def die(msg):
    print(f"\n[ERROR] {msg}", file=sys.stderr, flush=True)
    sys.exit(1)

# ── Ollama ─────────────────────────────────────────────────────────────────────

def ollama(prompt: str, system: str, num_predict: int = 3000,
           temperature: float = 0.75) -> str:
    """Call Qwen 27B. Raises on connection failure."""
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
                    "temperature": temperature,
                    "num_predict": num_predict,
                    "num_ctx": 16384,
                },
            },
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        raw = resp.json()["message"]["content"].strip()
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        return raw
    except requests.exceptions.ConnectionError:
        die("Ollama not reachable. Run: ollama serve")
    except Exception as e:
        die(f"Ollama call failed: {e}")

# ── Context loading ────────────────────────────────────────────────────────────

def load_learning_md() -> str:
    if not LEARNING_FILE.exists():
        log("WARNING: No LEARNING.md found — using first-principles only")
        return "(No catalog data — fresh start)"
    return LEARNING_FILE.read_text(encoding="utf-8")[:8000]

# ── Pass 1: Generate candidates ────────────────────────────────────────────────

PASS1_SYSTEM = """You are a publishing strategist specializing in practical nonfiction for Amazon KDP.

You generate specific, commercially viable book topic candidates that:
- Don't duplicate what the author has already published
- Target specific underserved pain points in proven niches
- Have titles that are hooks, not generic labels
- Build logically on the existing catalog's proven positioning

Output ONLY a JSON array. No preamble, no explanation."""

def generate_candidates(learning_md: str, count: int,
                         niche_focus: str, idea: str) -> list[dict]:
    """
    Pass 1: Ask Qwen 27B for candidate topics.
    Returns list of dicts: {title, niche, search_keyword, angle, target_reader, catalog_fit}
    """
    niche_note = f"\nFocus on the {niche_focus} niche." if niche_focus else ""
    idea_note  = f"\nThe author is interested in: '{idea}'. Include at least 2 angles on this." if idea else ""

    prompt = f"""Here is my published catalog with performance data:

{learning_md}

Generate {count} specific book topic candidates for my next publications.{niche_note}{idea_note}

Rules:
- Titles must be specific hooks. "Sleep Smarter After 50" beats "Sleep Optimization Guide"
- Never suggest a topic already covered in the catalog above
- Target reader must name a specific situation, not "busy people"
- search_keyword: the exact 2-4 word phrase someone types into Amazon to find this book
- Include at least one contrarian or underserved angle

Return a JSON array with {count} objects, each with these exact keys:
{{
  "title": "Full Book Title: Subtitle Hook",
  "niche": "one of: productivity, health, tech-security, self-help, business, ai-productivity",
  "search_keyword": "2-4 word Amazon search phrase",
  "angle": "1-2 sentences on what makes this book different from existing titles",
  "target_reader": "specific person with specific pain point",
  "catalog_fit": "how this cross-sells with existing books"
}}

Output ONLY the JSON array."""

    log(f"Pass 1: generating {count} candidates via Qwen 27B...")
    raw = ollama(prompt, PASS1_SYSTEM, num_predict=2000, temperature=0.8)

    # Extract JSON array
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        log(f"WARNING: Could not parse JSON from pass 1. Raw output:\n{raw[:400]}")
        die("Pass 1 returned no valid JSON. Check Ollama and retry.")

    try:
        candidates = json.loads(match.group(0))
        log(f"  Got {len(candidates)} candidates")
        return candidates
    except json.JSONDecodeError as e:
        log(f"JSON parse error: {e}\nRaw: {raw[:400]}")
        die("Failed to parse candidates JSON.")

# ── Pass 2: Research each candidate ───────────────────────────────────────────

def research_candidates(candidates: list[dict], skip_bsr: bool = False) -> list[dict]:
    """
    Pass 2: Run the researcher on each candidate's search keyword.
    Attaches market data to each candidate dict.
    Returns enriched candidates list.
    """
    # Insert researcher directory into path at call time, not module load time.
    # This avoids module-level side effects and fails loudly if the path is wrong.
    if not RESEARCHER_DIR.exists():
        log(f"WARNING: Researcher not found at {RESEARCHER_DIR}")
        log("Skipping live market research — results will use planner scores only")
        for c in candidates:
            c["market"] = None
        return candidates

    researcher_str = str(RESEARCHER_DIR)
    if researcher_str not in sys.path:
        sys.path.insert(0, researcher_str)

    try:
        from researcher import research_niche
        log("Researcher module loaded successfully")
    except ImportError as e:
        log(f"WARNING: Cannot import researcher: {e}")
        log("Skipping live market research — results will use planner scores only")
        for c in candidates:
            c["market"] = None
        return candidates

    enriched = []
    total    = len(candidates)

    for i, candidate in enumerate(candidates, 1):
        keyword  = candidate.get("search_keyword", candidate["title"].split(":")[0])
        title    = candidate["title"]
        log_section(f"Researching {i}/{total}: '{keyword}'")

        try:
            result = research_niche(
                niche=keyword,
                max_results=8,
                force_tier=0,        # waterfall: Firecrawl → Scrapling → Camoufox
                dry_run=False,       # writes to LEARNING.md (good — builds your data)
                skip_bsr=skip_bsr,
            )
            candidate["market"] = result["market"]
            candidate["top_books"] = [
                {"title": b.get("title", ""), "reviews": b.get("review_count", 0),
                 "rating": b.get("rating"), "price": b.get("price")}
                for b in result.get("top_books", [])[:5]
            ]
            candidate["bsr_best"] = result["market"].get("best_kindle_bsr")
            candidate["books_found"] = result["books_found"]

            score = result["market"]["score"]
            verdict = result["market"]["verdict"]
            bsr = candidate["bsr_best"]
            bsr_str = f" | BSR #{bsr:,}" if bsr else ""
            log(f"  Score: {score}/10 — {verdict}{bsr_str}")

        except Exception as e:
            log(f"  Research failed for '{keyword}': {e}")
            candidate["market"] = None
            candidate["top_books"] = []
            candidate["bsr_best"] = None
            candidate["books_found"] = 0

        enriched.append(candidate)

    return enriched

# ── Pass 3: Re-rank with market data ──────────────────────────────────────────

PASS3_SYSTEM = """You are a senior publishing strategist making a final book recommendation.

You have candidate topics with live Amazon market data. Your job:
1. Re-rank the candidates by commercial viability (BSR is the strongest signal)
2. Pick the single best book to write next
3. Write a final, production-ready topic plan

Rules for ranking:
- BSR < 5,000 in best competitor = hot market, prioritize
- BSR 5,000–20,000 = active market, good opportunity
- BSR > 50,000 = thin demand, deprioritize unless unique angle is exceptional
- High review counts (> 2,000 avg) = proven demand AND tougher competition — need a sharp angle
- Low review counts + good BSR = underserved niche, prioritize

Output clean Markdown only. No preamble."""

def rerank_with_market_data(candidates: list[dict], learning_md: str) -> str:
    """
    Pass 3: Feed all candidates + market data back to Qwen for final ranking.
    Returns the full topic_plan markdown string.
    """
    # Build a compact summary of each candidate + their market data
    summaries = []
    for i, c in enumerate(candidates, 1):
        m = c.get("market") or {}
        bsr = c.get("bsr_best")
        bsr_str = f"BSR #{bsr:,}" if bsr else "BSR: unknown"
        top_titles = ", ".join(
            f'"{b["title"][:50]}" ({b["reviews"]} reviews)'
            for b in c.get("top_books", [])[:3]
            if b.get("title")
        ) or "(no competitor data)"

        summaries.append(f"""Candidate {i}: {c['title']}
  Niche: {c['niche']}
  Search keyword: {c.get('search_keyword', '?')}
  Market score: {m.get('score', '?')}/10
  Market verdict: {m.get('verdict', 'unknown')}
  Best competitor BSR: {bsr_str}
  Avg competitor reviews: {m.get('avg_reviews', 0):,}
  Competition level: {m.get('competition', 'unknown')}
  Avg price: ${m.get('top_price', '?')}
  Your angle: {c.get('angle', '')}
  Target reader: {c.get('target_reader', '')}
  Catalog fit: {c.get('catalog_fit', '')}
  Top competitors: {top_titles}""")

    candidates_block = "\n\n".join(summaries)

    prompt = f"""I have {len(candidates)} book topic candidates with live Amazon market data.
My published catalog (for context on differentiation):

{learning_md[:3000]}

---

CANDIDATE MARKET ANALYSIS:

{candidates_block}

---

Based on this data, produce a final topic plan. Format:

# Book Topic Plan — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Executive Summary

[2-3 sentences: what the data shows, which niche is hottest right now, what the winning strategy is]

### Top 3 Priorities

1. **[Title]**
   - Niche: `niche`
   - Score: X.XX/10
   - Market signal: [BSR verdict in one line]

2. **[Title]**
   - Niche: `niche`
   - Score: X.XX/10
   - Market signal: [BSR verdict in one line]

3. **[Title]**
   - Niche: `niche`
   - Score: X.XX/10
   - Market signal: [BSR verdict in one line]

---

## Recommended Book: [Title]

### Why This One
[2-3 sentences explaining why market data + catalog fit makes this the best choice right now]

### Market Evidence
- Best competitor BSR: [number and what it means]
- Competition level: [assessment]
- Price point: [recommendation]
- Window: [is this evergreen or time-sensitive?]

### The Angle
[2-3 sentences on the specific differentiation that makes this book winnable]

### Target Reader
[Specific person with specific pain — not generic]

### Viability Score: X.X/10
**Verdict:** [one line summary]

---

## All Candidates Ranked

[Rank all {len(candidates)} candidates with one-line rationale for each position]

---

## What the Market Is Telling You

[3-5 bullet observations from the live Amazon data — patterns, trends, pricing signals, BSR patterns]

---

## Avoid Right Now

[2-3 specific angles the data says are oversaturated or underperforming]"""

    log("Pass 3: re-ranking with market data via Qwen 27B...")
    return ollama(prompt, PASS3_SYSTEM, num_predict=3000, temperature=0.65)

# ── Output ─────────────────────────────────────────────────────────────────────

def write_outputs(plan_content: str, candidates: list[dict]) -> Path:
    """Write topic_plan_latest.md and a JSON data file."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    latest_path = OUTPUT_DIR / "topic_plan_latest.md"
    dated_path  = OUTPUT_DIR / f"topic_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    json_path   = OUTPUT_DIR / "topic_plan_latest_data.json"

    latest_path.write_text(plan_content, encoding="utf-8")
    dated_path.write_text(plan_content, encoding="utf-8")

    # Also write raw candidate data as JSON for debugging/future use
    json_path.write_text(
        json.dumps(candidates, indent=2, default=str),
        encoding="utf-8"
    )

    log(f"Plan written:  {latest_path}")
    log(f"Archive:       {dated_path}")
    log(f"Data JSON:     {json_path}")
    return latest_path

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Topic Pipeline — Planner + Researcher + Re-rank"
    )
    parser.add_argument("--count",          type=int, default=5,
                        help="Number of candidates to generate (default: 5)")
    parser.add_argument("--niche",          type=str, default="",
                        help="Focus on a specific niche")
    parser.add_argument("--idea",           type=str, default="",
                        help="Specific topic idea to explore")
    parser.add_argument("--skip-research",  action="store_true",
                        help="Skip live Amazon research (planner-only mode)")
    parser.add_argument("--skip-bsr",       action="store_true",
                        help="Skip BSR product page fetching (saves ~3 Firecrawl credits per candidate)")
    parser.add_argument("--dry-run",        action="store_true",
                        help="Show plan without running")
    args = parser.parse_args()

    log_section("Topic Pipeline — Starting")
    log(f"  Candidates: {args.count}")
    log(f"  Niche focus: {args.niche or 'all'}")
    log(f"  Idea: {args.idea or 'none'}")
    log(f"  Research: {'SKIPPED' if args.skip_research else 'ON'}")
    log(f"  BSR fetch: {'SKIPPED' if args.skip_bsr else 'ON'}")

    if args.dry_run:
        log("\nDRY RUN — no LLM calls, no scraping")
        log(f"Would: generate {args.count} candidates via Qwen 27B")
        log(f"Would: research each via Firecrawl/BSR (~{args.count * 4} Firecrawl credits)")
        log(f"Would: re-rank via Qwen 27B")
        return 0

    # Load catalog
    log_section("Loading catalog data")
    learning_md = load_learning_md()
    log(f"  LEARNING.md: {len(learning_md)} chars")

    # Pass 1: Generate candidates
    log_section("Pass 1 — Generating candidates")
    candidates = generate_candidates(learning_md, args.count, args.niche, args.idea)

    log("\nCandidates generated:")
    for i, c in enumerate(candidates, 1):
        log(f"  {i}. {c['title']} [{c.get('search_keyword','')}]")

    # Pass 2: Research (unless skipped)
    if not args.skip_research:
        log_section("Pass 2 — Live Amazon research")
        credits_used = args.count * (4 if not args.skip_bsr else 1)
        log(f"  Estimated Firecrawl credits: ~{credits_used} of 3,000/month")
        candidates = research_candidates(candidates, skip_bsr=args.skip_bsr)
    else:
        log_section("Pass 2 — SKIPPED (--skip-research)")
        for c in candidates:
            c["market"] = None
            c["top_books"] = []
            c["bsr_best"] = None

    # Pass 3: Re-rank and generate final plan
    log_section("Pass 3 — Re-ranking with market data")
    plan_content = rerank_with_market_data(candidates, learning_md)

    if not plan_content:
        die("Pass 3 returned empty output")

    # Write outputs
    log_section("Writing outputs")
    plan_path = write_outputs(plan_content, candidates)

    # Summary
    log_section("PIPELINE COMPLETE")

    # Print top recommendation
    rec_match = re.search(
        r"## Recommended Book: (.+?)(?=\n###|\n---|\Z)",
        plan_content, re.DOTALL
    )
    if rec_match:
        log(f"\nTOP RECOMMENDATION:")
        print(rec_match.group(0).strip()[:600])

    log(f"\nFull plan: {plan_path}")
    log("")
    log("Next step — run the outliner:")
    log("  cd ~/.hermes/skills/ebook-factory/skills/outliner/")
    log("  python3 orchestrator.py --topic 'Your Title Here' --niche productivity")

    return 0


if __name__ == "__main__":
    sys.exit(main())
