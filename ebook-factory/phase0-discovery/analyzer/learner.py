"""
LEARNING.md Writer Module

Writes structured analysis entries to LEARNING.md for future reference.
"""

from pathlib import Path
from datetime import datetime


def format_learning_entry(
    book: dict,
    metrics_dict: dict,
    patterns: list,
) -> str:
    """
    Format a single book analysis into markdown for LEARNING.md.
    
    Args:
        book: Book data dict (title, asin, marketplace, etc.)
        metrics_dict: Calculated metrics (royalty_per_unit, keng_per_unit, niche_score)
        patterns: List of pattern dicts applicable to this book
    
    Returns:
        Formatted markdown entry
    """
    # Extract key data
    title = book.get('title', 'Unknown')
    asin = book.get('asin', 'N/A')
    marketplace = book.get('marketplace', 'Amazon.com')
    currency = book.get('currency', 'USD')
    symbol = {'USD': '$', 'GBP': '£', 'EUR': '€', 'JPY': '¥'}.get(currency, '$')
    
    # Metrics
    royalty = book.get('royalty_amount', 0)
    units = book.get('units_sold', 0) or book.get('net_units', 0)
    keng_total = metrics_dict.get('kenp_total', 0)
    keng_per_unit = metrics_dict.get('kenp_per_unit', 0)
    royalty_per_unit = metrics_dict.get('royalty_per_unit', 0)
    niche_category = metrics_dict.get('niche_category', 'other')
    overall_score = metrics_dict.get('overall_score', 0)
    royalty_type = book.get('royalty_type', '70%')
    
    # Format date
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    # Build markdown entry
    entry = f"""## [{date_str}] Book: {title} (ASIN: {asin})

### Performance Summary
- **Royalty:** {symbol}{royalty:.2f} ({currency})
- **Units Sold:** {units}
- **KENP Pages:** {keng_total}
- **Marketplace:** {marketplace}
- **Price:** {symbol}{book.get('avg_offer_price', 0):.2f} ({currency})
- **Royalty Tier:** {royalty_type}

### Metrics
- **Royalty/unit:** {symbol}{royalty_per_unit:.2f}
- **KENP/unit:** {keng_per_unit:.1f} pages
- **Niche Category:** {niche_category}
- **Niche Score:** {overall_score}/10

### Patterns Observed
"""
    
    # Add patterns for this book
    if patterns:
        relevant_patterns = [p for p in patterns if title in p.get('evidence', [])]
        if relevant_patterns:
            for pattern in relevant_patterns:
                desc = pattern['description']
                if pattern['pattern_type'] == 'high_engagement':
                    entry += f"- ✅ High reader engagement ({pattern['metrics'].get('kenp_per_unit', 0):.0f} KENP/unit)\n"
                elif pattern['pattern_type'] == 'strong_niche':
                    entry += f"- ✅ {niche_category} niche performs well\n"
                else:
                    entry += f"- ℹ️ {desc}\n"
        else:
            entry += "- ℹ️ No specific patterns detected for this book\n"
    else:
        entry += "- ℹ️ Limited data (first sale record)\n"
    
    entry += """
### Recommendations
"""
    
    # Generate recommendations based on metrics
    if keng_per_unit >= 25:
        entry += "1. ✅ **High engagement** — This topic holds reader attention. Consider similar topics.\n"
    else:
        entry += "1. ⚠️ **Low engagement** — Only {:.0f} KENP/unit. Consider shorter, punchier content.\n".format(keng_per_unit)
    
    if royalty_per_unit >= 3.0:
        entry += "2. ✅ **Good price point** — {:.2f}/unit meets target.\n".format(royalty_per_unit)
    else:
        entry += "2. ⚠️ **Below target royalty** — {:.2f}/unit (target: $3.50+).\n".format(royalty_per_unit)
    
    if niche_category == 'tech-security':
        entry += "3. 🔍 **Tech/security niche shows promise** — UK marketplace converts. Try US market.\n"
    elif niche_category == 'productivity':
        entry += "3. 🔍 **Productivity niche is competitive** — Need unique angle to stand out.\n"
    elif niche_category == 'business-strategy':
        entry += "3. 🔍 **Business strategy books sell consistently** — $3.47-3.48 average royalty.\n"
    else:
        entry += f"3. 🔍 **Niche analysis: {niche_category}** — Monitor performance after 5+ books.\n"
    
    entry += f"""
---
"""
    
    return entry


def append_to_learning_md(
    learning_path: Path,
    entries: list,
):
    """
    Append analysis entries to LEARNING.md.
    
    Args:
        learning_path: Path to LEARNING.md
        entries: List of formatted markdown strings
    """
    # Create parent directories if needed
    learning_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Check if file exists and has content
    if learning_path.exists() and learning_path.stat().st_size > 0:
        # Append mode
        with open(learning_path, 'a', encoding='utf-8') as f:
            # Add separator if file has content
            with open(learning_path, 'r', encoding='utf-8') as rf:
                content = rf.read()
                if content and not content.endswith('\n'):
                    f.write('\n\n')
            
            # Write new entries
            for entry in entries:
                f.write(entry)
                f.write('\n')
    else:
        # Create new file with header
        with open(learning_path, 'w', encoding='utf-8') as f:
            f.write("# KDP Performance Learning Base\n\n")
            f.write("## Purpose\n\n")
            f.write("This file accumulates insights from KDP sales data analysis.\n")
            f.write("Each entry contains:\n")
            f.write("- Book performance metrics\n")
            f.write("- Patterns detected\n")
            f.write("- Recommendations for future topics\n\n")
            f.write("## Analysis History\n\n")
            
            for entry in entries:
                f.write(entry)
                f.write('\n')
    
    print(f"✓ Appended {len(entries)} entries to {learning_path}")


def generate_summary_report(
    aggregates: dict,
    patterns: list,
    book_count: int,
) -> str:
    """
    Generate a summary report section for LEARNING.md.
    
    Args:
        aggregates: Dict of niche aggregates
        patterns: List of detected patterns
        book_count: Total books analyzed
    
    Returns:
        Formatted summary markdown
    """
    total_royalty = sum(d['total_royalty'] for d in aggregates.values())
    if book_count > 0:
        avg_royalty = sum(d['avg_royalty_per_unit'] * d['book_count'] for d in aggregates.values()) / book_count
    else:
        avg_royalty = 0
    
    summary = f"""
## Summary Report ({datetime.now().strftime("%Y-%m-%d")})

### Overall Metrics
- **Books Analyzed:** {book_count}
- **Total Royalties:** ${total_royalty:.2f}
- **Average Royalty/Unit:** ${avg_royalty:.2f}
"""
    
    # Best-performing niche
    if aggregates:
        best_niche = max(aggregates.items(), key=lambda x: x[1]['avg_royalty_per_unit'])
        summary += f"""
### Best Performing Niche
- **Niche:** {best_niche[0]}
- **Avg Royalty:** ${best_niche[1]['avg_royalty_per_unit']:.2f}/unit
- **Avg KENP:** {best_niche[1]['avg_keng_per_unit']:.1f} pages/unit
- **Book Count:** {best_niche[1]['book_count']}
"""
    
    # Top patterns detected
    if patterns:
        summary += """
### Key Patterns Detected
"""
        for i, pattern in enumerate(patterns[:3], 1):
            summary += f"""
{i}. **{pattern['pattern_type']}**
   - {pattern['description']}
   - **Recommendation:** {pattern['recommendation']}
"""
    
    summary += """
---
"""
    
    return summary
