"""
Metrics Calculator Module

Calculates per-book and aggregate metrics for pattern detection.
"""

from typing import Dict, List, Any
from collections import defaultdict
import re

def calculate_per_book_metrics(books: List[Dict], keng_data: List[Dict]) -> List[Dict]:
    """
    Calculate metrics for each book.
    
    Returns list of books with added metrics:
    - royalty_per_unit
    - keng_per_unit
    - niche_category
    - overall_score
    """
    # Create a KENP lookup by ASIN
    kenp_lookup = {}
    for keng in keng_data:
        asin = keng.get('asin', '')
        if asin:
            if asin not in kenp_lookup:
                kenp_lookup[asin] = 0
            kenp_lookup[asin] += keng.get('kenp_pages', 0)
    
    metrics_list = []
    
    for book in books:
        asin = book.get('asin', '')
        units = book.get('units_sold', 0) or book.get('net_units', 0)
        royalty = book.get('royalty_amount', 0)
        
        # KENP for this book (by ASIN)
        keng_pages = kenp_lookup.get(asin, 0)
        
        # Calculate metrics
        royalty_per_unit = royalty / units if units > 0 else 0
        keng_per_unit = keng_pages / units if units > 0 else 0
        
        # Detect niche category
        title = book.get('title', '').lower()
        niche_category = categorize_niche(title)
        
        # Calculate overall score (0-10)
        overall_score = calculate_niche_score(royalty_per_unit, keng_per_unit, units, niche_category)
        
        # Add metrics to book record
        enriched_book = book.copy()
        enriched_book.update({
            'metrics': {
                'royalty_per_unit': royalty_per_unit,
                'kenp_per_unit': keng_per_unit,
                'kenp_total': keng_pages,
                'niche_category': niche_category,
                'overall_score': overall_score
            }
        })
        
        metrics_list.append(enriched_book)
    
    return metrics_list


def categorize_niche(title: str) -> str:
    """
    Categorize book into niche based on title keywords.
    """
    title_lower = title.lower()
    
    # Define patterns
    patterns = [
        (r'security|network|hacking|protection|cyber', 'tech-security'),
        (r'second\s*brain|productivity|organization|second\s*brain', 'productivity'),
        (r'80/20|pareto|business|strategy|results|efficiency', 'business-strategy'),
        (r'health|fitness|nutrition|workout', 'health-fitness'),
        (r'finance|money|invest|budget', 'personal-finance'),
        (r'cooking|recipe|kitchen|meal', 'cooking'),
        (r'parenting|kids|children|parent', 'parenting'),
        (r'relationship|dating|marriage|love', 'relationships'),
        (r'travel|vacation|backpacking', 'travel'),
        (r'python|code|programming|javascript', 'programming'),
        (r'meditation|mindfulness|spirituality', 'wellness'),
        (r'self-help|manifesting|abundance', 'self-help'),
    ]
    
    for pattern, category in patterns:
        if re.search(pattern, title_lower):
            return category
    
    return 'other'


def calculate_niche_score(royalty_per_unit: float, keng_per_unit: float, units: int, niche_category: str) -> float:
    """
    Calculate overall niche performance score (0-10).
    
    Weights:
    - Royalty per unit: 40%
    - KENP per unit: 30%
    - Units sold: 30%
    """
    # Normalize royalty_per_unit (target: $3.50 is 8/10)
    royalty_score = min(royalty_per_unit / 3.50 * 8, 10)
    
    # Normalize KENP per unit (target: 30 pages is 8/10)
    keng_score = min(keng_per_unit / 30 * 8, 10)
    
    # Normalize units sold (0-20 scale, 2+ units is 8/10)
    if units >= 2:
        units_score = 8
    elif units == 1:
        units_score = 5
    else:
        units_score = 0
    
    # Weighted average
    score = (royalty_score * 0.4) + (keng_score * 0.3) + (units_score * 0.3)
    
    return round(score, 2)


def aggregate_metrics_by_niche(metrics_list: List[Dict]) -> Dict[str, Dict]:
    """
    Aggregate metrics by niche category.
    
    Returns:
        {
            'tech-security': {
                'total_royalty': 2.60,
                'total_units': 1,
                'avg_royalty_per_unit': 2.60,
                'total_kenp': 28,
                'book_count': 1,
                ...
            },
            ...
        }
    """
    aggregates = defaultdict(lambda: {
        'total_royalty': 0,
        'total_units': 0,
        'total_kenp': 0,
        'books': []
    })
    
    for book in metrics_list:
        niche = book['metrics']['niche_category']
        royalty = book.get('royalty_amount', 0)
        units = book.get('units_sold', 0) or book.get('net_units', 0)
        keng_pages = book['metrics']['kenp_total']
        
        aggregates[niche]['total_royalty'] += royalty
        aggregates[niche]['total_units'] += units
        aggregates[niche]['total_kenp'] += keng_pages
        aggregates[niche]['books'].append(book)
    
    # Calculate averages
    for niche, data in aggregates.items():
        if data['total_units'] > 0:
            data['avg_royalty_per_unit'] = data['total_royalty'] / data['total_units']
            data['avg_keng_per_unit'] = data['total_kenp'] / data['total_units']
        else:
            data['avg_royalty_per_unit'] = 0
            data['avg_keng_per_unit'] = 0
        
        data['book_count'] = len(data['books'])
    
    return dict(aggregates)


def detect_patterns(metrics_list: List[Dict], aggregates: Dict[str, Dict]) -> List[Dict]:
    """
    Detect patterns across books and niches.
    
    Returns list of pattern observations with:
    - pattern_type: 'niche_performance', 'price_elasticity', 'engagement_outlier', etc.
    - description: str
    - evidence: list of book titles or metrics
    - recommendation: str
    """
    patterns = []
    
    # Pattern 1: High-performing niches
    for niche, data in aggregates.items():
        if data['avg_royalty_per_unit'] >= 3.0 and data['book_count'] >= 1:
            patterns.append({
                'pattern_type': 'strong_niche',
                'description': f"Niche '{niche}' shows strong performance",
                'evidence': [book['title'][:50] for book in data['books']],
                'metrics': {
                    'avg_royalty': data['avg_royalty_per_unit'],
                    'avg_keng': data['avg_keng_per_unit']
                },
                'recommendation': f"Prioritize similar {niche} topics for next books"
            })
    
    # Pattern 2: High engagement outliers (KENP > 25 pages/unit)
    for book in metrics_list:
        if book['metrics']['kenp_per_unit'] >= 25:
            patterns.append({
                'pattern_type': 'high_engagement',
                'description': f"Book has unusually high reader engagement",
                'evidence': [book['title']],
                'metrics': {
                    'kenp_per_unit': book['metrics']['kenp_per_unit']
                },
                'recommendation': f"Analyze content structure of '{book['title'][:40]}...' for engagement drivers"
            })
    
    # Pattern 3: Consistent royalty per unit (price optimization)
    royalty_values = [book.get('royalty_amount', 0) for book in metrics_list if book.get('royalty_amount', 0) > 0]
    if len(royalty_values) >= 2:
        avg_royalty = sum(royalty_values) / len(royalty_values)
        std_dev = (sum((r - avg_royalty) ** 2 for r in royalty_values) / len(royalty_values)) ** 0.5
        if std_dev < 0.10:  # Low variance = consistent pricing
            patterns.append({
                'pattern_type': 'pricing_consistency',
                'description': f"Consistent royalty per unit (${avg_royalty:.2f} ±${std_dev:.2f})",
                'evidence': [f"${r:.2f}" for r in royalty_values],
                'metrics': {
                    'avg_royalty': avg_royalty,
                    'std_dev': std_dev
                },
                'recommendation': "Maintain $4.99 pricing for 70% KDP Select tier"
            })
    
    # Pattern 4: Marketplace performance
    marketplaces = defaultdict(list)
    for book in metrics_list:
        mp = book.get('marketplace', 'Unknown')
        marketplaces[mp].append(book)
    
    for mp, books in marketplaces.items():
        if len(books) >= 1:
            total_royalty = sum(book.get('royalty_amount', 0) for book in books)
            patterns.append({
                'pattern_type': 'marketplace_performance',
                'description': f"Marketplace '{mp}' shows activity",
                'evidence': [book['title'][:40] for book in books],
                'metrics': {
                    'total_units': len(books),
                    'total_royalty': total_royalty
                },
                'recommendation': f"Consider localized titles for {mp}"
            })
    
    # Sort patterns by importance (high engagement first, then strong niches)
    priority = {
        'high_engagement': 1,
        'strong_niche': 2,
        'pricing_consistency': 3,
        'marketplace_performance': 4
    }
    patterns.sort(key=lambda p: priority.get(p['pattern_type'], 10))
    
    return patterns
