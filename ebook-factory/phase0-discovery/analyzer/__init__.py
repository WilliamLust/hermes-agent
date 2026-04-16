"""
Analyzer Skill Package - KDP Data Analysis

Provides tools for parsing Amazon KDP reports, calculating metrics,
detecting patterns, and writing structured insights to LEARNING.md.
"""

from pathlib import Path
import sys

# Make imports work from this package
_this = Path(__file__).parent
if str(_this) not in sys.path:
    sys.path.insert(0, str(_this.parent))

from orchestrator import run_analysis, display_quick_summary
from parser import parse_all_kdp_files
from metrics import calculate_per_book_metrics, detect_patterns
from learner import format_learning_entry, append_to_learning_md

__all__ = [
    'run_analysis',
    'display_quick_summary',
    'parse_all_kdp_files',
    'calculate_per_book_metrics',
    'detect_patterns',
    'format_learning_entry',
    'append_to_learning_md'
]

__version__ = '0.1.0'
__author__ = 'BookForge Analytics'
