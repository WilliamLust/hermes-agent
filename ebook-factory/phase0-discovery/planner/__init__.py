"""
Planner Skill — Topic Selection Engine

Reads LEARNING.md (from analyzer), scores niches, generates topic recommendations.
"""

from pathlib import Path
import sys

_this = Path(__file__).parent
if str(_this) not in sys.path:
    sys.path.insert(0, str(_this.parent))

from niche_scorer import read_learning_md, score_niches
from topic_generator import generate_topic_recommendations
from orchestrator import run_planner

__all__ = [
    'read_learning_md',
    'score_niches',
    'generate_topic_recommendations',
    'run_planner'
]

__version__ = '0.1.0'
