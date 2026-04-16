"""
Niche Scorer — Reads LEARNING.md and calculates viability scores for each niche.
"""

from pathlib import Path
import re
from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class NicheData:
    """Data for a single niche."""
    name: str
    book_count: int
    total_royalties: float
    avg_royalty_per_unit: float
    avg_kenp_per_unit: float
    total_units: int
    entries: List[Dict]  # Raw entries for this niche


def read_learning_md(learning_path: Path) -> Dict:
    """
    Parse LEARNING.md and extract book insights.
    
    Returns:
        Dict with:
        - 'entries': List of parsed book entries
        - 'niches': Dict of niche_name -> NicheData
    """
    if not learning_path.exists():
        return {'entries': [], 'niches': {}, 'error': 'LEARNING.md not found'}
    
    content = learning_path.read_text()
    
    # Parse individual book entries
    entries = []
    # Match from ## [date] Book: title (ASIN: xxx) to the next ## or end of file
    entry_pattern = re.compile(
        r'## \[(\d{4}-\d{2}-\d{2})\] Book: (.+?) \(ASIN: ([A-Z0-9]+)\)(.+?)(?=## \[|\Z)',
        re.DOTALL
    )
    
    for match in entry_pattern.finditer(content):
        date = match.group(1)
        title = match.group(2).strip()
        asin = match.group(3)
        body = match.group(4) or ''
        
        entry = {
            'date': date,
            'title': title,
            'asin': asin,
            'body': body
        }
        
        # Extract metrics from body
        entry['metrics'] = parse_entry_metrics(body)
        
        entries.append(entry)
    
    # Aggregate by niche
    niches = aggregate_by_niche(entries)
    
    return {
        'entries': entries,
        'niches': niches,
        'error': None
    }


def parse_entry_metrics(body: str) -> Dict:
    """Extract numeric metrics from entry body."""
    metrics = {}
    
    # Royalty — handles "$3.45", "$3.45 (USD)", "$2,760.00 (USD)"
    match = re.search(r'- \*\*Royalty:\*\*\s*\$([\d,]+\.?[\d]*)', body)
    if match:
        metrics['royalty'] = float(match.group(1).replace(',', ''))
    
    # Units
    match = re.search(r'- \*\*Units Sold:\*\*\s*(\d+)', body)
    if match:
        metrics['units'] = int(match.group(1))
    
    # KENP
    match = re.search(r'- \*\*KENP Pages:\*\*\s*(\d+)', body)
    if match:
        metrics['kenp_pages'] = int(match.group(1))
    
    # Royalty/unit
    match = re.search(r'- \*\*Royalty/unit:\*\*\s*\$(\d+\.?\d*)', body)
    if match:
        metrics['royalty_per_unit'] = float(match.group(1))
    
    # KENP/unit
    match = re.search(r'- \*\*KENP/unit:\*\*\s*(\d+\.?\d*)', body)
    if match:
        metrics['kenp_per_unit'] = float(match.group(1))
    
    # Niche
    match = re.search(r'- \*\*Niche Category:\*\*\s*(\S+)', body)
    if match:
        metrics['niche'] = match.group(1)
    
    # Niche score
    match = re.search(r'- \*\*Niche Score:\*\*\s*(\d+\.?\d*)/10', body)
    if match:
        metrics['niche_score'] = float(match.group(1))
    
    return metrics


def parse_entry_patterns(body: str) -> List[Dict]:
    """Extract patterns from entry body."""
    patterns = []
    
    # Find pattern sections
    pattern_block = re.search(
        r'### Patterns Observed\s+(.*?)(?=###|\Z)',
        body,
        re.DOTALL
    )
    
    if pattern_block:
        pattern_text = pattern_block.group(1)
        # Simple pattern extraction (one per line starting with -)
        for line in pattern_text.strip().split('\n'):
            if line.startswith('-'):
                patterns.append({'text': line.strip()[1:].strip()})
    
    return patterns


def parse_entry_recommendations(body: str) -> List[str]:
    """Extract recommendations from entry body."""
    recommendations = []
    
    # Find recommendations section
    rec_block = re.search(
        r'### Recommendations\s+(.*?)(?=###|\Z)',
        body,
        re.DOTALL
    )
    
    if rec_block:
        rec_text = rec_block.group(1)
        # Extract numbered recommendations
        for match in re.finditer(r'\d+\. (.+?)(?=\d+\.|\Z)', rec_text, re.DOTALL):
            text = match.group(1).strip()
            # Remove bullet/format chars
            text = re.sub(r'[⚠️🔍✅❓]', '', text).strip()
            recommendations.append(text)
    
    return recommendations


def aggregate_by_niche(entries: List[Dict]) -> Dict[str, NicheData]:
    """Group entries by niche and calculate aggregates."""
    niche_data: Dict[str, List[Dict]] = {}
    
    for entry in entries:
        niche = entry['metrics'].get('niche', 'unknown')
        if niche not in niche_data:
            niche_data[niche] = []
        niche_data[niche].append(entry)
    
    result = {}
    for niche, entries_list in niche_data.items():
        total_royalties = sum(e['metrics'].get('royalty', 0) for e in entries_list)
        total_units = sum(e['metrics'].get('units', 0) for e in entries_list)
        total_kenp = sum(e['metrics'].get('kenp_pages', 0) for e in entries_list)
        
        avg_royalty_per_unit = (
            total_royalties / total_units if total_units > 0 else 0
        )
        avg_kenp_per_unit = (
            total_kenp / total_units if total_units > 0 else 0
        )
        
        result[niche] = NicheData(
            name=niche,
            book_count=len(entries_list),
            total_royalties=total_royalties,
            avg_royalty_per_unit=avg_royalty_per_unit,
            avg_kenp_per_unit=avg_kenp_per_unit,
            total_units=total_units,
            entries=entries_list
        )
    
    return result


def score_niches(
    niches: Dict[str, NicheData],
    config: Dict
) -> List[Tuple[str, float, Dict]]:
    """
    Score niches based on weighted criteria.
    
    Returns list of (niche_name, score, details) sorted by score descending.
    """
    scored = []
    
    roi_weight = config.get('scoring', {}).get('roi_weight', 0.4)
    engagement_weight = config.get('scoring', {}).get('engagement_weight', 0.3)
    market_weight = config.get('scoring', {}).get('market_weight', 0.2)
    expertise_weight = config.get('scoring', {}).get('expertise_weight', 0.1)
    
    min_roi = config.get('filters', {}).get('min_roi_per_unit', 2.0)
    min_kenp = config.get('filters', {}).get('min_kenp_per_unit', 15)
    
    for niche_name, data in niches.items():
        # ROI score (0-10)
        roi_score = min(data.avg_royalty_per_unit / min_roi * 10, 10)
        
        # Engagement score (0-10)
        # Only penalize if we have actual KENP data showing low engagement.
        # If KENP/unit is 0 it likely means no KU readers yet, not poor engagement.
        if data.avg_kenp_per_unit > 0:
            engagement_score = min(data.avg_kenp_per_unit / 25 * 10, 10)
        else:
            engagement_score = 5.0  # Neutral — no data yet
        
        # Market score (0-10) — based on book count (more books = more demand)
        market_score = min(data.book_count * 2, 10)
        
        # Expertise score (0-10) — placeholder, could be user-defined
        expertise_score = 5.0
        
        # Weighted composite
        total_score = (
            roi_score * roi_weight +
            engagement_score * engagement_weight +
            market_score * market_weight +
            expertise_score * expertise_weight
        )
        
        details = {
            'roi_score': round(roi_score, 2),
            'engagement_score': round(engagement_score, 2),
            'market_score': round(market_score, 2),
            'expertise_score': round(expertise_score, 2),
            'book_count': data.book_count,
            'avg_royalty_per_unit': round(data.avg_royalty_per_unit, 2),
            'avg_kenp_per_unit': round(data.avg_kenp_per_unit, 2),
            'total_royalties': round(data.total_royalties, 2)
        }
        
        scored.append((niche_name, total_score, details))
    
    # Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)
    
    return scored
