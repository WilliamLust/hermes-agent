"""
Topic Generator — Generates specific book topic recommendations from scored niches.
"""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import re


@dataclass
class TopicRecommendation:
    """A recommended book topic."""
    niche: str
    topic_name: str
    suggested_title: str
    unique_angle: str
    target_audience: str
    competitive_advantage: str
    expected_roi_per_unit: float
    estimated_pages: int
    validation_notes: List[str]


def generate_topic_recommendations(
    scored_niches: List[tuple],  # [(niche, score, details), ...]
    learning_entries: List[Dict],
    config: Dict,
    historical: Optional[Dict[str, Any]] = None
) -> List[TopicRecommendation]:
    """
    Generate topic recommendations from scored niches.
    
    Args:
        scored_niches: List of (niche, score, details) tuples
        learning_entries: Raw entries from LEARNING.md
        config: Configuration dict
        historical: Optional historical marketplace data
    
    Returns:
        List of TopicRecommendation objects
    """
    max_topics = config.get('generation', {}).get('max_topics', 5)
    include_competitors = config.get('generation', {}).get('include_competitors', True)
    include_angle = config.get('generation', {}).get('include_angle', True)
    
    recommendations = []
    
    for niche_name, score, details in scored_niches[:max_topics]:
        if score < 4.0:  # Minimum viable score
            continue
        
        # Extract relevant entries for this niche
        niche_entries = [e for e in learning_entries 
                        if e['metrics'].get('niche') == niche_name]
        
        # Extract historical data for this niche (if available)
        niche_historical = None
        if historical and historical.get('has_data'):
            historical_lookup = {
                item['niche'].lower(): item 
                for item in historical['top_niches']
            }
            niche_lower = niche_name.lower()
            if niche_lower in historical_lookup:
                niche_historical = historical_lookup[niche_lower]
        
        # Generate topic
        rec = generate_single_topic(
            niche_name=niche_name,
            score=score,
            details=details,
            entries=niche_entries,
            include_competitors=include_competitors,
            include_angle=include_angle,
            historical=niche_historical
        )
        
        if rec:
            recommendations.append(rec)
            
    return recommendations


def generate_single_topic(
    niche_name: str,
    score: float,
    details: Dict,
    entries: List[Dict],
    include_competitors: bool,
    include_angle: bool,
    historical: Optional[Dict] = None
) -> TopicRecommendation:
    """Generate a single topic recommendation."""
    
    # Derive topic name from niche
    topic_name = niche_name.replace('-', ' ').title()
    
    # Generate suggested title
    suggested_title = derive_suggested_title(niche_name, entries, historical)
    
    # Generate unique angle
    unique_angle = derive_unique_angle(niche_name, entries, historical) if include_angle else ""
    
    # Target audience
    target_audience = derive_target_audience(niche_name)
    
    # Competitive advantage
    competitive_advantage = derive_competitive_advantage(niche_name, details, historical)
    
    # Expected ROI
    expected_roi = details.get('avg_royalty_per_unit', 3.0)
    
    # Estimated pages (based on KENP data)
    estimated_pages = int(details.get('avg_kenp_per_unit', 200) * 1.2)  # 20% buffer
    
    # Validation notes
    validation_notes = []
    if details.get('book_count', 0) >= 3:
        validation_notes.append(f"✅ {details['book_count']}+ books already in this niche")
    if expected_roi >= 3.50:
        validation_notes.append(f"✅ Strong ROI: ${expected_roi:.2f}/unit")
    if details.get('avg_kenp_per_unit', 0) >= 25:
        validation_notes.append(f"✅ High engagement: {details['avg_kenp_per_unit']:.1f} KENP/unit")
    else:
        validation_notes.append(f"⚠️ Low engagement detected ({details['avg_kenp_per_unit']:.1f} KENP/unit)")
    
    return TopicRecommendation(
        niche=niche_name,
        topic_name=topic_name,
        suggested_title=suggested_title,
        unique_angle=unique_angle,
        target_audience=target_audience,
        competitive_advantage=competitive_advantage,
        expected_roi_per_unit=expected_roi,
        estimated_pages=estimated_pages,
        validation_notes=validation_notes
    )


def derive_suggested_title(niche_name: str, entries: List[Dict], historical: Optional[Dict] = None) -> str:
    """Derive a suggested book title based on niche and past entries."""
    
    # Base title templates by niche
    templates = {
        'tech-security': "The No-BS Guide to {topic}: {subtopic} without the jargon",
        'tech-programming': "Practical {topic}: Real-World {subtopic} for Developers",
        'productivity': "The {topic} Blueprint: {subtopic} in 30 Days",
        'business-strategy': "The {topic} Playbook: {subtopic} for Entrepreneurs",
        'health-wellness': "The {topic} Reset: {subtopic} for Modern Life",
        'other': "The Complete Guide to {topic}: {subtopic}"
    }
    
    template = templates.get(niche_name, templates['other'])
    
    # Extract keywords from niche name
    topic = niche_name.replace('-', ' ').title()
    subtopic = extract_subtopic_from_entries(entries, niche_name)
    
    # Enhance with historical data if available
    if historical and historical.get('avg_roi', 0) >= 0.35:
        subtopic = f"{subtopic} (Proven High-ROI)"
    
    return template.format(topic=topic, subtopic=subtopic)


def extract_subtopic_from_entries(entries: List[Dict], niche_name: str) -> str:
    """Extract a subtopic based on existing entries in the niche."""
    
    if not entries:
        return "Essentials"
    
    # Simple heuristic: find common words in titles
    all_words = []
    for entry in entries:
        title = entry['title'].lower()
        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'to', 'for', 'of', 'and', 'guide', 'book', 'how', 'to'}
        words = [w for w in title.split() if w not in stop_words and len(w) > 3]
        all_words.extend(words)
    
    # Most common word (simple heuristic)
    from collections import Counter
    if all_words:
        counter = Counter(all_words)
        most_common = counter.most_common(3)
        if most_common:
            return f"{most_common[0][0].title()} Mastery"
    
    return "Essentials"


def derive_unique_angle(niche_name: str, entries: List[Dict], historical: Optional[Dict] = None) -> str:
    """Derive a unique angle for the book."""
    
    # Check historical performance first
    if historical:
        avg_roi = historical.get('avg_roi', 0)
        avg_kenp = historical.get('avg_kenp', 0)
        listing_count = historical.get('listing_count', 0)
        
        if avg_roi >= 0.35:
            return "Leverages proven high-ROI market dynamics with refined positioning"
        
        if avg_kenp >= 30:
            return "Capitalizes on high engagement patterns with premium content delivery"
        
        if listing_count <= 5 and avg_roi >= 0.25:
            return "First-mover advantage in emerging niche with strong ROI potential"
    
    patterns = []
    for entry in entries:
        patterns.extend(entry.get('patterns', []))
    
    # Check for common patterns
    pattern_text = ' '.join([p.get('text', '') for p in patterns]).lower()
    
    if 'low engagement' in pattern_text or 'kenp' in pattern_text:
        return "Shorter, action-oriented format with immediate value delivery"
    
    if 'marketplace' in pattern_text:
        return "Regional focus with localized examples and case studies"
    
    if 'below target' in pattern_text:
        return "Premium positioning with advanced concepts and exclusive insights"
    
    # Default angle based on niche
    angles = {
        'tech-security': "Beginner-friendly security without computer science prerequisites",
        'tech-programming': "Project-based learning with real-world code examples",
        'productivity': "Evidence-based methods backed by scientific research",
        'business-strategy': "Case study-driven approach with measurable outcomes"
    }
    
    return angles.get(niche_name, "Practical, step-by-step approach with real-world examples")


def derive_target_audience(niche_name: str) -> str:
    """Derive target audience based on niche."""
    
    audiences = {
        'tech-security': "Small business owners, home users, IT beginners",
        'tech-programming': "Junior developers, career switchers, self-taught programmers",
        'productivity': "Busy professionals, entrepreneurs, students",
        'business-strategy': "Startup founders, small business owners, aspiring entrepreneurs",
        'health-wellness': "Busy adults seeking sustainable health improvements"
    }
    
    return audiences.get(niche_name, "General readers seeking practical solutions")


def derive_competitive_advantage(niche_name: str, details: Dict, historical: Optional[Dict] = None) -> str:
    """Derive competitive advantage based on performance metrics."""
    
    roi = details.get('avg_royalty_per_unit', 0)
    kelp = details.get('avg_kenp_per_unit', 0)
    book_count = details.get('book_count', 0)
    
    advantages = []
    
    # Historical data advantages
    if historical:
        hist_roi = historical.get('avg_roi', 0)
        hist_kenp = historical.get('avg_kenp', 0)
        
        if hist_roi >= 0.35:
            advantages.append(f"Marketplace-validated: ${hist_roi*100:.0f} avg ROI proven")
        
        if hist_kenp >= 30:
            advantages.append(f"High engagement proven: {hist_kenp:.0f} KENP/unit marketplace average")
    
    # Current data advantages
    if roi >= 3.50:
        advantages.append("Proven high-ROI topic with strong monetization")
    
    if kelp >= 25:
        advantages.append("High reader engagement indicates strong content-market fit")
    
    if book_count >= 3:
        advantages.append("Established market demand with room for differentiation")
    elif book_count < 3:
        advantages.append("First-mover advantage in emerging sub-niche")
    
    # Add niche-specific advantage
    niche_advantages = {
        'tech-security': "Simplifies complex security concepts for non-technical audiences",
        'tech-programming': "Focuses on practical skills over theory",
        'productivity': "Science-backed methods vs. generic advice"
    }
    
    if niche_name in niche_advantages:
        advantages.append(niche_advantages[niche_name])
    
    return "; ".join(advantages) if advantages else "General market appeal"
