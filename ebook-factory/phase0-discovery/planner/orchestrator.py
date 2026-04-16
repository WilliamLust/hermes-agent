"""
Orchestrator — Main Planner Pipeline

Reads LEARNING.md, scores niches, generates topic recommendations, outputs topic_plan.md
"""

from pathlib import Path
import sys
import json
from datetime import datetime
import yaml
from typing import Dict, List, Tuple

from niche_scorer import read_learning_md, score_niches
from topic_generator import generate_topic_recommendations, TopicRecommendation
from historical_store import HistoricalStore, ListingEntry
from typing import Optional, List, Dict, Any


def load_config(config_path: Path) -> Dict:
    """Load configuration from YAML file."""
    if not config_path.exists():
        return {}
    
    with open(config_path) as f:
        return yaml.safe_load(f)


def load_historical_data(config: Dict) -> Dict:
    """Load historical marketplace data from database."""
    from hermes_constants import get_hermes_home
    
    db_path = get_hermes_home() / 'planner.db'
    
    if not db_path.exists():
        return {
            'has_data': False,
            'total_listings': 0,
            'top_niches': [],
            'recent_trends': [],
            'store': None,
            'message': 'No historical marketplace data available'
        }
    
    store = HistoricalStore(str(db_path))
    
    # Get aggregate data
    top_niches = store.get_top_performing_niches(n=20, min_listings=2)
    recent_trends = store.get_recent_trends(days=90)
    all_listings = store.get_all()
    
    return {
        'has_data': True,
        'total_listings': len(all_listings),
        'top_niches': top_niches,
        'recent_trends': recent_trends,
        'store': store,
        'message': f"Loaded {len(all_listings)} marketplace listings"
    }


def score_niches_with_history(
    niches: List[str],
    config: Dict,
    historical: Dict[str, Any]
) -> List[tuple]:
    """Score niches with historical marketplace data.
    
    Args:
        niches: List of niche names from LEARNING.md
        config: Configuration dictionary
        historical: Historical data from load_historical_data()
    
    Returns:
        List of (niche, score, details) tuples
    """
    # Get base scores from niche_scorer
    base_scores = score_niches(niches, config)
    
    if not historical['has_data']:
        return base_scores
    
    # Create lookup of historical data
    historical_lookup = {
        item['niche'].lower(): item 
        for item in historical['top_niches']
    }
    
    trending_lookup = {
        item['niche'].lower(): item
        for item in historical['recent_trends']
    }
    
    scored_with_history = []
    for niche, base_score, details in base_scores:
        # Start with base score
        score = base_score
        historical_bonus = 0.0
        trend_bonus = 0.0
        
        niche_lower = niche.lower()
        
        # Historical performance bonus (up to +1.0)
        if niche_lower in historical_lookup:
            hist_data = historical_lookup[niche_lower]
            # Bonus for strong historical performance
            if hist_data['avg_roi'] >= 0.3:
                historical_bonus = min(hist_data['avg_roi'] / 0.3, 1.0)
            
            details['historical_avg_roi'] = hist_data['avg_roi']
            details['historical_avg_kenp'] = hist_data['avg_kenp']
            details['historical_book_count'] = hist_data['listing_count']
        
        # Trend bonus (up to +1.0)
        if niche_lower in trending_lookup:
            trend_data = trending_lookup[niche_lower]
            # Bonus for being in recent trends
            trend_bonus = min(trend_data['listing_count'] / 5, 1.0)
            
            details['trending'] = True
            details['trending_listing_count'] = trend_data['listing_count']
        
        # Combine scores (capped at 10)
        final_score = min(score + historical_bonus + trend_bonus, 10.0)
        
        scored_with_history.append((niche, final_score, details))
    
    # Sort by score descending
    scored_with_history.sort(key=lambda x: x[1], reverse=True)
    
    return scored_with_history


def run_planner(
    config_path: Path,
    learning_md_path: Path = None,
    output_path: Path = None,
    dry_run: bool = False
) -> Dict:
    """
    Main planner pipeline.
    
    Args:
        config_path: Path to config.yaml
        learning_md_path: Path to LEARNING.md (overrides config)
        output_path: Path to write topic_plan.md (overrides config)
        dry_run: If True, skip writing output file
    
    Returns:
        Dict with results and status
    """
    # Load config
    config = load_config(config_path)
    
    # Override paths from args
    if learning_md_path:
        config['learning_md_path'] = str(learning_md_path)
    if output_path:
        config['output_path'] = str(output_path)
    
    learning_md_path = Path(config['learning_md_path'])
    output_path = Path(config['output_path'])
    
    print(f"╔════════════════════════════════════════╗")
    print(f"║   🔧 Planner Agent Initializing       ║")
    print(f"╚════════════════════════════════════════╝")
    print()
    
    # Phase 0: Load historical marketplace data
    print("📊 Phase 0: Checking historical marketplace data...")
    historical = load_historical_data(config)
    
    if historical['has_data']:
        print(f"   ✓ {historical['message']}")
        print(f"   ✓ Found {len(historical['top_niches'])} top-performing niches")
        if historical['recent_trends']:
            print(f"   ✓ Found {len(historical['recent_trends'])} trending niches (90 days)")
    else:
        print(f"   ⚠️ {historical['message']}")
        print("   ℹ️ Analysis will rely on LEARNING.md only")
    print()
    
    # Phase 1: Read LEARNING.md
    print("📖 Phase 1: Reading LEARNING.md...")
    result = read_learning_md(learning_md_path)
    
    if result.get('error'):
        error_msg = f"❌ {result['error']}"
        print(error_msg)
        return {'error': error_msg}
    
    entries = result['entries']
    niches = result['niches']
    
    if not entries:
        error_msg = "❌ No entries found in LEARNING.md — Run analyzer first"
        print(error_msg)
        return {'error': error_msg}
    
    print(f"   ✓ Found {len(entries)} book entries")
    print(f"   ✓ Found {len(niches)} niches")
    print()
    
    # Phase 2: Score niches (with historical context if available)
    print("📊 Phase 2: Scoring niches...")
    scored_niches = score_niches_with_history(niches, config, historical)
    
    print(f"   ✓ Scored {len(scored_niches)} niches")
    
    # Show top niches
    print("   Top niches:")
    for niche, score, details in scored_niches[:3]:
        print(f"     {niche}: {score:.2f}/10")
    print()
    
    # Phase 3: Generate recommendations
    print("💡 Phase 3: Generating topic recommendations...")
    recommendations = generate_topic_recommendations(
        scored_niches,
        entries,
        config,
        historical if historical['has_data'] else None
    )
    
    print(f"   ✓ Generated {len(recommendations)} recommendations")
    print()
    
    if not recommendations:
        warning = "⚠️ No viable topics found (all niches scored below 4.0)"
        print(warning)
        return {'warning': warning, 'recommendations': []}
    
    # Close historical store if open (before writing files)
    if historical['store']:
        historical['store'].__exit__(None, None, None)
    
    # Phase 4: Write output
    output_content = generate_plan_output(
        recommendations=recommendations,
        scored_niches=scored_niches,
        config=config,
        historical=historical,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    
    if dry_run:
        print("ℹ️ Dry run — skipped writing to topic_plan.md")
        print()
        print("═╤═══════════════════════════")
        print("📊 Simulation Output:")
        print("═╤═══════════════════════════")
        print(output_content)
        print()
    else:
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            f.write(output_content)
        
        print(f"✅ Plan written to {output_path}")
        print()
    
    # Summary
    print("═╤═════════════════════════════")
    print("📊 Planner Complete")
    print(f"   Niches analyzed: {len(niches)}")
    print(f"   Historical data: {'Yes' if historical['has_data'] else 'No'}")
    print(f"   Topics generated: {len(recommendations)}")
    print(f"   Output: {output_path.name}")
    print("═╤═════════════════════════════")
    print()
    
    return {
        'status': 'success',
        'recommendations': recommendations,
        'scored_niches': scored_niches,
        'historical': historical if not historical['has_data'] or not historical.get('store') else {
            k: v for k, v in historical.items() if k != 'store'
        },
        'output_path': str(output_path),
        'dry_run': dry_run
    }


def generate_plan_output(
    recommendations: List[TopicRecommendation],
    scored_niches: List[tuple],
    config: Dict,
    historical: Dict[str, Any],
    timestamp: str
) -> str:
    """Generate the topic_plan.md content."""
    
    lines = []
    
    # Header
    lines.append(f"# Book Topic Plan — {timestamp}")
    lines.append("")
    lines.append("Generated by Hermes Planner Agent")
    lines.append("")
    
    # Historical data badge
    if historical['has_data']:
        lines.append("✅ Includes historical marketplace analysis from `~/.hermes/planner.db`")
        lines.append("")
    else:
        lines.append("⚠️ No historical marketplace data available")
        lines.append("")
    
    lines.append("This plan is based on analysis of your KDP sales data from LEARNING.md.")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # Executive Summary
    lines.append("## Executive Summary")
    lines.append("")
    num_topics = len(recommendations)
    lines.append(f"**{num_topics} high-potential topics** identified from your KDP data.")
    lines.append("")
    lines.append("### Top 3 Priorities")
    lines.append("")
    for i, rec in enumerate(recommendations[:3], 1):
        lines.append(f"{i}. **{rec.suggested_title}**")
        lines.append(f"   - Niche: `{rec.niche}`")
        lines.append(f"   - Expected ROI: ${rec.expected_roi_per_unit:.2f}/unit")
        lines.append(f"   - Score: {calculate_recommendation_score(rec):.2f}/10")
        lines.append("")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Historical Context Section (if available)
    if historical['has_data']:
        lines.append("## Historical Marketplace Context")
        lines.append("")
        lines.append("This analysis leverages **historical marketplace data** from `planner.db` to improve recommendations.")
        lines.append("")
        lines.append(f"• **Total marketplace listings analyzed:** {historical['total_listings']}")
        lines.append(f"• **Top performing niches with history:** {len(historical['top_niches'])}")
        
        if historical['recent_trends']:
            lines.append(f"• **Recent trending niches (90 days):** {len(historical['recent_trends'])}")
        
        lines.append("")
        
        # Show top 5 historical performers
        lines.append("### Top 5 Historically-Performing Niches")
        lines.append("")
        lines.append("| Niche | Listings | Avg ROI | Avg KENP |")
        lines.append("|-------|----------|---------|----------|")
        
        for item in historical['top_niches'][:5]:
            niche = item['niche']
            count = item['listing_count']
            avg_roi = item['avg_roi'] * 100  # Convert decimal to percentage
            avg_kenp = item['avg_kenp']
            lines.append(f"| {niche} | {count} | ${avg_roi:.1f} | {avg_kenp:.1f} |")
        
        lines.append("")
        lines.append("### Recent Trending Niches (90 Days)")
        lines.append("")
        
        if historical['recent_trends']:
            lines.append("These niches showed strong recent activity:")
            lines.append("")
            for item in historical['recent_trends'][:5]:
                niche = item['niche']
                count = item['listing_count']
                lines.append(f"• `{niche}`: {count} listings")
            lines.append("")
        else:
            lines.append("No significant recent trends detected.")
            lines.append("")
        
        lines.append("---")
        lines.append("")
    
    # Detailed Recommendations
    lines.append("## Detailed Topic Recommendations")
    lines.append("")
    
    for i, rec in enumerate(recommendations, 1):
        lines.append(f"### {i}. {rec.suggested_title}")
        lines.append("")
        lines.append(f"**Niche:** `{rec.niche}`")
        lines.append("")
        lines.append("#### Recommended Angle")
        lines.append("")
        lines.append(rec.unique_angle)
        lines.append("")
        lines.append("#### Target Audience")
        lines.append("")
        lines.append(rec.target_audience)
        lines.append("")
        lines.append("#### Competitive Advantage")
        lines.append("")
        lines.append(rec.competitive_advantage)
        lines.append("")
        lines.append("#### Project Specs")
        lines.append("")
        lines.append(f"- **Estimated Pages:** {rec.estimated_pages}")
        lines.append(f"- **Expected ROI/unit:** ${rec.expected_roi_per_unit:.2f}")
        lines.append("")
        lines.append("#### Validation Notes")
        lines.append("")
        for note in rec.validation_notes:
            lines.append(f"- {note}")
        lines.append("")
        lines.append("---")
        lines.append("")
    
    # Niche Score Summary
    lines.append("## Niche Score Summary")
    lines.append("")
    lines.append("| Niche | Score | Books | Avg ROI/unit | Avg KENP/unit |")
    lines.append("|---|------|-------|--------------|---------------|")
    for niche, score, details in scored_niches:
        hist_note = ""
        if historical['has_data'] and details.get('historical_avg_roi'):
            hist_note = f" ✓ Hist: ${details['historical_avg_roi']:.2f}"
        
        lines.append(
            f"| {niche} | {score:.2f} | {details['book_count']} | "
            f"${details['avg_royalty_per_unit']:.2f} | {details['avg_kenp_per_unit']:.1f} |"
        )
        if hist_note:
            lines.append(f"   `{hist_note}`")
    
    lines.append("")
    
    # Notes
    lines.append("## Notes")
    lines.append("")
    lines.append("- **ROI threshold:** Recommendations require $2.50+ per unit")
    lines.append("- **Engagement threshold:** Recommendations require 20+ KENP/unit")
    lines.append("- **Market validation:** Niches must have 1+ existing books")
    
    if historical['has_data']:
        lines.append("- **Historical data:** Recommendations weighted by marketplace performance history")
    
    lines.append("")
    lines.append("## Next Steps")
    lines.append("")
    lines.append("1. Review top 3 recommendations")
    lines.append("2. Validate against Amazon search results")
    lines.append("3. Select 1 topic for immediate development")
    lines.append("4. Feed chosen topic back into Analyzer for monitoring")
    lines.append("")
    
    return "\n".join(lines)


def calculate_recommendation_score(rec: TopicRecommendation) -> float:
    """Calculate an overall score for a recommendation."""
    # Simple weight: ROI (40%), engagement (30%), market (30%)
    roi_component = min(rec.expected_roi_per_unit / 3.50 * 10, 10)
    # KENP estimate based on pages (200 pages ≈ 25 KENP)
    kelp_estimate = rec.estimated_pages / 8  # rough conversion
    engagement_component = min(kelp_estimate / 25 * 10, 10)
    market_component = 7.0  # placeholder
    
    return roi_component * 0.4 + engagement_component * 0.3 + market_component * 0.3


if __name__ == "__main__":
    # Allow config override via environment or CLI
    import os
    
    config_path = Path(os.environ.get('PLANNER_CONFIG', '/home/bookforge/.hermes/hermes_skills/planner/config.yaml'))
    # Canonical LEARNING.md — single source of truth for the whole factory
    learning_md_path = Path(os.environ.get('LEARNING_MD_PATH', '/home/bookforge/books/factory/LEARNING.md'))
    output_path = Path(os.environ.get('OUTPUT_PATH', '/home/bookforge/.hermes/output/planner/topic_plan_latest.md'))
    dry_run = os.environ.get('DRY_RUN', 'false').lower() == 'true'
    
    results = run_planner(
        config_path=config_path,
        learning_md_path=learning_md_path,
        output_path=output_path,
        dry_run=dry_run
    )
    
    if 'error' in results:
        sys.exit(1)
    
    print("✅ Planner completed successfully")
