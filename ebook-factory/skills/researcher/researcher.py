#!/usr/bin/env python3
"""
Ebook Factory — Researcher Agent
=================================
Scrapes Amazon market data for a given niche keyword and appends enriched
research findings to ~/books/factory/LEARNING.md.

Tiered fallback strategy:
  Tier 1 → Firecrawl API (fast, credit-based)
  Tier 2 → Scrapling StealthyFetcher (stealth browser, Cloudflare bypass)
  Tier 3 → Camoufox (anti-detect Firefox, nuclear option for heavy bot guards)

Usage:
  python3 researcher.py --niche "home organization"
  python3 researcher.py --niche "productivity" --max-results 10
  python3 researcher.py --niche "sleep health" --dry-run
  python3 researcher.py --niche "gut health" --tier 2   # force Scrapling
  python3 researcher.py --niche "gut health" --tier 3   # force Camoufox
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

import requests

# ── Paths ─────────────────────────────────────────────────────────────────────

def get_hermes_home() -> Path:
    try:
        from hermes_constants import get_hermes_home as _ghh
        return Path(_ghh())
    except ImportError:
        return Path.home() / ".hermes"

HERMES_HOME   = get_hermes_home()
LEARNING_MD   = Path.home() / "books" / "factory" / "LEARNING.md"
ENV_FILE      = HERMES_HOME / ".env"

# ── Env loading ────────────────────────────────────────────────────────────────

def load_env():
    env = {}
    for path in [ENV_FILE, Path.home() / ".hermes" / ".env"]:
        if path.exists():
            for line in path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    env[k.strip()] = v.strip()
    env.update(os.environ)
    return env

ENV = load_env()
FIRECRAWL_API_KEY = ENV.get("FIRECRAWL_API_KEY", "")
TELEGRAM_BOT_TOKEN = ENV.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = ENV.get("TELEGRAM_CHAT_ID", "")

# ── Logging ────────────────────────────────────────────────────────────────────

def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def log_tier(tier: int, msg: str):
    icons = {1: "🔥", 2: "🕷️", 3: "🦊"}
    names = {1: "Firecrawl", 2: "Scrapling", 3: "Camoufox"}
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{icons.get(tier,'?')} {names.get(tier,'?')}] {msg}", flush=True)

# ── Telegram notification ──────────────────────────────────────────────────────

def notify_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception as e:
        log(f"Telegram notify failed (non-fatal): {e}")

# ── URL builders ───────────────────────────────────────────────────────────────

def amazon_search_url(keyword: str, page: int = 1) -> str:
    q = quote_plus(keyword)
    # Force US store, Kindle Store category, Kindle format filter
    # gl=us&language=en_US ensures we get USD prices
    return (
        f"https://www.amazon.com/s?k={q}+kindle+ebook"
        f"&i=digital-text"
        f"&rh=n%3A133140011%2Cp_n_feature_nine_browse-bin%3A3291437011"
        f"&gl=us&language=en_US"
        f"&page={page}"
    )

def amazon_bestseller_url(keyword: str) -> str:
    # Kindle Store bestsellers search
    q = quote_plus(keyword)
    return f"https://www.amazon.com/s?k={q}&i=digital-text&s=review-rank"

# ── BSR: ASIN extraction + product page BSR fetch ─────────────────────────────

def extract_asins_from_search(raw: str, max_asins: int = 5) -> list[str]:
    """
    Extract top Kindle product ASINs (by search position) from a Firecrawl search page.
    Prefers Kindle eBook ASINs (B0... format) over paperback ISBNs.
    """
    # sr_1_N ranked URLs with ASIN
    asin_pat = re.compile(
        r'https://www\.amazon\.com/[^/\s\)]+/dp/([A-Z0-9]{10})/ref=sr_1_(\d+)'
    )
    seen = set()
    matches = []
    for m in asin_pat.finditer(raw):
        asin, pos = m.group(1), int(m.group(2))
        if asin not in seen:
            seen.add(asin)
            matches.append((asin, pos))

    matches.sort(key=lambda x: x[1])

    # Prefer Kindle ASINs (start with B0) — paperbacks are 10-digit numbers
    kindle_asins = [a for a, _ in matches if a.startswith("B")]
    other_asins  = [a for a, _ in matches if not a.startswith("B")]

    # Return Kindle-first, then others as fallback
    ordered = kindle_asins + other_asins
    return ordered[:max_asins]

def fetch_bsr_for_asin(asin: str, force_tier: int = 0) -> dict:
    """
    Fetch a Kindle product page and extract BSR data.
    Returns dict with kindle_bsr, subcategories list, title, price, rating.
    Cost: 1 Firecrawl credit.
    """
    url = f"https://www.amazon.com/dp/{asin}/"
    # Use product-specific scraper that includes li/ul (needed for BSR list)
    content = firecrawl_scrape_product(url)
    if not content:
        # Fallback to general tiered fetcher
        content, _ = fetch_with_fallback(url, force_tier=force_tier)

    result = {
        "asin": asin,
        "kindle_bsr": None,
        "book_bsr": None,
        "subcategories": [],
        "title": "",
        "price": None,
        "rating": None,
        "review_count": 0,
    }

    if not content:
        return result

    # Title — first H1 or bold early in page
    title_m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if title_m:
        result["title"] = title_m.group(1).strip()[:120]

    # Best Sellers Rank section
    idx = content.lower().find("best sellers rank")
    if idx >= 0:
        bsr_window = content[idx:idx+800]

        # Kindle Store BSR — overall rank: "#N in Kindle Store"
        km = re.search(r"#([\d,]+)\s+in\s+Kindle\s+Store", bsr_window, re.IGNORECASE)
        if km:
            result["kindle_bsr"] = int(km.group(1).replace(",", ""))

        # Books BSR
        bm = re.search(r"#([\d,]+)\s+in\s+Books\b", bsr_window, re.IGNORECASE)
        if bm:
            result["book_bsr"] = int(bm.group(1).replace(",", ""))

        # Subcategory ranks: "#N in [Category Name](url)"
        for rank_m in re.finditer(r"#([\d,]+)\s+in\s+\[([^\]]+)\]", bsr_window):
            rank = int(rank_m.group(1).replace(",", ""))
            cat  = rank_m.group(2).strip()
            result["subcategories"].append({"rank": rank, "category": cat})

        # Also handle format: "#N in Category Name" (no markdown link)
        for rank_m in re.finditer(r"#([\d,]+)\s+in\s+([A-Z][^#\n\[]{5,60}?)(?:\s*[\n\(]|$)", bsr_window):
            rank = int(rank_m.group(1).replace(",", ""))
            cat  = rank_m.group(2).strip().rstrip("(")
            if "Kindle Store" not in cat and "Books" not in cat:
                if not any(s["category"] == cat for s in result["subcategories"]):
                    result["subcategories"].append({"rank": rank, "category": cat})

        # If no overall Kindle BSR but we have subcategory ranks, use best subcategory
        # as a proxy (it's a lower bound on actual demand)
        if result["kindle_bsr"] is None and result["subcategories"]:
            best_subcat = min(result["subcategories"], key=lambda x: x["rank"])
            # Only use as proxy if it's a meaningful rank (< 10,000)
            if best_subcat["rank"] < 10_000:
                result["kindle_bsr"] = best_subcat["rank"] * 10  # rough Kindle Store equivalent

    # Price
    price_m = re.search(r"\$(\d+\.\d{2})", content[:3000])
    if price_m:
        try:
            val = float(price_m.group(1))
            if 0.49 <= val <= 49.99:
                result["price"] = val
        except ValueError:
            pass

    # Rating
    rating_m = re.search(r"(\d+\.\d+)\s+out of\s+5\s+stars?", content[:3000], re.IGNORECASE)
    if rating_m:
        try:
            val = float(rating_m.group(1))
            if 1.0 <= val <= 5.0:
                result["rating"] = val
        except ValueError:
            pass

    # Review count
    reviews_m = re.search(r"([\d,]+)\s+ratings?", content[:5000], re.IGNORECASE)
    if reviews_m:
        try:
            result["review_count"] = int(reviews_m.group(1).replace(",", ""))
        except ValueError:
            pass

    return result

def fetch_bsr_for_niche(raw_search: str, force_tier: int = 0,
                         max_products: int = 3) -> list[dict]:
    """
    Extract top ASINs from search page and fetch BSR for each.
    Returns list of BSR dicts sorted by kindle_bsr (ascending = better rank).
    Credit cost: max_products Firecrawl credits.
    """
    asins = extract_asins_from_search(raw_search, max_asins=max_products + 2)
    if not asins:
        log("BSR: no ASINs found in search results")
        return []

    bsr_data = []
    fetched = 0
    for asin in asins:
        if fetched >= max_products:
            break
        log(f"BSR: fetching product page for ASIN {asin}")
        bsr = fetch_bsr_for_asin(asin, force_tier=force_tier)
        # Accept if we got any BSR signal (kindle or books)
        if bsr["kindle_bsr"] is not None or bsr["book_bsr"] is not None:
            bsr_data.append(bsr)
            fetched += 1
        elif bsr.get("title") or bsr.get("rating"):
            # Got page content but no BSR field — still store as partial data
            bsr_data.append(bsr)
        time.sleep(0.5)

    # Sort by Kindle BSR ascending (lower = better selling)
    bsr_data.sort(key=lambda x: x["kindle_bsr"] or 9_999_999)
    return bsr_data

def interpret_bsr(bsr: int | None) -> str:
    """Human-readable BSR interpretation for LEARNING.md."""
    if bsr is None:
        return "unknown"
    if bsr <= 1_000:
        return f"#{bsr:,} 🔥 top seller (~100-500 sales/day)"
    if bsr <= 5_000:
        return f"#{bsr:,} ✅ strong seller (~20-100 sales/day)"
    if bsr <= 20_000:
        return f"#{bsr:,} 👍 active seller (~5-20 sales/day)"
    if bsr <= 100_000:
        return f"#{bsr:,} 📉 occasional sales (~1-5/day)"
    return f"#{bsr:,} ⚠️ slow mover (<1 sale/day)"

# ── TIER 1: Firecrawl ─────────────────────────────────────────────────────────

def firecrawl_scrape(url: str, timeout: int = 30) -> str | None:
    if not FIRECRAWL_API_KEY:
        log_tier(1, "No API key — skipping Firecrawl")
        return None
    try:
        log_tier(1, f"Scraping: {url}")
        resp = requests.post(
            "https://api.firecrawl.dev/v1/scrape",
            headers={"Authorization": f"Bearer {FIRECRAWL_API_KEY}"},
            json={
                "url": url,
                "formats": ["markdown"],
                "onlyMainContent": True,
                "includeTags": ["h1","h2","h3","span","div","a","p"],
                "timeout": timeout * 1000,
            },
            timeout=timeout + 10,
        )
        if resp.status_code == 402:
            log_tier(1, "Credits exhausted — falling through to Tier 2")
            return None
        if resp.status_code != 200:
            log_tier(1, f"HTTP {resp.status_code} — falling through to Tier 2")
            return None
        data = resp.json()
        content = data.get("data", {}).get("markdown", "")
        if len(content) < 200:
            log_tier(1, "Response too short — falling through to Tier 2")
            return None
        log_tier(1, f"OK — {len(content):,} chars")
        return content
    except Exception as e:
        log_tier(1, f"Error: {e} — falling through to Tier 2")
        return None

def firecrawl_scrape_product(url: str, timeout: int = 30) -> str | None:
    """Firecrawl scrape optimized for Amazon product pages (includes li/ul for BSR)."""
    if not FIRECRAWL_API_KEY:
        return None
    try:
        log_tier(1, f"Scraping product: {url}")
        resp = requests.post(
            "https://api.firecrawl.dev/v1/scrape",
            headers={"Authorization": f"Bearer {FIRECRAWL_API_KEY}"},
            json={
                "url": url,
                "formats": ["markdown"],
                "onlyMainContent": True,
                # Include li/ul so BSR list items are preserved
                "includeTags": ["h1","h2","h3","span","div","a","p","li","ul","table","td","th"],
                "timeout": timeout * 1000,
            },
            timeout=timeout + 10,
        )
        if resp.status_code != 200:
            return None
        content = resp.json().get("data", {}).get("markdown", "")
        if len(content) < 200:
            return None
        log_tier(1, f"Product OK — {len(content):,} chars")
        return content
    except Exception as e:
        log_tier(1, f"Product scrape error: {e}")
        return None

def scrapling_scrape(url: str) -> str | None:
    try:
        log_tier(2, f"Scraping: {url}")
        from scrapling.fetchers import StealthyFetcher
        page = StealthyFetcher.fetch(
            url,
            headless=True,
            network_idle=True,
            block_images=True,
            disable_resources=True,
        )
        text = page.get_all_text(ignore_tags=["script","style","nav","footer"])
        if len(text) < 200:
            log_tier(2, "Response too short — falling through to Tier 3")
            return None
        log_tier(2, f"OK — {len(text):,} chars")
        return text
    except Exception as e:
        log_tier(2, f"Error: {e} — falling through to Tier 3")
        return None

# ── TIER 3: Camoufox ──────────────────────────────────────────────────────────

def camoufox_scrape(url: str) -> str | None:
    try:
        log_tier(3, f"Scraping: {url}")
        from camoufox.sync_api import Camoufox
        with Camoufox(headless=True, block_images=True) as fox:
            page = fox.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            time.sleep(2)
            text = page.inner_text("body")
            page.close()
        if len(text) < 200:
            log_tier(3, "Response too short — all tiers exhausted")
            return None
        log_tier(3, f"OK — {len(text):,} chars")
        return text
    except Exception as e:
        log_tier(3, f"Error: {e} — all tiers exhausted")
        return None

# ── Tiered fetch ───────────────────────────────────────────────────────────────

def fetch_with_fallback(url: str, force_tier: int = 0) -> tuple[str | None, int]:
    """Returns (content, tier_used) or (None, 0) if all failed."""
    if force_tier == 2:
        content = scrapling_scrape(url)
        return (content, 2) if content else (None, 0)
    if force_tier == 3:
        content = camoufox_scrape(url)
        return (content, 3) if content else (None, 0)

    # Normal waterfall
    content = firecrawl_scrape(url)
    if content:
        return content, 1

    content = scrapling_scrape(url)
    if content:
        return content, 2

    content = camoufox_scrape(url)
    if content:
        return content, 3

    return None, 0

# ── Amazon result parser ───────────────────────────────────────────────────────

def parse_amazon_results(raw: str, niche: str) -> list[dict]:
    """
    Extract Kindle book entries from Firecrawl's Amazon search markdown.

    Firecrawl renders Amazon search results with titles as bold markdown links:
        [**Book Title**](https://amazon.com/...)

    Rating appears nearby as: 4.7_4.7 out of 5 stars_ or 4.7 out of 5 stars
    Reviews appear as: [(34,079)](url) or [34,079 ratings](url)
    Price appears as: $13.99
    """
    results = []

    # ── Extract titles from image alt-text (most reliable across page variants) ─
    # Amazon always renders: [![Title](img_url)](product_url)
    img_alt_pat = re.compile(
        r'\[!\[([^\]]{8,160})\]\(https://m\.media-amazon\.com[^\)]+\)\]'
        r'\(https://www\.amazon\.com[^\)]+\)'
    )

    # Supplemental: bold markdown links [**Title**](url) — some page variants
    bold_link_pat = re.compile(
        r'\[\*\*(.+?)\*\*\]\(https://www\.amazon\.com[^\)]+\)'
    )

    noise_title_pat = re.compile(
        r"(Back to top|Help|Need help|Customer Service|Your account|"
        r"Sign in|Shop|Browse|See all|Kindle Unlimited|Prime|^Amazon|"
        r"^GBP|^USD|^\$\d)",
        re.IGNORECASE
    )

    candidate_titles = []
    seen_titles = set()

    # Primary: image alt-text (most reliable)
    for m in img_alt_pat.finditer(raw):
        title = m.group(1).strip()
        if noise_title_pat.search(title):
            continue
        if len(title) < 8 or len(title) > 160:
            continue
        if title not in seen_titles:
            candidate_titles.append((title, m.start()))
            seen_titles.add(title)

    # Supplement: bold links (some page variants have these, some don't)
    for m in bold_link_pat.finditer(raw):
        title = m.group(1).strip()
        # Strip bold markers
        title = re.sub(r"^\*\*|\*\*$", "", title).strip()
        if noise_title_pat.search(title):
            continue
        if len(title) < 8 or len(title) > 160:
            continue
        if title not in seen_titles:
            candidate_titles.append((title, m.start()))
            seen_titles.add(title)

    # ── Build a title→position map preferring bold links over img (data is near bold) ──
    # Bold link positions have rating/price data nearby; img positions don't
    bold_positions = {}
    for m in bold_link_pat.finditer(raw):
        title_raw = m.group(1).strip()
        title_clean = re.sub(r"^\*\*|\*\*$", "", title_raw).strip()
        if title_clean not in bold_positions:
            bold_positions[title_clean] = m.start()

    # Assign best position for each candidate title
    # If a bold link version exists for this title, use that position for data extraction
    candidate_titles_with_pos = []
    for title, img_pos in candidate_titles:
        # Try to find a matching bold link (first 50 chars match)
        best_pos = img_pos
        for bold_title, bold_pos in bold_positions.items():
            if title[:40].lower() in bold_title[:50].lower() or bold_title[:40].lower() in title[:50].lower():
                best_pos = bold_pos
                break
        candidate_titles_with_pos.append((title, best_pos))

    candidate_titles = candidate_titles_with_pos
    # ── For each title, find rating/price in the following window ─────────────
    rating_pat  = re.compile(r"(\d+\.\d+)(?:_\d+\.\d+)?\s*out of\s*5\s*stars?",
                             re.IGNORECASE)
    reviews_pat = re.compile(r"\[\(?([0-9,]+(?:\.[0-9]+)?[Kk]?)\)?\]\(https?://")  # [(147.6K)](url)
    price_pat   = re.compile(r"\$(\d+\.?\d*)")
    ku_pat      = re.compile(r"Kindle Unlimited|Free with KU", re.IGNORECASE)

    for title, pos in candidate_titles:
        window = raw[pos: pos + 3000]

        # Rating
        rating = None
        rm = rating_pat.search(window)
        if rm:
            try:
                val = float(rm.group(1))
                if 1.0 <= val <= 5.0:
                    rating = val
            except ValueError:
                pass

        # Review count
        review_count = 0
        rcm = reviews_pat.search(window)
        if rcm:
            try:
                raw_num = rcm.group(1).replace(",", "")
                if raw_num.lower().endswith("k"):
                    review_count = int(float(raw_num[:-1]) * 1000)
                else:
                    review_count = int(float(raw_num))
            except ValueError:
                pass

        # Price — search wider window since prices appear after all the review links
        price = None
        is_ku = bool(ku_pat.search(window[:800]))
        for pm in price_pat.finditer(window[:2000]):
            try:
                val = float(pm.group(1))
                if 0.49 <= val <= 49.99:
                    price = val
                    break
            except ValueError:
                pass
        if price is None and is_ku:
            price = 0.0

        # Must have at least a price or rating to count
        if price is None and rating is None:
            continue

        results.append({
            "title": title,
            "author": "",
            "rating": rating,
            "review_count": review_count,
            "price": price,
            "kindle": True,
        })

    return results[:15]

# ── Market scoring ─────────────────────────────────────────────────────────────

def score_market(books: list[dict], niche: str,
                  bsr_data: list[dict] | None = None) -> dict:
    """
    Score niche opportunity 1.0–10.0.

    Scoring weights (revised with BSR):
      BSR signal (40%)  — how well do top competitors sell right now?
      Demand signal (30%) — review counts indicate proven buyer base
      Price signal (20%) — is the price point commercially viable?
      Competition signal (10%) — are there beatable entries?
    """
    # ── BSR score (40%) ───────────────────────────────────────────────────────
    bsr_score = 5.0  # neutral default when no BSR data
    best_bsr  = None
    avg_bsr   = None

    if bsr_data:
        kindle_bsrs = [b["kindle_bsr"] for b in bsr_data if b.get("kindle_bsr")]
        if kindle_bsrs:
            best_bsr = min(kindle_bsrs)
            avg_bsr  = int(sum(kindle_bsrs) / len(kindle_bsrs))

            # BSR → demand score (lower BSR = higher demand)
            if best_bsr <= 1_000:
                bsr_score = 9.5   # proven hot market
            elif best_bsr <= 5_000:
                bsr_score = 8.5   # strong demand
            elif best_bsr <= 20_000:
                bsr_score = 7.0   # active market — good target
            elif best_bsr <= 50_000:
                bsr_score = 5.5   # moderate — needs right angle
            elif best_bsr <= 100_000:
                bsr_score = 4.0   # thin or declining
            else:
                bsr_score = 2.0   # not selling

    # ── Demand score from review counts (30%) ─────────────────────────────────
    if not books:
        demand_score = 3.0
        avg_reviews  = 0
        avg_rating   = 0.0
        avg_price    = 4.99
        kindle_ratio = 0.0
    else:
        total = len(books)
        avg_reviews  = sum(b.get("review_count", 0) for b in books) / total
        avg_rating   = sum(b.get("rating") or 4.0 for b in books) / total
        prices       = [b["price"] for b in books if b.get("price") and b["price"] > 0]
        avg_price    = sum(prices) / len(prices) if prices else 4.99
        kindle_ratio = sum(1 for b in books if b.get("kindle")) / total

        # Reviews → demand (even partial data is useful)
        if avg_reviews >= 5000:
            demand_score = 9.0
        elif avg_reviews >= 2000:
            demand_score = 7.5
        elif avg_reviews >= 500:
            demand_score = 6.0
        elif avg_reviews >= 100:
            demand_score = 5.0
        elif avg_reviews > 0:
            demand_score = 4.0
        else:
            demand_score = 3.5  # no review data — neutral, not penalizing

    # ── Price score (20%) ─────────────────────────────────────────────────────
    # Sweet spot for Kindle nonfiction: $3.99–$9.99
    if 3.99 <= avg_price <= 9.99:
        price_score = 8.0
    elif 2.99 <= avg_price < 3.99:
        price_score = 6.0  # low price = lower royalty
    elif 9.99 < avg_price <= 14.99:
        price_score = 7.0  # higher price = fewer buyers but more $ each
    elif avg_price > 14.99:
        price_score = 5.5  # premium — hard to compete
    else:
        price_score = 5.0

    # ── Competition score (10%) ───────────────────────────────────────────────
    # Low avg reviews per competitor = easier to enter
    if avg_reviews == 0:
        competition_score = 5.0  # unknown
    elif avg_reviews < 100:
        competition_score = 8.0  # low competition
    elif avg_reviews < 500:
        competition_score = 6.5
    elif avg_reviews < 2000:
        competition_score = 5.0
    else:
        competition_score = 3.5  # tough — need strong differentiation

    # ── Weighted final score ──────────────────────────────────────────────────
    score = round(
        bsr_score  * 0.40 +
        demand_score * 0.30 +
        price_score  * 0.20 +
        competition_score * 0.10,
        2
    )
    score = max(1.0, min(10.0, score))

    demand_label = (
        "high"   if avg_reviews > 2000 else
        "medium" if avg_reviews > 200  else
        "low"
    )
    competition_label = (
        "high"   if avg_reviews > 3000 else
        "medium" if avg_reviews > 500  else
        "low"
    )

    # Verdict
    if score >= 8.0:
        verdict = "Hot market — strong demand, act fast"
    elif score >= 7.0:
        verdict = "Strong opportunity — high demand, beatable competition"
    elif score >= 5.5:
        verdict = "Moderate opportunity — proceed with differentiated angle"
    elif score >= 4.0:
        verdict = "Marginal — thin or declining market, needs strong hook"
    else:
        verdict = "Avoid — low demand or impenetrable competition"

    return {
        "score":             score,
        "demand":            demand_label,
        "competition":       competition_label,
        "avg_reviews":       round(avg_reviews) if books else 0,
        "avg_rating":        round(avg_rating, 2) if books else 0.0,
        "top_price":         round(avg_price, 2),
        "kindle_ratio":      round(kindle_ratio, 2) if books else 0.0,
        "book_count":        len(books),
        "best_kindle_bsr":   best_bsr,
        "avg_kindle_bsr":    avg_bsr,
        "bsr_score":         round(bsr_score, 1),
        "verdict":           verdict,
    }

# ── LEARNING.md writer ─────────────────────────────────────────────────────────

def append_to_learning(niche: str, books: list[dict], market: dict,
                        tier_used: int, bsr_data: list[dict] | None = None,
                        dry_run: bool = False) -> str:
    tier_names = {1: "Firecrawl", 2: "Scrapling", 3: "Camoufox"}
    today = datetime.now().strftime("%Y-%m-%d")
    ts    = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    top_titles = "\n".join(
        f"  - \"{b['title'][:100]}\" "
        f"({'★' * int(b['rating']) if b.get('rating') else 'no rating'}, "
        f"{b.get('review_count', 0):,} reviews, "
        f"${b.get('price', '?')})"
        for b in books[:5]
    ) or "  (no titles parsed)"

    # BSR section
    bsr_section = ""
    if bsr_data:
        bsr_lines = []
        for b in bsr_data:
            if b.get("kindle_bsr"):
                interp = interpret_bsr(b["kindle_bsr"])
                title_short = b.get("title", b["asin"])[:60]
                subcat = b["subcategories"][0]["category"] if b.get("subcategories") else "Kindle Store"
                bsr_lines.append(f"  - [{title_short}](https://amazon.com/dp/{b['asin']}) → {interp} | Top cat: {subcat}")
        if bsr_lines:
            best = market.get("best_kindle_bsr")
            avg  = market.get("avg_kindle_bsr")
            bsr_section = (
                f"\n### BSR Intelligence (top {len(bsr_data)} competitors)\n"
                f"Best Kindle BSR: {interpret_bsr(best)}\n"
                f"Avg Kindle BSR (top {len(bsr_data)}): #{avg:,}\n\n"
                + "\n".join(bsr_lines) + "\n"
                + f"\n**BSR verdict:** "
                + ("✅ Proven demand — top titles selling actively" if best and best <= 20_000
                   else "⚠️ Thin demand — top titles barely selling" if best and best > 100_000
                   else "📊 Moderate activity — niche viable with right angle")
            )

    entry = f"""
---

## [{today}] Researcher: Niche Analysis — {niche.title()}
<!-- AUTO-GENERATED: {ts} | Tier: {tier_names.get(tier_used, 'unknown')} -->

### Market Score: {market['score']}/10 — {market['verdict']}

| Metric                    | Value                          |
|---------------------------|--------------------------------|
| Demand                    | {market['demand']}             |
| Competition               | {market['competition']}        |
| Best Kindle BSR           | {interpret_bsr(market.get('best_kindle_bsr'))} |
| Avg BSR (top competitors) | {'#' + f"{market['avg_kindle_bsr']:,}" if market.get('avg_kindle_bsr') else 'n/a'} |
| BSR Score Component       | {market.get('bsr_score', 'n/a')}/10 (40% weight) |
| Avg Reviews (top {market['book_count']})   | {market['avg_reviews']:,}              |
| Avg Rating                | {market['avg_rating']}         |
| Avg Price                 | ${market['top_price']}         |
| Kindle Ratio              | {int(market['kindle_ratio']*100)}%     |
| Data Source               | {tier_names.get(tier_used, 'unknown')} |
{bsr_section}
### Top Competitor Titles Found
{top_titles}

### Recommendations
- Score {market['score']}/10 → {"✅ Proceed to outline" if market['score'] >= 6.0 else "⚠️ Consider adjacent niche or stronger angle"}
- Target price: ${market['top_price']} (market avg) — consider ${round(market['top_price'] - 0.01, 2)} to undercut
- If BSR > 100,000 on top books: pivot to more specific sub-niche (e.g. "productivity for ADHD" not "productivity")
- Niche Category: `{niche.lower().replace(" ", "-")}`
"""

    if dry_run:
        log("DRY RUN — would append to LEARNING.md:")
        print(entry)
        return entry

    LEARNING_MD.parent.mkdir(parents=True, exist_ok=True)
    with open(LEARNING_MD, "a") as f:
        f.write(entry)
    log(f"Appended research entry to {LEARNING_MD}")
    return entry

# ── Main research flow ─────────────────────────────────────────────────────────

def research_niche(niche: str, max_results: int = 10,
                   force_tier: int = 0, dry_run: bool = False,
                   skip_bsr: bool = False) -> dict:
    log(f"Starting research for niche: '{niche}'")
    log(f"Tier strategy: {'forced tier ' + str(force_tier) if force_tier else 'waterfall (Firecrawl → Scrapling → Camoufox)'}")
    log(f"BSR enrichment: {'disabled (--no-bsr)' if skip_bsr else 'enabled (3 product pages)'}")

    start = time.time()
    all_books = []
    tier_used = 0
    bsr_data  = []

    # Scrape page 1 of Amazon Kindle search
    url1 = amazon_search_url(niche, page=1)
    content, tier_used = fetch_with_fallback(url1, force_tier=force_tier)

    if content:
        books_p1 = parse_amazon_results(content, niche)
        log(f"Page 1: found {len(books_p1)} candidate titles")
        all_books.extend(books_p1)

        # BSR enrichment: fetch product pages for top 3 ASINs
        if not skip_bsr:
            log("BSR: extracting top ASINs from search results...")
            bsr_data = fetch_bsr_for_niche(content, force_tier=force_tier, max_products=3)
            log(f"BSR: fetched data for {len(bsr_data)} products")

        # Page 2 if we have headroom
        if len(books_p1) >= 3 and len(all_books) < max_results:
            time.sleep(1.0)
            url2 = amazon_search_url(niche, page=2)
            content2, _ = fetch_with_fallback(url2, force_tier=force_tier)
            if content2:
                books_p2 = parse_amazon_results(content2, niche)
                log(f"Page 2: found {len(books_p2)} additional titles")
                all_books.extend(books_p2)

        # Deduplicate
        seen = set()
        unique = []
        for b in all_books:
            if b["title"] not in seen:
                seen.add(b["title"])
                unique.append(b)
        all_books = unique[:max_results]
    else:
        log("WARNING: All tiers failed — proceeding with empty dataset")

    elapsed = round(time.time() - start, 1)
    log(f"Scraping complete in {elapsed}s — {len(all_books)} titles, {len(bsr_data)} BSR records")

    # Score the market (BSR-integrated)
    market = score_market(all_books, niche, bsr_data=bsr_data)
    bsr_summary = ""
    if bsr_data and market.get("best_kindle_bsr"):
        bsr_summary = f" | BSR #{market['best_kindle_bsr']:,} (best competitor)"
    log(f"Market score: {market['score']}/10 — {market['verdict']}{bsr_summary}")

    # Write to LEARNING.md
    entry = append_to_learning(niche, all_books, market, tier_used,
                                bsr_data=bsr_data, dry_run=dry_run)

    result = {
        "niche":          niche,
        "books_found":    len(all_books),
        "bsr_records":    len(bsr_data),
        "market":         market,
        "tier_used":      tier_used,
        "elapsed_seconds": elapsed,
        "top_books":      all_books[:5],
        "bsr_data":       bsr_data,
    }

    # Telegram notification (enriched with BSR)
    bsr_line = ""
    if bsr_data and market.get("best_kindle_bsr"):
        bsr_line = f"\nBest competitor BSR: {interpret_bsr(market['best_kindle_bsr'])}"

    msg = (
        f"📊 *Research complete: {niche.title()}*\n\n"
        f"Score: *{market['score']}/10*\n"
        f"Verdict: {market['verdict']}"
        f"{bsr_line}\n"
        f"Demand: {market['demand']} | Competition: {market['competition']}\n"
        f"Avg price: ${market['top_price']} | Books sampled: {len(all_books)}\n\n"
        f"{'✅ Recommended — proceed to outline' if market['score'] >= 6.0 else '⚠️ Marginal — review before proceeding'}"
    )
    if not dry_run:
        notify_telegram(msg)

    return result

# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Ebook Factory Researcher — Amazon niche market analysis"
    )
    parser.add_argument("--niche", required=True,
                        help='Niche keyword, e.g. "home organization"')
    parser.add_argument("--max-results", type=int, default=10,
                        help="Max book results to collect (default: 10)")
    parser.add_argument("--tier", type=int, default=0, choices=[0,1,2,3],
                        help="Force scraping tier: 0=waterfall, 1=Firecrawl, 2=Scrapling, 3=Camoufox")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print LEARNING.md entry without writing it")
    parser.add_argument("--json", action="store_true",
                        help="Output result as JSON to stdout")
    parser.add_argument("--no-bsr", action="store_true",
                        help="Skip BSR product page fetching (saves ~3 Firecrawl credits)")
    args = parser.parse_args()

    result = research_niche(
        niche=args.niche,
        max_results=args.max_results,
        force_tier=args.tier,
        dry_run=args.dry_run,
        skip_bsr=args.no_bsr,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        log("─" * 60)
        log(f"DONE: {args.niche}")
        log(f"  Score:       {result['market']['score']}/10")
        log(f"  Verdict:     {result['market']['verdict']}")
        log(f"  Books found: {result['books_found']}")
        if result['market'].get('best_kindle_bsr'):
            log(f"  Best BSR:    {interpret_bsr(result['market']['best_kindle_bsr'])}")
        log(f"  BSR records: {result['bsr_records']}")
        log(f"  Tier used:   {result['tier_used']} ({['Firecrawl','Scrapling','Camoufox'][result['tier_used']-1] if result['tier_used'] else 'none'})")
        log(f"  Time:        {result['elapsed_seconds']}s")
        if not args.dry_run:
            log(f"  Written to:  {LEARNING_MD}")

if __name__ == "__main__":
    main()
