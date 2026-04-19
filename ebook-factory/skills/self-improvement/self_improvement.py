#!/usr/bin/env python3
"""
Ebook Factory — Self-Improvement Agent
========================================
The factory's brain. Learns from every book published and every research scan
run, continuously improving niche selection, chapter quality, and market timing.

Five modules, designed to run together or independently:

  Module 1: Harvester      — scrapes KDP dashboard for live sales/KENP data
  Module 2: Pattern Analyzer — distills what's working across the catalog
  Module 3: Prompt Refiner  — updates chapter-builder and outliner prompts
  Module 4: Topic Scout     — proactively finds high-potential next topics
  Module 5: Quality Auditor — retrospective per book, closes the feedback loop

Data flows:
  LEARNING.md          ← Harvester appends performance data
  patterns.json        ← Analyzer writes, Refiner + Scout read
  prompt_overrides.json ← Refiner writes, Chapter-Builder reads
  topic_candidates.md  ← Scout writes, Telegram delivers Sunday brief
  audit_log.json       ← Auditor writes, Analyzer reads next cycle

Usage:
  python3 self_improvement.py --all                 # Run full cycle
  python3 self_improvement.py --harvest             # Module 1 only
  python3 self_improvement.py --analyze             # Module 2 only
  python3 self_improvement.py --refine-prompts      # Module 3 only
  python3 self_improvement.py --scout               # Module 4 only
  python3 self_improvement.py --audit               # Module 5 only
  python3 self_improvement.py --report              # Print state, no writes
  python3 self_improvement.py --all --dry-run       # Simulate, no writes
"""

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests

# ── Paths ─────────────────────────────────────────────────────────────────────

def get_hermes_home() -> Path:
    try:
        from hermes_constants import get_hermes_home as _ghh
        return Path(_ghh())
    except ImportError:
        return Path.home() / ".hermes"

HERMES_HOME   = get_hermes_home()
FACTORY_DIR   = HERMES_HOME / "ebook-factory"
SKILLS_DIR    = HERMES_HOME / "ebook-factory" / "skills"
WORKBOOKS_DIR = FACTORY_DIR / "workbooks"
SI_DIR        = SKILLS_DIR / "self-improvement"
SI_DIR.mkdir(parents=True, exist_ok=True)

LEARNING_MD          = Path.home() / "books" / "factory" / "LEARNING.md"
PATTERNS_JSON        = SI_DIR / "patterns.json"
PROMPT_OVERRIDES     = SI_DIR / "prompt_overrides.json"
TOPIC_CANDIDATES     = SI_DIR / "topic_candidates.md"
AUDIT_LOG            = SI_DIR / "audit_log.json"
IMPROVEMENT_REPORT   = SI_DIR / "improvement_report.md"

# Agent prompt files (what Refiner patches)
CHAPTER_BUILDER_PY   = SKILLS_DIR / "chapter-builder" / "chapter_builder.py"
OUTLINER_PY          = HERMES_HOME / "skills" / "ebook-factory" / "skills" / "outliner" / "orchestrator.py"
RESEARCHER_PY        = SKILLS_DIR / "researcher" / "researcher.py"

# ── Env ───────────────────────────────────────────────────────────────────────

def load_env() -> dict:
    env = {}
    for path in [HERMES_HOME / ".env", Path.home() / ".hermes" / ".env"]:
        if path.exists():
            for line in path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    env[k.strip()] = v.strip()
    env.update(os.environ)
    return env

ENV              = load_env()
KDP_EMAIL        = ENV.get("KDP_EMAIL", "")
KDP_PASSWORD     = ENV.get("KDP_PASSWORD", "")
TELEGRAM_TOKEN   = ENV.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = ENV.get("TELEGRAM_CHAT_ID", "")
FIRECRAWL_KEY    = ENV.get("FIRECRAWL_API_KEY", "")

# ── Logging ───────────────────────────────────────────────────────────────────

def log(msg: str, module: str = ""):
    tag = f"[{module}] " if module else ""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {tag}{msg}", flush=True)

def section(title: str):
    print(f"\n{'═'*60}", flush=True)
    print(f"  {title}", flush=True)
    print(f"{'═'*60}", flush=True)

# ── Telegram ──────────────────────────────────────────────────────────────────

def notify_telegram(msg: str, parse_mode: str = "Markdown"):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": parse_mode},
            timeout=10,
        )
    except Exception as e:
        log(f"Telegram failed (non-fatal): {e}")

# ══════════════════════════════════════════════════════════════════════════════
# MODULE 1: PERFORMANCE HARVESTER
# ══════════════════════════════════════════════════════════════════════════════

def parse_learning_md_books() -> list[dict]:
    """
    Parse all existing book performance entries from LEARNING.md.
    Returns list of book dicts with: title, asin, royalty, units, kenp,
    niche, niche_score, date, royalty_per_unit, kenp_per_unit.
    """
    if not LEARNING_MD.exists():
        return []

    text = LEARNING_MD.read_text(encoding="utf-8", errors="replace")
    books = []

    # Split on book entry headers
    book_blocks = re.split(r"\n---\n", text)

    for block in book_blocks:
        # Only process blocks that look like book performance entries
        if "ASIN:" not in block or "Royalty:" not in block:
            continue

        book = {}

        # Title and date
        title_m = re.search(r"## \[(\d{4}-\d{2}-\d{2})\] Book: (.+?)(?:\s+\(ASIN:|\n)", block)
        if title_m:
            book["date"]  = title_m.group(1)
            book["title"] = title_m.group(2).strip()

        # ASIN
        asin_m = re.search(r"ASIN:\s*([A-Z0-9]{10})", block)
        if asin_m:
            book["asin"] = asin_m.group(1)

        # Royalty
        royalty_m = re.search(r"Royalty:\s*\$?([\d,\.]+)", block)
        if royalty_m:
            try:
                book["royalty"] = float(royalty_m.group(1).replace(",", ""))
            except ValueError:
                book["royalty"] = 0.0

        # Units sold
        units_m = re.search(r"Units Sold:\s*(\d+)", block)
        if units_m:
            book["units"] = int(units_m.group(1))

        # KENP pages
        kenp_m = re.search(r"KENP Pages:\s*([\d,]+)", block)
        if kenp_m:
            book["kenp"] = int(kenp_m.group(1).replace(",", ""))

        # Price
        price_m = re.search(r"Price:\s*\$?([\d\.]+)", block)
        if price_m:
            try:
                book["price"] = float(price_m.group(1))
            except ValueError:
                book["price"] = 4.99

        # Niche category — strip markdown bold markers
        niche_m = re.search(r"Niche Category:\s*(.+)", block)
        if niche_m:
            book["niche"] = re.sub(r"\*+", "", niche_m.group(1)).strip()

        # Niche score
        score_m = re.search(r"Niche Score:\s*([\d\.]+)", block)
        if score_m:
            try:
                book["niche_score"] = float(score_m.group(1))
            except ValueError:
                pass

        # Derived metrics
        book["royalty_per_unit"] = (
            book.get("royalty", 0) / book["units"]
            if book.get("units", 0) > 0 else 0.0
        )
        book["kenp_per_unit"] = (
            book.get("kenp", 0) / book["units"]
            if book.get("units", 0) > 0 else 0.0
        )

        if book.get("title") and book.get("asin"):
            books.append(book)

    return books


def scrape_kdp_dashboard_bsr(asins: list[str]) -> dict[str, dict]:
    """
    Scrape current BSR for each published ASIN from Amazon product pages.
    Returns dict: asin → {kindle_bsr, book_bsr, rating, review_count, updated}

    Tier 1: Plain requests with browser-like headers (FREE, ~1.5s/page, works)
    Tier 2: Firecrawl API (costs credits, last resort)
    """
    results = {}

    # ── Tier 1: Plain requests ──────────────────────────────────────────────
    BSR_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }

    for asin in asins:
        try:
            log(f"  Scraping BSR for ASIN {asin}...", "Harvester")
            resp = requests.get(
                f"https://www.amazon.com/dp/{asin}/",
                headers=BSR_HEADERS,
                timeout=15,
            )
            if resp.status_code == 404:
                log(f"    ASIN {asin} not found (404) — product may be delisted", "Harvester")
                continue
            if resp.status_code != 200:
                log(f"    Failed: HTTP {resp.status_code}", "Harvester")
                continue

            html = resp.text
            bsr_data = {"asin": asin, "updated": datetime.now().isoformat()}

            # Kindle BSR
            km = re.search(r"#([\d,]+)\s+in\s+Kindle\s+Store", html, re.IGNORECASE)
            if km:
                bsr_data["kindle_bsr"] = int(km.group(1).replace(",", ""))

            # Books BSR
            bm = re.search(r"#([\d,]+)\s+in\s+Books\b", html, re.IGNORECASE)
            if bm:
                bsr_data["book_bsr"] = int(bm.group(1).replace(",", ""))

            # Rating
            rm = re.search(r"(\d+\.\d+)\s+out\s+of\s+5\s+stars?", html, re.IGNORECASE)
            if rm:
                try:
                    bsr_data["rating"] = float(rm.group(1))
                except ValueError:
                    pass

            # Reviews
            rev_m = re.search(r"([\d,]+)\s+ratings?", html, re.IGNORECASE)
            if rev_m:
                try:
                    bsr_data["review_count"] = int(rev_m.group(1).replace(",", ""))
                except ValueError:
                    pass

            results[asin] = bsr_data
            log(f"    BSR: #{bsr_data.get('kindle_bsr','?')} Kindle | "
                f"{bsr_data.get('review_count','?')} reviews | "
                f"{bsr_data.get('rating','?')} stars", "Harvester")
            time.sleep(0.5)  # gentle rate limit

        except Exception as e:
            log(f"    Error scraping {asin}: {e}", "Harvester")

    # ── Tier 2: Firecrawl fallback (only if Tier 1 got nothing) ─────────────
    if not results and asins and FIRECRAWL_KEY:
        log("Tier 1 (plain requests) failed for all ASINs — trying Firecrawl fallback", "Harvester")
        for asin in asins:
            try:
                resp = requests.post(
                    "https://api.firecrawl.dev/v1/scrape",
                    headers={"Authorization": f"Bearer {FIRECRAWL_KEY}"},
                    json={
                        "url": f"https://www.amazon.com/dp/{asin}/",
                        "formats": ["markdown"],
                        "onlyMainContent": True,
                        "timeout": 30000,
                    },
                    timeout=40,
                )
                if resp.status_code != 200:
                    log(f"    Firecrawl failed: HTTP {resp.status_code}", "Harvester")
                    continue
                raw = resp.json().get("data", {}).get("markdown", "")
                bsr_data = {"asin": asin, "updated": datetime.now().isoformat()}
                km = re.search(r"#([\d,]+)\s+in\s+Kindle\s+Store", raw, re.IGNORECASE)
                if km:
                    bsr_data["kindle_bsr"] = int(km.group(1).replace(",", ""))
                bm = re.search(r"#([\d,]+)\s+in\s+Books\b", raw, re.IGNORECASE)
                if bm:
                    bsr_data["book_bsr"] = int(bm.group(1).replace(",", ""))
                rm = re.search(r"(\d+\.\d+)\s+out\s+of\s+5\s+stars?", raw, re.IGNORECASE)
                if rm:
                    try: bsr_data["rating"] = float(rm.group(1))
                    except ValueError: pass
                rev_m = re.search(r"([\d,]+)\s+ratings?", raw, re.IGNORECASE)
                if rev_m:
                    try: bsr_data["review_count"] = int(rev_m.group(1).replace(",", ""))
                    except ValueError: pass
                results[asin] = bsr_data
                time.sleep(1.0)
            except Exception as e:
                log(f"    Firecrawl error for {asin}: {e}", "Harvester")

    return results


def harvest_performance(dry_run: bool = False) -> dict:
    """
    Module 1: Parse existing LEARNING.md books and scrape live BSR data.
    Appends a dated performance update entry to LEARNING.md.
    Returns summary dict.
    """
    section("Module 1: Performance Harvester")
    books = parse_learning_md_books()
    log(f"Found {len(books)} books in LEARNING.md", "Harvester")

    if not books:
        log("No books found — nothing to harvest", "Harvester")
        return {"books": 0}

    # Get ASINs with existing performance data (deduplicated)
    seen_asins = set()
    unique_books = []
    for b in books:
        asin = b.get("asin", "")
        if asin and asin not in seen_asins:
            seen_asins.add(asin)
            unique_books.append(b)
    books = unique_books
    log(f"After dedup: {len(books)} unique books", "Harvester")

    asins = [b["asin"] for b in books]
    log(f"ASINs to check: {asins}", "Harvester")

    # Scrape live BSR for each
    live_bsr = scrape_kdp_dashboard_bsr(asins)

    # If ALL BSR scrapes failed, log warning — data will use historical values
    if not live_bsr and asins:
        log("WARNING: All BSR scrapes failed — using historical LEARNING.md data only", "Harvester")

    today = datetime.now().strftime("%Y-%m-%d")
    ts    = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    # Build update entries
    updates = []
    for book in books:
        asin = book.get("asin", "")
        bsr_info = live_bsr.get(asin, {})
        entry = {
            "title":          book.get("title", ""),
            "asin":           asin,
            "niche":          book.get("niche", ""),
            "units":          book.get("units", 0),
            "kenp":           book.get("kenp", 0),
            "royalty":        book.get("royalty", 0.0),
            "kenp_per_unit":  book.get("kenp_per_unit", 0.0),
            "royalty_per_unit": book.get("royalty_per_unit", 0.0),
            "niche_score":    book.get("niche_score", 0.0),
            "kindle_bsr":     bsr_info.get("kindle_bsr"),
            "review_count":   bsr_info.get("review_count", 0),
            "rating":         bsr_info.get("rating"),
        }
        updates.append(entry)

    # Build LEARNING.md harvest entry
    rows = "\n".join(
        f"| {u['title'][:45]:<45} | {u['asin']} | "
        f"{'#' + str(u['kindle_bsr']) if u['kindle_bsr'] else 'n/a':>12} | "
        f"{u['review_count']:>7} | "
        f"${u['royalty_per_unit']:.2f} | "
        f"{u['kenp_per_unit']:.0f} |"
        for u in updates
    )

    md_entry = f"""
---

## [{today}] Harvester: Live Performance Snapshot
<!-- AUTO-GENERATED: {ts} -->

| Title | ASIN | Kindle BSR | Reviews | $/unit | KENP/unit |
|-------|------|-----------|---------|--------|-----------|
{rows}

**Catalog health:**
- Books tracked: {len(updates)}
- Books with live BSR data: {len([u for u in updates if u.get('kindle_bsr')])}
- Total catalog royalties (historical): ${sum(u['royalty'] for u in updates):,.2f}
- Best performer: {max(updates, key=lambda x: x['royalty'], default={'title':'none'})['title'][:50]}
"""

    if dry_run:
        log("DRY RUN — would append to LEARNING.md:", "Harvester")
        print(md_entry)
    else:
        with open(LEARNING_MD, "a") as f:
            f.write(md_entry)
        log(f"Appended harvest entry to LEARNING.md", "Harvester")

    return {"books": len(updates), "live_bsr": len(live_bsr), "updates": updates}


def rotate_learning_md(max_books: int = 20, dry_run: bool = False):
    """Keep only the last max_books original entries in LEARNING.md.
    
    Older entries are archived to LEARNING_archive.md. Harvester snapshots
    (dated performance tables) are always kept — only original book entries
    are rotated. This prevents the file from growing unbounded and hitting
    the planner's 8000-char cap.
    """
    if not LEARNING_MD.exists():
        return
    
    content = LEARNING_MD.read_text(encoding="utf-8", errors="replace")
    
    # Split into book entries (## [date] Book: ...) and harvester snapshots (## [date] Harvester: ...)
    # Keep all harvester snapshots, only rotate book entries
    book_entries = re.split(r"(?=^## \[\d{4}-\d{2}-\d{2}\] Book:)", content, flags=re.MULTILINE)
    
    # First element is the header/preamble
    preamble = book_entries[0] if book_entries else ""
    entries = book_entries[1:] if len(book_entries) > 1 else []
    
    if len(entries) <= max_books:
        log(f"LEARNING.md has {len(entries)} book entries — no rotation needed", "Harvester")
        return
    
    keep = entries[-max_books:]
    archive = entries[:-max_books]
    
    if dry_run:
        log(f"DRY RUN — would archive {len(archive)} old entries, keep {len(keep)}", "Harvester")
        return
    
    # Write archive file
    archive_path = LEARNING_MD.with_suffix(".archive.md")
    with open(archive_path, "a", encoding="utf-8") as f:
        for entry in archive:
            f.write(entry)
    log(f"Archived {len(archive)} old entries to {archive_path.name}", "Harvester")
    
    # Rewrite LEARNING.md with preamble + kept entries
    new_content = preamble + "".join(keep)
    LEARNING_MD.write_text(new_content, encoding="utf-8")
    log(f"LEARNING.md rotated: {len(entries)} → {len(keep)} book entries", "Harvester")


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 2: PATTERN ANALYZER
# ══════════════════════════════════════════════════════════════════════════════

def parse_researcher_entries() -> list[dict]:
    """Parse all Researcher niche analysis entries from LEARNING.md."""
    if not LEARNING_MD.exists():
        return []

    text = LEARNING_MD.read_text(encoding="utf-8", errors="replace")
    entries = []

    for block in re.split(r"\n---\n", text):
        if "Researcher: Niche Analysis" not in block:
            continue

        entry = {}

        # Date + niche
        header_m = re.search(r"\[(\d{4}-\d{2}-\d{2})\] Researcher: Niche Analysis — (.+)", block)
        if header_m:
            entry["date"]  = header_m.group(1)
            entry["niche"] = header_m.group(2).strip()

        # Market score
        score_m = re.search(r"Market Score:\s*([\d\.]+)/10", block)
        if score_m:
            try:
                entry["market_score"] = float(score_m.group(1))
            except ValueError:
                pass

        # BSR
        bsr_m = re.search(r"Best Kindle BSR\s*\|\s*#([\d,]+)", block)
        if bsr_m:
            try:
                entry["best_bsr"] = int(bsr_m.group(1).replace(",", ""))
            except ValueError:
                pass

        # Avg price
        price_m = re.search(r"Avg Price\s*\|\s*\$([\d\.]+)", block)
        if price_m:
            try:
                entry["avg_price"] = float(price_m.group(1))
            except ValueError:
                pass

        if entry.get("niche") and entry.get("market_score") is not None:
            entries.append(entry)

    return entries


def analyze_patterns(harvest_data: dict, dry_run: bool = False) -> dict:
    """
    Module 2: Cross-reference catalog performance with research scores.
    Identifies what's working, what's not, updates scoring weights.
    Writes patterns.json.
    """
    section("Module 2: Pattern Analyzer")

    books    = parse_learning_md_books()
    research = parse_researcher_entries()

    if not books:
        log("No books to analyze — skipping", "Analyzer")
        return {}

    # ── Niche performance grouping ────────────────────────────────────────────
    niche_stats: dict[str, dict] = defaultdict(lambda: {
        "books": [], "total_royalty": 0.0, "total_units": 0,
        "total_kenp": 0, "avg_kenp_per_unit": 0.0,
        "avg_royalty_per_unit": 0.0, "research_scores": [],
    })

    for book in books:
        niche = book.get("niche", "unknown")
        ns    = niche_stats[niche]
        ns["books"].append(book.get("title", ""))
        ns["total_royalty"]  += book.get("royalty", 0.0)
        ns["total_units"]    += book.get("units", 0)
        ns["total_kenp"]     += book.get("kenp", 0)
        if book.get("niche_score"):
            ns["research_scores"].append(book["niche_score"])

    # Compute derived stats per niche
    niche_performance = {}
    for niche, ns in niche_stats.items():
        total_units = ns["total_units"] or 1
        niche_performance[niche] = {
            "book_count":          len(ns["books"]),
            "total_royalty":       round(ns["total_royalty"], 2),
            "total_units":         ns["total_units"],
            "avg_royalty_per_unit": round(ns["total_royalty"] / total_units, 2),
            "avg_kenp_per_unit":   round(ns["total_kenp"] / total_units, 1),
            "avg_research_score":  round(
                sum(ns["research_scores"]) / len(ns["research_scores"]), 2
            ) if ns["research_scores"] else None,
            "titles": ns["books"],
        }

    # ── Key patterns ──────────────────────────────────────────────────────────
    patterns = {}

    # Best niche by total royalty
    if niche_performance:
        best_niche = max(niche_performance, key=lambda n: niche_performance[n]["total_royalty"])
        patterns["best_niche_by_revenue"] = best_niche
        patterns["best_niche_royalty"]    = niche_performance[best_niche]["total_royalty"]

    # Best KENP engagement niche (reader engagement)
    best_kenp_niche = max(
        niche_performance,
        key=lambda n: niche_performance[n]["avg_kenp_per_unit"],
        default=None
    )
    if best_kenp_niche:
        patterns["best_kenp_engagement_niche"] = best_kenp_niche
        patterns["best_kenp_per_unit"] = niche_performance[best_kenp_niche]["avg_kenp_per_unit"]

    # Research score accuracy: compare predicted score vs actual royalty/unit
    score_royalty_pairs = [
        (b.get("niche_score", 0), b.get("royalty_per_unit", 0))
        for b in books if b.get("niche_score") and b.get("units", 0) > 0
    ]
    if score_royalty_pairs:
        # Simple correlation direction: are higher scores producing higher royalties?
        high_score  = [r for s, r in score_royalty_pairs if s >= 7.0]
        low_score   = [r for s, r in score_royalty_pairs if s < 5.0]
        patterns["high_score_avg_royalty"] = round(
            sum(high_score) / len(high_score), 2) if high_score else None
        patterns["low_score_avg_royalty"]  = round(
            sum(low_score) / len(low_score), 2) if low_score else None

        # Calibration: if low-score books are outperforming, our scorer is miscalibrated
        if high_score and low_score:
            if patterns["low_score_avg_royalty"] > patterns["high_score_avg_royalty"]:
                patterns["scorer_calibration_warning"] = (
                    "Low-scored niches are outperforming high-scored ones. "
                    "BSR weight may be too high or review-count signal is weak."
                )

    # KENP signal: books with >30 KENP/unit are genuinely engaging readers
    engaging_books = [b for b in books if b.get("kenp_per_unit", 0) > 30]
    thin_books     = [b for b in books if 0 < b.get("kenp_per_unit", 0) <= 10]
    patterns["engaging_book_count"] = len(engaging_books)
    patterns["thin_engagement_count"] = len(thin_books)
    if engaging_books:
        patterns["engaging_book_niches"] = list({b.get("niche") for b in engaging_books})
    if thin_books:
        patterns["thin_engagement_titles"] = [b.get("title", "") for b in thin_books]

    # Price signal: optimal price point
    prices_by_performance = sorted(
        [(b.get("price", 4.99), b.get("royalty_per_unit", 0))
         for b in books if b.get("units", 0) > 0],
        key=lambda x: x[1], reverse=True
    )
    if prices_by_performance:
        patterns["optimal_price_point"] = prices_by_performance[0][0]

    # ── Scoring weight recommendations ────────────────────────────────────────
    # Based on catalog evidence, adjust the researcher's scoring weights
    weight_recommendations = {
        "bsr_weight":         0.40,  # default
        "demand_weight":      0.30,
        "price_weight":       0.20,
        "competition_weight": 0.10,
    }
    if patterns.get("scorer_calibration_warning"):
        # BSR proxy (subcategory ×10) may be inflating demand signal — reduce weight
        weight_recommendations["bsr_weight"]    = 0.30
        weight_recommendations["demand_weight"] = 0.40
        log("Adjusting scoring weights: reducing BSR weight due to calibration mismatch", "Analyzer")

    # ── Chapter quality signals ───────────────────────────────────────────────
    quality_signals = {}

    # KENP/unit < 10 on a book with >10 units suggests the content isn't engaging readers
    if thin_books:
        quality_signals["low_engagement_warning"] = (
            f"{len(thin_books)} book(s) have very low KENP/unit (<10). "
            f"Content may be too generic or not delivering on the promise."
        )

    # Recurring validation issues from audit log
    if AUDIT_LOG.exists():
        try:
            audit_data = json.loads(AUDIT_LOG.read_text())
            all_issues = []
            for entry in audit_data.get("retrospectives", []):
                all_issues.extend(entry.get("content_issues", []))
            if all_issues:
                # Count recurring issues
                issue_counts = defaultdict(int)
                for issue in all_issues:
                    issue_counts[issue] += 1
                top_issues = sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:3]
                quality_signals["recurring_content_issues"] = [i for i, _ in top_issues]
        except Exception:
            pass

    patterns["quality_signals"] = quality_signals

    # ── Final patterns object ─────────────────────────────────────────────────
    full_patterns = {
        "generated_at":        datetime.now().isoformat(),
        "catalog_size":        len(books),
        "niches_tracked":      len(niche_performance),
        "niche_performance":   niche_performance,
        "patterns":            patterns,
        "weight_recommendations": weight_recommendations,
        "quality_signals":     quality_signals,
    }

    log(f"Patterns extracted from {len(books)} books across {len(niche_performance)} niches", "Analyzer")
    if patterns.get("best_niche_by_revenue"):
        log(f"Best niche by revenue: {patterns['best_niche_by_revenue']} (${patterns['best_niche_royalty']:,.2f})", "Analyzer")
    if patterns.get("scorer_calibration_warning"):
        log(f"⚠️  Calibration: {patterns['scorer_calibration_warning'][:80]}", "Analyzer")

    if dry_run:
        log("DRY RUN — would write patterns.json:", "Analyzer")
        print(json.dumps(full_patterns, indent=2)[:2000])
    else:
        PATTERNS_JSON.write_text(json.dumps(full_patterns, indent=2))
        log(f"Patterns written to {PATTERNS_JSON}", "Analyzer")

    return full_patterns


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 3: PROMPT REFINER
# ══════════════════════════════════════════════════════════════════════════════

def build_prompt_overrides(patterns: dict) -> dict:
    """
    Given pattern analysis, determine what prompt improvements to make.
    Returns overrides dict that Chapter-Builder and Outliner will read.
    """
    overrides = {
        "generated_at":           datetime.now().isoformat(),
        "chapter_builder_additions": [],
        "outliner_additions": [],
        "niche_specific_guidance": {},
        "scoring_weight_overrides": {},
        "quality_rules": [],
    }

    p = patterns.get("patterns", {})
    q = patterns.get("quality_signals", {})

    # ── Chapter-Builder prompt additions ──────────────────────────────────────

    # Low KENP engagement → content is too generic
    if q.get("low_engagement_warning"):
        overrides["chapter_builder_additions"].append(
            "ENGAGEMENT REQUIREMENT: Readers must feel compelled to keep reading. "
            "Each section must answer a question the reader is actively asking. "
            "Never explain what you're about to explain — just explain it. "
            "Every chapter must end with a specific, actionable next step the reader can take today."
        )

    # Recurring content issues from audit
    recurring = q.get("recurring_content_issues", [])
    for issue in recurring:
        if "generic" in issue.lower():
            overrides["chapter_builder_additions"].append(
                "SPECIFICITY: Replace all generic advice with specific named examples. "
                "If you find yourself writing 'many people', 'studies show', or 'experts say' "
                "without a specific source — stop and add the specific person, study, or number."
            )
        if "short" in issue.lower() or "word count" in issue.lower():
            overrides["chapter_builder_additions"].append(
                "DEPTH: This niche rewards comprehensive coverage. "
                "Each main point needs: a clear explanation, a concrete example, "
                "and a practical application. Do not skip any of these three."
            )

    # ── Niche-specific guidance ───────────────────────────────────────────────

    niche_perf = patterns.get("niche_performance", {})
    engaging_niches = p.get("engaging_book_niches", [])

    for niche, perf in niche_perf.items():
        guidance = {}

        # High KENP niches: readers finish these — sustain the narrative
        if niche in engaging_niches:
            guidance["strength"] = (
                f"Readers are engaged with {niche} content (high KENP/unit). "
                f"Maintain narrative momentum. Use cliffhangers between sections. "
                f"Make each chapter feel like it's building toward something."
            )

        # Low royalty despite high research score: topic may be resonating but conversion is weak
        if perf.get("avg_royalty_per_unit", 0) < 2.0 and perf.get("book_count", 0) > 1:
            guidance["improvement"] = (
                f"Books in {niche} have lower-than-expected conversion. "
                f"Focus on stronger value proposition in chapters 1 and 2 — "
                f"readers need to feel the promise of value immediately. "
                f"Hook the reader with a specific outcome by page 5."
            )

        if guidance:
            overrides["niche_specific_guidance"][niche] = guidance

    # ── Scoring weight overrides for Researcher ───────────────────────────────
    weights = patterns.get("weight_recommendations", {})
    if weights:
        overrides["scoring_weight_overrides"] = weights

    # ── Outliner additions ────────────────────────────────────────────────────

    optimal_price = p.get("optimal_price_point")
    if optimal_price:
        overrides["outliner_additions"].append(
            f"DEPTH CALIBRATION: Catalog data shows ${optimal_price:.2f} is the optimal price point. "
            f"Structure outlines for 10-12 chapters of substantive content that justifies this price. "
            f"Each chapter should deliver a complete, standalone value unit."
        )

    if p.get("best_kenp_engagement_niche"):
        best = p["best_kenp_engagement_niche"]
        overrides["outliner_additions"].append(
            f"ENGAGEMENT MODEL: '{best}' books show the highest reader completion. "
            f"Study the structure of successful {best} titles: they typically use a "
            f"problem-solution-implementation pattern with strong chapter-ending hooks."
        )

    # ── Quality rules (applied at validation) ────────────────────────────────
    overrides["quality_rules"] = [
        "Each chapter must have a concrete, specific example (not hypothetical)",
        "Chapter conclusions must include one actionable takeaway",
        "No chapter may use the word 'simply' or 'just' without a specific process",
        "Minimum of 3 H2 headings per chapter to ensure structure",
    ]

    return overrides


def refine_prompts(patterns: dict, dry_run: bool = False) -> dict:
    """
    Module 3: Update prompt_overrides.json based on pattern analysis.
    Chapter-Builder and Outliner check this file and apply additions.
    """
    section("Module 3: Prompt Refiner")

    if not patterns:
        if PATTERNS_JSON.exists():
            patterns = json.loads(PATTERNS_JSON.read_text())
        else:
            log("No patterns available — run --analyze first", "Refiner")
            return {}

    overrides = build_prompt_overrides(patterns)

    additions = overrides.get("chapter_builder_additions", [])
    niche_guidance = overrides.get("niche_specific_guidance", {})
    log(f"Generated {len(additions)} chapter prompt additions", "Refiner")
    log(f"Niche-specific guidance for {len(niche_guidance)} niches", "Refiner")

    for a in additions:
        log(f"  + {a[:80]}...", "Refiner")

    if dry_run:
        log("DRY RUN — would write prompt_overrides.json:", "Refiner")
        print(json.dumps(overrides, indent=2)[:2000])
    else:
        PROMPT_OVERRIDES.write_text(json.dumps(overrides, indent=2))
        log(f"Prompt overrides written to {PROMPT_OVERRIDES}", "Refiner")

        # Patch chapter_builder.py to load overrides at startup
        _patch_chapter_builder_for_overrides()

    return overrides


def _patch_chapter_builder_for_overrides():
    """
    Add override-loading code to chapter_builder.py if not already present.
    The patch is minimal and non-destructive — it appends to SYSTEM_PROMPT.
    """
    if not CHAPTER_BUILDER_PY.exists():
        log("chapter_builder.py not found — skipping patch", "Refiner")
        return

    content = CHAPTER_BUILDER_PY.read_text()

    # Already patched?
    if "prompt_overrides.json" in content:
        log("chapter_builder.py already loads overrides — skipping patch", "Refiner")
        return

    # Create timestamped backup before any modification
    from datetime import datetime as _dt
    backup = CHAPTER_BUILDER_PY.with_suffix(f".py.bak.{_dt.now().strftime('%Y%m%d_%H%M%S')}")
    import shutil
    shutil.copy2(CHAPTER_BUILDER_PY, backup)
    log(f"Backed up chapter_builder.py to {backup.name}", "Refiner")

    # Find where SYSTEM_PROMPT is defined and inject override loading after it
    override_loader = '''

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
        extra = "\\n\\nFACTORY LEARNING (apply these insights from published catalog):\\n"
        for a in additions:
            extra += f"- {a}\\n"
        if rules:
            extra += "\\nQUALITY GATES (each chapter must pass):\\n"
            for r in rules:
                extra += f"- {r}\\n"
        return extra
    except Exception:
        return ""

SYSTEM_PROMPT = SYSTEM_PROMPT + _load_prompt_overrides()
'''

    # Inject after the SYSTEM_PROMPT definition
    marker = 'Just write the chapter."""'
    if marker in content:
        patched = content.replace(marker, marker + override_loader, 1)
        CHAPTER_BUILDER_PY.write_text(patched)
        log("chapter_builder.py patched to load prompt overrides", "Refiner")
    else:
        log("Could not find patch point in chapter_builder.py — manual update needed", "Refiner")


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 4: TOPIC SCOUT
# ══════════════════════════════════════════════════════════════════════════════

def get_adjacent_topics(catalog_niches: list[str]) -> list[str]:
    """
    Generate adjacent topic candidates based on catalog niches.
    Adjacency map: what works near what we've already published.
    """
    adjacency = {
        "productivity": [
            "deep work strategies", "async communication for remote teams",
            "morning routines for high performers", "decision fatigue management",
            "digital minimalism", "focus rituals for entrepreneurs",
            "time blocking for parents", "productivity for ADHD adults",
        ],
        "health": [
            "longevity habits", "anti-inflammatory eating on a budget",
            "mental health basics without therapy", "chronic pain management at home",
            "hormonal health for women over 40", "sleep optimization for shift workers",
            "gut health for athletes", "fasting simplified",
        ],
        "tech-security": [
            "password security for families", "smart home privacy",
            "identity theft recovery", "online privacy for seniors",
            "vpn setup guide", "two-factor authentication guide",
            "email security basics", "social media privacy settings",
        ],
        "parenting": [
            "screen time management for kids", "raising emotionally intelligent children",
            "homework help strategies", "teen mental health guide for parents",
            "co-parenting after divorce", "parenting highly sensitive children",
            "reading habits for kids", "kids and money basics",
        ],
        "business": [
            "solopreneur systems", "freelancing pricing strategy",
            "email marketing for small business", "passive income side hustles",
            "bookkeeping basics for entrepreneurs", "client communication templates",
            "remote team management", "building a consulting practice",
        ],
        "self-help": [
            "boundary setting for people pleasers", "anxiety management without medication",
            "confidence building for introverts", "habit stacking simplified",
            "emotional regulation toolkit", "self-compassion practices",
            "overcoming imposter syndrome", "building resilience after failure",
        ],
    }

    candidates = []
    for niche in catalog_niches:
        candidates.extend(adjacency.get(niche, []))

    # Also add cross-niche opportunities (trending intersections)
    cross_niche = [
        "ai tools for small business owners",
        "walking for mental health",
        "digital detox for productivity",
        "sleep and athletic performance",
        "financial wellness for chronic illness",
        "remote work ergonomics",
    ]
    candidates.extend(cross_niche)

    return list(dict.fromkeys(candidates))  # deduplicate preserving order


def scrape_movers_and_shakers() -> list[dict]:
    """
    Scrape Amazon Kindle Movers & Shakers for trending topics.
    These are books with the biggest sales rank gains in 24 hours — early demand signal.
    """
    movers_url = "https://www.amazon.com/gp/movers-and-shakers/digital-text/ref=zg_bsms_digital-text"

    if not FIRECRAWL_KEY:
        return []

    try:
        resp = requests.post(
            "https://api.firecrawl.dev/v1/scrape",
            headers={"Authorization": f"Bearer {FIRECRAWL_KEY}"},
            json={
                "url": movers_url,
                "formats": ["markdown"],
                "onlyMainContent": True,
                "timeout": 30000,
            },
            timeout=40,
        )
        if resp.status_code != 200:
            return []

        raw = resp.json().get("data", {}).get("markdown", "")

        # Extract titles and rank changes
        entries = []
        rank_change_pat = re.compile(r"up\s+(\d+)%|down\s+(\d+)%|\+(\d+)%|-(\d+)%", re.IGNORECASE)

        # Image alt-text titles
        title_pat = re.compile(
            r'\[!\[([^\]]{8,120})\]\(https://[^)]+\)\]\(https://www\.amazon\.com[^)]+\)'
        )
        for m in title_pat.finditer(raw):
            title = m.group(1).strip()
            if not any(noise in title.lower() for noise in ["amazon", "sign in", "cart"]):
                entries.append({"title": title, "source": "movers_and_shakers"})

        return entries[:20]
    except Exception as e:
        log(f"Movers & Shakers scrape failed: {e}", "Scout")
        return []


def get_google_trends(keywords: list[str]) -> dict[str, float]:
    """
    Check Google Trends interest for a list of keywords.
    Returns dict: keyword → interest score (0-100).
    """
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl="en-US", tz=360)
        scores = {}
        # Process in batches of 5 (pytrends limit)
        for i in range(0, min(len(keywords), 15), 5):
            batch = keywords[i:i+5]
            pytrends.build_payload(batch, timeframe="today 3-m", geo="US")
            interest = pytrends.interest_over_time()
            if not interest.empty:
                for kw in batch:
                    if kw in interest.columns:
                        scores[kw] = float(interest[kw].mean())
            time.sleep(1.5)  # rate limit
        return scores
    except Exception as e:
        log(f"Google Trends unavailable: {e}", "Scout")
        return {}


def score_candidate_topics(candidates: list[str], patterns: dict,
                            trend_scores: dict) -> list[dict]:
    """
    Score each candidate topic using:
    - Google Trends interest (if available)
    - Adjacency to proven successful niches
    - Pattern data (which niches are most profitable)
    """
    p = patterns.get("patterns", {})
    niche_perf = patterns.get("niche_performance", {})
    best_niche  = p.get("best_niche_by_revenue", "")
    best_kenp   = p.get("best_kenp_engagement_niche", "")

    # Niche keyword mapping for scoring adjacency
    niche_keywords = {
        "productivity": ["productivity", "time", "habits", "focus", "efficiency", "work"],
        "health":       ["health", "gut", "sleep", "diet", "fitness", "nutrition", "wellness"],
        "tech-security":["security", "privacy", "cyber", "digital", "network", "vpn"],
        "parenting":    ["parent", "child", "kid", "family", "teen", "school"],
        "business":     ["business", "freelance", "income", "entrepreneur", "client"],
        "self-help":    ["anxiety", "confidence", "habit", "mindset", "emotion", "stress"],
    }

    scored = []
    for topic in candidates:
        topic_lower = topic.lower()
        score = 50.0  # base score

        # Google Trends boost
        trend_score = trend_scores.get(topic, 0)
        score += trend_score * 0.3

        # Adjacency to best-performing niche
        if best_niche in niche_keywords:
            if any(kw in topic_lower for kw in niche_keywords[best_niche]):
                score += 20
                bonus_reason = f"adjacent to best niche ({best_niche})"
            else:
                bonus_reason = ""
        else:
            bonus_reason = ""

        # Adjacency to high-KENP niche (engaged readers)
        if best_kenp and best_kenp in niche_keywords:
            if any(kw in topic_lower for kw in niche_keywords[best_kenp]):
                score += 10

        # Already published? Penalize (avoid duplicate niches)
        published_topics = []
        for niche, perf in niche_perf.items():
            published_topics.extend(perf.get("titles", []))
        if any(topic_lower in t.lower() or t.lower() in topic_lower
               for t in published_topics):
            score -= 30

        # Specificity bonus: specific audiences outperform generic (from catalog patterns)
        specificity_markers = [
            "for ", "guide to ", "system for ", "method for ",
            "strategy for ", "without ", "simplified"
        ]
        if any(m in topic_lower for m in specificity_markers):
            score += 15

        scored.append({
            "topic":         topic,
            "score":         round(score, 1),
            "trend_score":   trend_score,
            "bonus_reason":  bonus_reason,
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def scout_topics(patterns: dict, dry_run: bool = False) -> list[dict]:
    """
    Module 4: Proactively find high-potential next topics.
    Writes topic_candidates.md and sends weekly Telegram brief.
    """
    section("Module 4: Topic Scout")

    if not patterns:
        if PATTERNS_JSON.exists():
            patterns = json.loads(PATTERNS_JSON.read_text())
        else:
            log("No patterns — run --analyze first", "Scout")
            patterns = {}

    # What niches are we already in?
    catalog_niches = list(patterns.get("niche_performance", {}).keys())
    log(f"Catalog niches: {catalog_niches}", "Scout")

    # Generate adjacent topic candidates
    candidates = get_adjacent_topics(catalog_niches)
    log(f"Generated {len(candidates)} adjacent topic candidates", "Scout")

    # Check Movers & Shakers for trending topics
    movers = scrape_movers_and_shakers()
    if movers:
        log(f"Found {len(movers)} trending titles from Movers & Shakers", "Scout")
        # Extract keywords from trending titles for our candidate list
        for m in movers[:10]:
            title = m["title"].lower()
            # Add as a research candidate if it looks nonfiction
            if not any(noise in title for noise in ["novel", "romance", "fantasy", "fiction", "manga"]):
                candidates.insert(0, m["title"])

    # Google Trends check on top candidates
    top_candidates = candidates[:15]
    log(f"Checking Google Trends for {len(top_candidates)} candidates...", "Scout")
    trend_scores = get_google_trends(top_candidates)
    if trend_scores:
        log(f"Got trend data for {len(trend_scores)} topics", "Scout")

    # Score all candidates
    scored = score_candidate_topics(candidates, patterns, trend_scores)
    top_5 = scored[:5]

    today = datetime.now().strftime("%Y-%m-%d")
    ts    = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    # Build topic_candidates.md
    rows = "\n".join(
        f"| {i+1} | {t['topic']:<55} | {t['score']:>5.1f} | "
        f"{t['trend_score']:>5.1f} | {t['bonus_reason'] or '—'} |"
        for i, t in enumerate(top_5)
    )

    md_content = f"""# Topic Scout Report — {today}
<!-- AUTO-GENERATED: {ts} -->

## Top 5 Recommended Topics This Week

| # | Topic | Score | Trend | Reason |
|---|-------|-------|-------|--------|
{rows}

## How to Use This Report

1. Pick a topic from the table above
2. Run researcher: `python3 researcher.py --niche "<topic>"`
3. If score ≥ 6.0, run outliner to start the book

## All Candidates Scored ({len(scored)} total)

"""
    for t in scored[:20]:
        md_content += f"- **{t['topic']}** — Score: {t['score']:.1f}"
        if t.get("bonus_reason"):
            md_content += f" ({t['bonus_reason']})"
        md_content += "\n"

    md_content += f"\n_Generated {today} by self-improvement agent_\n"

    if dry_run:
        log("DRY RUN — would write topic_candidates.md:", "Scout")
        print(md_content[:2000])
    else:
        TOPIC_CANDIDATES.write_text(md_content)
        log(f"Topic candidates written to {TOPIC_CANDIDATES}", "Scout")

    # Telegram weekly brief
    top3_lines = "\n".join(
        f"{i+1}. *{t['topic']}* (score: {t['score']:.0f})"
        for i, t in enumerate(top_5[:3])
    )
    msg = (
        f"📡 *Weekly Topic Brief — {today}*\n\n"
        f"Top 3 candidates for your next book:\n\n"
        f"{top3_lines}\n\n"
        f"Full report: `{TOPIC_CANDIDATES}`\n"
        f"To research: `python3 researcher.py --niche \"<topic>\"`"
    )
    if not dry_run:
        notify_telegram(msg)
        log("Telegram weekly brief sent", "Scout")

    return top_5


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 5: QUALITY AUDITOR
# ══════════════════════════════════════════════════════════════════════════════

def audit_published_books(harvest_data: dict, dry_run: bool = False) -> dict:
    """
    Module 5: Retrospective analysis per published book.
    Compares predicted research score vs actual performance.
    Flags specific quality issues that need addressing.
    Writes audit_log.json.
    """
    section("Module 5: Quality Auditor")

    books = parse_learning_md_books()
    if not books:
        log("No books to audit", "Auditor")
        return {}

    retrospectives = []

    for book in books:
        # Audit all books that have an ASIN (even zero-unit books — flag missing data)
        if not book.get("asin"):
            continue

        retro = {
            "title":        book.get("title", ""),
            "asin":         book.get("asin", ""),
            "niche":        book.get("niche", ""),
            "audited_at":   datetime.now().isoformat(),
            "flags":        [],
            "content_issues": [],
            "diagnosis":    "",
            "recommended_action": "",
        }

        royalty_per_unit = book.get("royalty_per_unit", 0)
        kenp_per_unit    = book.get("kenp_per_unit", 0)
        niche_score      = book.get("niche_score", 0)
        units            = book.get("units", 0)

        # ── Flag: predicted high but performing low ───────────────────────────
        if niche_score >= 7.0 and royalty_per_unit < 2.0 and units > 5:
            retro["flags"].append("overestimated_demand")
            retro["diagnosis"] = (
                f"Research score was {niche_score}/10 but royalty/unit is ${royalty_per_unit:.2f}. "
                f"Niche may be more competitive than BSR suggested, or title/cover is not converting."
            )
            retro["recommended_action"] = (
                "Run A/B price test. Review cover against top competitors. "
                "Consider subtitle optimization for Amazon SEO."
            )

        # ── Flag: low KENP engagement (readers not finishing) ─────────────────
        if units >= 5 and kenp_per_unit < 15:
            retro["flags"].append("low_reader_engagement")
            retro["content_issues"].append("low KENP per unit")
            retro["diagnosis"] = (
                retro.get("diagnosis", "") +
                f" KENP/unit of {kenp_per_unit:.1f} suggests readers are not completing the book. "
                f"Chapter 1 may not be delivering on the promise, or content depth is insufficient."
            )
            retro["recommended_action"] = (
                retro.get("recommended_action", "") +
                " Review Chapter 1 for a strong hook. "
                "Ensure each chapter ends with a reason to continue to the next."
            )

        # ── Flag: strong performer — what can we replicate? ───────────────────
        if royalty_per_unit >= 3.00 and kenp_per_unit >= 30:
            retro["flags"].append("top_performer")
            retro["diagnosis"] = (
                f"Strong performer: ${royalty_per_unit:.2f}/unit, {kenp_per_unit:.0f} KENP/unit. "
                f"This title's niche ({book.get('niche','')}) and approach should be replicated."
            )
            retro["recommended_action"] = (
                f"Write adjacent title in '{book.get('niche','')}' niche. "
                f"Study this book's structure for outliner improvements."
            )

        # ── Flag: zero KENP (KU subscribers aren't finding it) ───────────────
        if units >= 3 and kenp_per_unit == 0:
            retro["flags"].append("kdp_select_not_working")
            retro["content_issues"].append("zero KENP reads despite sales")
            retro["diagnosis"] = (
                retro.get("diagnosis", "") +
                " Zero KENP despite sales suggests this book is not being surfaced to KU subscribers. "
                "Amazon may not be categorizing it correctly for KU recommendations."
            )
            retro["recommended_action"] = (
                retro.get("recommended_action", "") +
                " Re-check category assignments in KDP. "
                "Consider a Kindle Countdown Deal to signal activity to the algorithm."
            )

        retrospectives.append(retro)

    # Summarize
    flags_count = defaultdict(int)
    for r in retrospectives:
        for f in r.get("flags", []):
            flags_count[f] += 1

    audit_data = {
        "generated_at":   datetime.now().isoformat(),
        "books_audited":  len(retrospectives),
        "flags_summary":  dict(flags_count),
        "top_performers": [r["title"] for r in retrospectives if "top_performer" in r.get("flags", [])],
        "needs_attention":[r["title"] for r in retrospectives if "overestimated_demand" in r.get("flags", []) or "low_reader_engagement" in r.get("flags", [])],
        "retrospectives": retrospectives,
    }

    log(f"Audited {len(retrospectives)} books", "Auditor")
    for flag, count in flags_count.items():
        log(f"  {flag}: {count} book(s)", "Auditor")

    if flags_count.get("top_performers"):
        log(f"Top performers: {audit_data['top_performers']}", "Auditor")
    if flags_count.get("low_reader_engagement"):
        log(f"⚠️  Low engagement books: {audit_data['needs_attention']}", "Auditor")

    if dry_run:
        log("DRY RUN — would write audit_log.json", "Auditor")
        print(json.dumps(audit_data, indent=2)[:2000])
    else:
        AUDIT_LOG.write_text(json.dumps(audit_data, indent=2))
        log(f"Audit log written to {AUDIT_LOG}", "Auditor")

    # Telegram notification for books needing attention
    if not dry_run and audit_data["needs_attention"]:
        msg = (
            f"📊 *Quality Audit Complete*\n\n"
            f"Books audited: {len(retrospectives)}\n"
            f"Top performers: {', '.join(audit_data['top_performers'][:2]) or 'none yet'}\n"
            f"Need attention: {', '.join(audit_data['needs_attention'][:2])}\n\n"
            f"Full audit: `{AUDIT_LOG}`"
        )
        notify_telegram(msg)

    return audit_data


# ══════════════════════════════════════════════════════════════════════════════
# REPORT GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

def generate_report(harvest_data: dict, patterns: dict,
                    overrides: dict, scout_results: list,
                    audit_data: dict) -> str:
    """Generate a human-readable markdown improvement report."""
    today = datetime.now().strftime("%Y-%m-%d")
    ts    = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    books = parse_learning_md_books()
    total_royalty = sum(b.get("royalty", 0) for b in books)
    total_units   = sum(b.get("units", 0) for b in books)

    p = patterns.get("patterns", {}) if patterns else {}
    niche_perf = patterns.get("niche_performance", {}) if patterns else {}

    # Best performing niches table
    niche_rows = ""
    for niche, perf in sorted(
        niche_perf.items(),
        key=lambda x: x[1].get("total_royalty", 0),
        reverse=True
    ):
        niche_rows += (
            f"| {niche:<20} | {perf['book_count']:>5} | "
            f"${perf['total_royalty']:>10,.2f} | "
            f"{perf['avg_kenp_per_unit']:>12.1f} | "
            f"${perf['avg_royalty_per_unit']:>8.2f} |\n"
        )

    # Top topic candidates
    scout_rows = ""
    for i, t in enumerate(scout_results[:3] if scout_results else []):
        scout_rows += f"{i+1}. **{t['topic']}** — Score: {t['score']:.0f}/100\n"

    # Prompt changes
    additions = overrides.get("chapter_builder_additions", []) if overrides else []
    additions_text = "\n".join(f"- {a[:100]}" for a in additions) or "_No changes needed_"

    report = f"""# Ebook Factory — Self-Improvement Report
<!-- AUTO-GENERATED: {ts} -->

## Catalog Health — {today}

| Metric | Value |
|--------|-------|
| Books published | {len(books)} |
| Total royalties | ${total_royalty:,.2f} |
| Total units sold | {total_units:,} |
| Best niche | {p.get('best_niche_by_revenue', 'n/a')} |
| Best KENP niche | {p.get('best_kenp_engagement_niche', 'n/a')} |

## Niche Performance

| Niche | Books | Revenue | KENP/unit | $/unit |
|-------|-------|---------|-----------|--------|
{niche_rows or '_No data yet_'}

## Prompt Improvements Applied

{additions_text}

## This Week's Top Topic Recommendations

{scout_rows or '_Run --scout to generate recommendations_'}

## Books Needing Attention

{chr(10).join('- ' + t for t in (audit_data or {}).get('needs_attention', [])) or '_All books performing as expected_'}

## Next Actions

1. Research top topic candidate with `researcher.py`
2. Review any flagged books in KDP dashboard
3. Next full cycle: {(datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')}

---
_Self-improvement agent v1.0 — runs weekly via cron_
"""

    return report


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Ebook Factory Self-Improvement Agent"
    )
    parser.add_argument("--all",            action="store_true", help="Run full improvement cycle")
    parser.add_argument("--harvest",        action="store_true", help="Module 1: scrape performance data")
    parser.add_argument("--analyze",        action="store_true", help="Module 2: analyze patterns")
    parser.add_argument("--refine-prompts", action="store_true", help="Module 3: update prompts")
    parser.add_argument("--scout",          action="store_true", help="Module 4: find next topics")
    parser.add_argument("--audit",          action="store_true", help="Module 5: quality retrospective")
    parser.add_argument("--report",         action="store_true", help="Print improvement report")
    parser.add_argument("--dry-run",        action="store_true", help="Simulate — no writes")
    args = parser.parse_args()

    if not any([args.all, args.harvest, args.analyze,
                args.refine_prompts, args.scout, args.audit, args.report]):
        parser.print_help()
        return

    harvest_data = {}
    patterns     = {}
    overrides    = {}
    scout_results = []
    audit_data   = {}

    run_harvest  = args.all or args.harvest
    run_analyze  = args.all or args.analyze
    run_refine   = args.all or args.refine_prompts
    run_scout    = args.all or args.scout
    run_audit    = args.all or args.audit

    # Load existing patterns if available (for modules that need them)
    if not run_analyze and PATTERNS_JSON.exists():
        try:
            patterns = json.loads(PATTERNS_JSON.read_text())
        except Exception:
            pass

    # ── Module 1: Harvest ─────────────────────────────────────────────────────
    if run_harvest:
        harvest_data = harvest_performance(dry_run=args.dry_run)
        # R2: Rotate LEARNING.md to prevent unbounded growth
        rotate_learning_md(max_books=20, dry_run=args.dry_run)

    # ── Module 2: Analyze ─────────────────────────────────────────────────────
    if run_analyze:
        patterns = analyze_patterns(harvest_data, dry_run=args.dry_run)

    # ── Module 3: Refine Prompts ──────────────────────────────────────────────
    if run_refine:
        overrides = refine_prompts(patterns, dry_run=args.dry_run)

    # ── Module 4: Scout ───────────────────────────────────────────────────────
    if run_scout:
        scout_results = scout_topics(patterns, dry_run=args.dry_run)

    # ── Module 5: Audit ───────────────────────────────────────────────────────
    if run_audit:
        audit_data = audit_published_books(harvest_data, dry_run=args.dry_run)

    # ── Report ────────────────────────────────────────────────────────────────
    if args.report or args.all:
        section("Improvement Report")
        report = generate_report(harvest_data, patterns, overrides, scout_results, audit_data)
        print(report)
        if not args.dry_run:
            IMPROVEMENT_REPORT.write_text(report)
            log(f"Report written to {IMPROVEMENT_REPORT}")

    # ── Full cycle Telegram summary ───────────────────────────────────────────
    if args.all and not args.dry_run:
        top_topic = scout_results[0]["topic"] if scout_results else "n/a"
        books = parse_learning_md_books()
        msg = (
            f"🧠 *Self-Improvement Cycle Complete*\n\n"
            f"Catalog: {len(books)} books\n"
            f"Patterns updated ✅\n"
            f"Prompts refined ✅\n"
            f"Top topic pick: *{top_topic}*\n"
            f"Next cycle: {(datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')}"
        )
        notify_telegram(msg)
        log("Full cycle complete — Telegram summary sent")


if __name__ == "__main__":
    main()
