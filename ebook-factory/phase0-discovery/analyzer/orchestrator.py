"""
Analyzer Module - KDP Data Analysis Pipeline

Main skill module for analyzing Amazon KDP sales data and writing
structured insights to LEARNING.md.

Usage:
    python -c "from hermes_skills.analyzer import run_analysis; run_analysis()"

Or via run_analysis.sh wrapper.
"""

from pathlib import Path
import json
import yaml
import sys
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from analyzer.parser import parse_all_kdp_files
from analyzer.metrics import (
    calculate_per_book_metrics,
    aggregate_metrics_by_niche,
    detect_patterns
)
from analyzer.learner import (
    format_learning_entry,
    append_to_learning_md,
    generate_summary_report
)


def load_config(config_path: Path) -> dict:
    """Load analyzer configuration from config.yaml."""
    if not config_path.exists():
        print(f"⚠ Config not found: {config_path}")
        return {}
    
    with open(config_path) as f:
        return yaml.safe_load(f)


def run_analysis(
    config_path: Path = Path("/home/bookforge/.hermes/hermes_skills/analyzer/config.yaml"),
    kdp_directory: Path = None,
    learning_md_path: Path = None,
    dry_run: bool = False,
) -> dict:
    """
    Run the full KDP analysis pipeline.
    
    Args:
        config_path: Path to config.yaml
        kdp_directory: Override KDP download directory
        learning_md_path: Override LEARNING.md path
        dry_run: If True, don't write to LEARNING.md
    
    Returns:
        Analysis results dict
    """
    # Load configuration
    config = load_config(config_path)
    
    # Override parameters if provided
    kdp_directory = kdp_directory or Path(config.get('kdp_directory', '/home/bookforge/Downloads'))
    learning_md_path = learning_md_path or Path(config.get('learning_md_path', '/home/bookforge/books/factory/LEARNING.md'))
    
    print(f"📊 KDP Analysis Pipeline")
    print(f"   KDP Directory: {kdp_directory}")
    print(f"   LEARNING.md: {learning_md_path}")
    print(f"   Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}")
    print()
    
    # Phase 1: Parse KDP files
    print("@e1⚡ Phase 1: Parsing KDP files...")
    
    kdp_data = parse_all_kdp_files(kdp_directory)
    
    if not kdp_data['all_books']:
        print("❌ No book data found in KDP files.")
        print(f"   Checked: {kdp_directory}")
        return {'error': 'No book data found'}
    
    all_books = kdp_data['all_books']
    all_kenp = kdp_data['all_kenp']
    
    print(f"   ✓ Found {len(all_books)} book records")
    print(f"   ✓ Found {len(all_kenp)} KENP records")
    print()
    
    # Phase 2: Calculate metrics
    print("@e2⚡ Phase 2: Calculating per-book metrics...")
    
    metrics_list = calculate_per_book_metrics(all_books, all_kenp)
    aggregates = aggregate_metrics_by_niche(metrics_list)
    
    print(f"   ✓ Analyzed {len(metrics_list)} books across {len(aggregates)} niche(s)")
    print()
    
    # Phase 3: Detect patterns
    print("@e3⚡ Phase 3: Detecting patterns...")
    
    patterns = detect_patterns(metrics_list, aggregates)
    
    print(f"   ✓ Detected {len(patterns)} patterns")
    for pattern in patterns[:3]:
        print(f"     - {pattern['pattern_type']}: {pattern['description'][:60]}...")
    print()
    
    # Phase 4: Write to LEARNING.md
    if not dry_run:
        print("@e4📝 Phase 4: Writing to LEARNING.md...")
        
        # Generate entries for each book
        entries = []
        for book in metrics_list:
            entry = format_learning_entry(book, book['metrics'], patterns)
            entries.append(entry)
        
        # Generate summary report
        summary = generate_summary_report(aggregates, patterns, len(metrics_list))
        entries.append(summary)
        
        # Append to LEARNING.md
        append_to_learning_md(learning_md_path, entries)
    else:
        print("ℹ️ Dry run — skipped writing to LEARNING.md")
    
    # Generate final report
    print()
    print("═╤══════════════════════════")
    print("📊 Analysis Complete")
    print(f"   Books analyzed: {len(metrics_list)}")
    print(f"   Niches detected: {len(aggregates)}")
    print(f"   Patterns found: {len(patterns)}")
    print(f"   LEARNING.md: {learning_md_path}")
    print("═╤══════════════════════════")
    print()
    
    # Return results for programmatic access
    return {
        'books_analyzed': len(metrics_list),
        'niches': len(aggregates),
        'patterns': patterns,
        'aggregates': aggregates,
        'metrics_list': metrics_list,
        'learning_md_path': str(learning_md_path)
    }


def display_quick_summary(metrics_list: list, aggregates: dict, patterns: list):
    """Display a quick summary to stdout."""
    print("═╤══════════════════════════")
    print("Quick Summary")
    print("═╤══════════════════════════")
    
    # Per-niche breakdown
    print("\nNiche Performance:")
    for niche, data in sorted(aggregates.items(), key=lambda x: x[1]['avg_royalty_per_unit'], reverse=True):
        print(f"  {niche:20s} ${data['avg_royalty_per_unit']:6.2f}/unit  "
              f"{data['book_count']:2d} books  "
              f"{data['avg_keng_per_unit']:6.1f} KENP/unit")
    
    # Top patterns
    if patterns:
        print("\nTop Patterns:")
        for i, pattern in enumerate(patterns[:5], 1):
            print(f"  {i}. {pattern['description'][:60]}...")
    
    print("═╤══════════════════════════")


if __name__ == "__main__":
    # Allow config override via environment or CLI
    import os
    
    config_path = Path(os.environ.get('ANALYZER_CONFIG', '/home/bookforge/.hermes/hermes_skills/analyzer/config.yaml'))
    kdp_dir = Path(os.environ.get('KDP_DIR', '/home/bookforge/Downloads'))
    # Canonical LEARNING.md — single source of truth for the whole factory
    learning_path_env = os.environ.get('LEARNING_PATH', '')
    learning_path = Path(learning_path_env) if learning_path_env else Path('/home/bookforge/books/factory/LEARNING.md')
    dry_run = os.environ.get('DRY_RUN', 'false').lower() == 'true'
    
    results = run_analysis(
        config_path=config_path,
        kdp_directory=kdp_dir,
        learning_md_path=learning_path,
        dry_run=dry_run,
    )
    
    if 'error' in results:
        sys.exit(1)
    
    display_quick_summary(
        results['metrics_list'],
        results['aggregates'],
        results['patterns']
    )
