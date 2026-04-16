#!/usr/bin/env python3
"""
Outliner Agent — Run via `hermes run_skill outliner`

Transforms topic_plan output into production-ready book outline.

Usage:
    hermes run_skill outliner                    # Auto-selects top topic
    hermes run_skill outliner --topic <title>    # Specify topic
    hermes run_skill outliner --chapters 12      # Custom chapter count
"""

import os
import sys
import json
import re
import argparse
from pathlib import Path
from datetime import datetime

# ======================================================================
# CONFIGURATION
# ======================================================================

HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
WORKBOOKS_DIR = HERMES_HOME / "ebook-factory" / "workbooks"
TOPIC_PLANS_DIR = HERMES_HOME / "output" / "planner"
LEARNING_FILE = HERMES_HOME / "hermes_skills" / "planner" / "learning_data" / "LEARNING.md"

# ======================================================================
# HELPER FUNCTIONS
# ======================================================================

def log_step(step: str) -> None:
    """Print colored step indicator."""
    print(f"\n📌 {step}")

def error_exit(message: str) -> None:
    """Print error and exit."""
    print(f"\n❌ ERROR: {message}")
    sys.exit(1)

def warning(message: str) -> None:
    """Print warning."""
    print(f"\n⚠️  WARNING: {message}")

def slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    return text

def read_file_content(filepath: Path) -> str:
    """Read file content."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        error_exit(f"Failed to read {filepath}: {e}")

def write_file_content(filepath: Path, content: str) -> None:
    """Write file content."""
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        error_exit(f"Failed to write {filepath}: {e}")

# ======================================================================
# DATA PARSING
# ======================================================================

def find_topic_plans() -> list:
    """Find all topic_plan files."""
    if not TOPIC_PLANS_DIR.exists():
        return []
    plans = list(TOPIC_PLANS_DIR.glob("topic_plan_*.md"))
    return sorted(plans, key=lambda p: p.stat().st_mtime, reverse=True)

def load_topic_plan(plan_path: Path) -> dict:
    """Load and parse topic_plan file."""
    content = read_file_content(plan_path)
    
    topics = []
    lines = content.split("\n")
    
    # Parse "Top 3 Priorities" section in Executive Summary
    # Format: "1. **Title**\n   - Score: X.XX/10"
    in_priorities = False
    current_topic = None
    
    for line in lines:
        # Detect "### Top 3 Priorities" section
        if "Top 3 Priorities" in line:
            in_priorities = True
            continue
        
        # Exit section on new header
        if in_priorities and line.startswith("###") and "Top 3 Priorities" not in line:
            in_priorities = False
            continue
        
        if in_priorities:
            # Detect numbered item: "1. **Title**"
            match = re.match(r'^\d+\.\s+\*\*(.+?)\*\*$', line.strip())
            if match:
                if current_topic:
                    topics.append(current_topic)
                current_topic = {
                    "number": len(topics) + 1,
                    "title": match.group(1).strip(),
                    "viability_score": None
                }
            # Find score line: "   - Score: 6.10/10"
            elif current_topic and "score:" in line.lower():
                score_match = re.search(r'Score:\s*(\d+\.?\d*)/10', line)
                if score_match:
                    current_topic["viability_score"] = float(score_match.group(1))
    
    # Save last topic
    if current_topic:
        topics.append(current_topic)
    
    if not topics:
        error_exit("No valid topics found in topic_plan file")
    
    # Sort by score (highest first)
    topics.sort(key=lambda t: t.get("viability_score", 0), reverse=True)
    
    return {"topics": topics, "file": str(plan_path)}

def load_learning_data() -> dict:
    """Load LEARNING.md file."""
    if not LEARNING_FILE.exists():
        return None
    
    content = read_file_content(LEARNING_FILE)
    
    # Parse learning data into sections
    data = {
        "cases": [],
        "market_insights": [],
        "voice_examples": []
    }
    
    for line in content.split("\n"):
        if "case study" in line.lower() or "example" in line.lower():
            data["cases"].append(line.strip())
        elif "market" in line.lower() or "trend" in line.lower():
            data["market_insights"].append(line.strip())
    
    return data if data["cases"] or data["market_insights"] else None

# ======================================================================
# OUTLINE GENERATION
# ======================================================================

VALIDATION_CHECKLIST = """
## Validation Checklist

- [ ] All chapters have clear objectives
- [ ] Each chapter targets realistic word count
- [ ] Every section has keywords (3-5 per section)
- [ ] LEARNING.md case studies referenced where applicable
- [ ] Topics align with topic_plan viability score
- [ ] No hallucinated facts (all claims anchorable)
"""

def generate_chapter_outline(chapter_num: int, chapter_title: str, learning_data) -> str:
    """Generate outline for a single chapter."""
    
    # Determine chapter type
    is_intro = chapter_num == 1
    is_conclusion = chapter_num == 10
    is_core = not is_intro and not is_conclusion
    
    # Generate sections based on chapter type
    if is_intro:
        sections = [
            {"title": "Introduction", "word_count": 300, "focus": "Hook + overview", "keywords": ["introduction", "overview", "beginner"], "example": "Opening scenario"},
            {"title": "Why This Matters", "word_count": 500, "focus": "Problem statement", "keywords": ["importance", "motivation", "relevance"], "example": "Market pain point"},
            {"title": "Core Concepts Overview", "word_count": 800, "focus": "Foundational theory", "keywords": ["concepts", "theory", "basics"], "example": "Key principle"},
            {"title": "Real-World Context", "word_count": 600, "focus": "Industry examples", "keywords": ["examples", "context", "industry"], "example": "Market data"},
            {"title": "Chapter Summary & Preview", "word_count": 300, "focus": "Recap + teaser", "keywords": ["summary", "key points", "next chapter"], "example": "Transition hook"},
        ]
    elif is_conclusion:
        sections = [
            {"title": "Summary of Key Learnings", "word_count": 800, "focus": "Book recap", "keywords": ["summary", "key takeaways", "lessons learned"], "example": "Synthesis"},
            {"title": "Action Plan", "word_count": 600, "focus": "Implementation steps", "keywords": ["action plan", "implementation", "next steps"], "example": "30-day plan"},
            {"title": "Common Pitfalls to Avoid", "word_count": 500, "focus": "Warnings", "keywords": ["pitfalls", "mistakes", "warnings"], "example": "Top 5 mistakes"},
            {"title": "Resources & References", "word_count": 400, "focus": "Further reading", "keywords": ["resources", "references", "further learning"], "example": "Tool list"},
            {"title": "Final Thoughts", "word_count": 200, "focus": "Closing message", "keywords": ["conclusion", "final words", "inspiration"], "example": "Call to action"},
        ]
    else:
        # Standard chapter
        sections = [
            {"title": "Chapter Introduction", "word_count": 300, "focus": "Chapter overview", "keywords": ["introduction", "chapter focus", "objectives"], "example": "Chapter hook"},
            {"title": "Core Concept 1", "word_count": 600, "focus": "Primary technique", "keywords": ["technique", "method", "approach"], "example": "Key example"},
            {"title": "Core Concept 2", "word_count": 600, "focus": "Secondary technique", "keywords": ["technique", "variation", "comparison"], "example": "Additional example"},
            {"title": "Practical Application", "word_count": 800, "focus": "Step-by-step guide", "keywords": ["application", "implementation", "how-to"], "example": "Step-by-step"},
            {"title": "Case Study", "word_count": 500, "focus": "Real-world example", "keywords": ["case study", "example", "results"], "example": "Success story"},
            {"title": "Common Mistakes & Solutions", "word_count": 400, "focus": "Troubleshooting", "keywords": ["mistakes", "solutions", "tips"], "example": "Troubleshooting guide"},
            {"title": "Chapter Summary", "word_count": 300, "focus": "Recap & transition", "keywords": ["summary", "key points", "transition"], "example": "Bridge to next"},
        ]
    
    # Enrich with LEARNING.md data if available
    if learning_data:
        cases = learning_data.get("cases", [])
        if is_core and len(cases) >= 3:
            sections[1]["example"] = cases[0]
            sections[2]["example"] = cases[1]
            sections[4]["example"] = cases[2]
    
    # Build chapter outline string
    total_words = sum(s["word_count"] for s in sections)
    
    outline = f"""## Chapter {chapter_num}: {chapter_title}

**Objective:** Teach core concepts and practical application  
**Target Audience:** Intermediate-level readers  
**Word Count Target:** {total_words} words

### Sections

"""
    
    for i, section in enumerate(sections, 1):
        outline += f"""{i}. **[{section['title']}]** (~{section['word_count']} words)
   - **Focus:** {section['focus']}
   - **Keywords:** {', '.join(section['keywords'])}
   - **Example:** {section['example']}

"""
    
    outline += "\n---\n"
    
    return outline

def generate_book_outline(topic_info: dict, learning_data: dict, num_chapters: int = 10) -> str:
    """Generate full book outline."""
    
    # Generate chapter titles based on topic
    topic_name = topic_info.get("title", "Book").split(":")[0]
    
    chapter_templates = [
        f"Introduction to {topic_name}",
        f"Why {topic_name} Matters Now",
        f"Core Principles of {topic_name}",
        f"Getting Started with {topic_name}",
        f"Advanced {topic_name} Techniques",
        f"Building Systems with {topic_name}",
        f"Optimizing {topic_name} Performance",
        f"Scaling {topic_name} for Growth",
        f"Troubleshooting {topic_name} Challenges",
        f"Mastering {topic_name}: Summary & Next Steps"
    ]
    
    chapter_titles = chapter_templates[:num_chapters]
    
    # Build outline
    outline = f"""# Book Outline: {topic_info.get('title', 'Untitled Book')}

**Source:** topic_plan_*.md  
**Generated:** {datetime.now().strftime('%Y-%m-%d')}  
**Total Chapters:** {num_chapters}  
**Estimated Word Count:** {num_chapters * 2500}-{num_chapters * 3000} words  
**Voice Style:** Professional, authoritative yet accessible

---

"""
    
    # Add all chapters
    for i, title in enumerate(chapter_titles, 1):
        outline += generate_chapter_outline(i, title, learning_data)
    
    # Add appendix
    outline += f"""
## Appendix: Research Summary

### LEARNING.md References Used
- Case study 1: {learning_data.get('cases', ['None'])[0] if learning_data and learning_data.get('cases') else 'None'}
- Case study 2: {learning_data.get('cases', ['None'])[1] if learning_data and len(learning_data.get('cases', [])) > 1 else 'None'}
- Market insight: {learning_data.get('market_insights', ['None'])[0] if learning_data and learning_data.get('market_insights') else 'None'}

### Gaps (Needs Additional Research)
- Latest market trends: Need current statistics (2025-2026)
- Case study data: May require external research

---

{VALIDATION_CHECKLIST}
"""
    
    return outline

# ======================================================================
# MAIN
# ======================================================================

def main():
    """Main entry point."""
    
    parser = argparse.ArgumentParser(description="Generate book outline from topic plan")
    parser.add_argument("--topic", type=str, help="Topic title to use")
    parser.add_argument("--chapters", type=int, default=10, help="Number of chapters")
    args = parser.parse_args()
    
    log_step("Starting Outliner Agent")
    
    # Step 1: Find topic plans
    log_step("Step 1: Finding topic plans...")
    plans = find_topic_plans()
    
    if not plans:
        error_exit("No topic_plan_*.md files found. Run topic_planner first.")
    
    plan_path = plans[0]
    log_step(f"Found: {plan_path.name}")
    
    # Step 2: Load topic plan
    log_step("Step 2: Loading topic plan...")
    topic_data = load_topic_plan(plan_path)
    
    if not topic_data.get("topics"):
        error_exit("No valid topics found in topic_plan file")
    
    # Select topic
    if args.topic:
        selected_topic = next(
            (t for t in topic_data["topics"] if args.topic.lower() in t.get("title", "").lower()),
            None
        )
        if not selected_topic:
            error_exit(f"Topic '{args.topic}' not found")
    else:
        selected_topic = topic_data["topics"][0]
    
    log_step(f"Selected topic: {selected_topic.get('title', 'Unknown')}")
    
    # Check viability
    viability = selected_topic.get("viability_score", 0)
    if viability < 6.0:
        error_exit(f"Topic viability too low ({viability:.1f} < 6.0)")
    
    log_step(f"Viability score: {viability:.1f} ✓")
    
    # Step 3: Load learning data
    log_step("Step 3: Loading LEARNING.md...")
    learning_data = load_learning_data()
    
    if learning_data:
        log_step(f"Loaded {len(learning_data.get('cases', []))} case studies")
    else:
        warning("LEARNING.md not found. Proceeding without historical data.")
    
    # Step 4: Generate outline
    log_step("Step 4: Generating outline...")
    outline = generate_book_outline(selected_topic, learning_data, args.chapters)
    
    # Step 5: Create workbook
    log_step("Step 5: Creating workbook directory...")
    topic_slug = slugify(selected_topic.get("title", "book"))
    workbook_dir = WORKBOOKS_DIR / f"book-{topic_slug}"
    workbook_dir.mkdir(parents=True, exist_ok=True)
    
    log_step(f"Workbook: {workbook_dir}")
    
    # Step 6: Write outline
    log_step("Step 6: Writing outline...")
    outline_path = workbook_dir / "01_outline.md"
    write_file_content(outline_path, outline)
    
    log_step(f"✓ Outline written to: {outline_path}")
    
    # Step 7: Validate
    log_step("Step 7: Running validation...")
    checks = [
        ("Has chapters", outline.count("## Chapter") == args.chapters),
        ("Has word counts", "Word Count Target:" in outline),
        ("Has keywords", "Keywords:" in outline),
        ("Has checklist", "Validation Checklist" in outline),
    ]
    
    all_passed = True
    for name, result in checks:
        status = "✓" if result else "✗"
        print(f"  {status} {name}")
        if not result:
            all_passed = False
    
    if all_passed:
        log_step("\n✅ OUTLINE GENERATION COMPLETE!")
        print(f"\nNext: Review {outline_path}, then run Chapter-Builder agents")
        return 0
    else:
        warning("\n⚠️  Outline created but validation failed. Review before proceeding.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
