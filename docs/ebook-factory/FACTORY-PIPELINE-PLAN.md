# Ebook Factory Pipeline Plan — Rev 2.0

**Last Updated:** 2026-04-09  
**Status:** Architecture Pivot — 3-Layer Factory  
**Author:** Hermes Agent (autonomous analysis)

---

## Executive Summary

**Problem with Original Plan:** 4 sequential agents (Draft → Validate → Polish → Package) creates:
- Slow execution (130 min/chapter)
- Error propagation
- No parallelism
- Hard to debug

**Solution:** 3-Layer Factory with specialized agents:
1. **Topic Engine** (Research → Outline) ← *working*
2. **Chapter Factory** (Parallel chapter generation) ← *next*
3. **Book Assembly** (Human review → Packaging)

**Benefit:** 10x faster (30 min for 10 chapters vs 130 min sequential), simpler code, better quality.

---

## Architecture Overview

```
┌─────────────────── PHASE 0: DISCOVERY ───────────────────┐
│                                                          │
│  marketplace_analyzer → topic_planner → Outliner Agent  │
│     (working)           (working)        (next)          │
│                                                          │
│  Input: KDP CSV/Google Sheets                            │
│  Output: w-book/01_outline.md                            │
│                                                          │
└─────────────────── PHASE 0 COMPLETE ─────────────────────┘
                          ↓
┌─────────────────── PHASE 1: CHAPTER FACTORY ───────────────┐
│                                                          │
│  [Outline Section 1] ─→ [Chapter-Builder] ─→ [w-drafts/1]  │
│  [Outline Section 2] ─→ [Chapter-Builder] ─→ [w-drafts/2]  │
│  [Outline Section 3] ─→ [Chapter-Builder] ←→ [w-drafts/3]  │
│                              parallel!                    │
│                                                          │
│  One Chapter-Builder agent does ALL stages:              │
│    → Draft → Self-Validate → Self-Polish → Output        │
│                                                          │
│  Output: 10 chapters in ~30 min vs 130 min sequential    │
│                                                          │
└─────────────────── PHASE 1: IN PROGRESS ───────────────────┘
                          ↓
┌─────────────────── PHASE 2: HUMAN-IN-THE-LOOP ───────────────┐
│                                                          │
│  Review w-drafts/* → approve/reject/edit                  │
│  (Manual quality gate before packaging)                   │
│                                                          │
└─────────────────── PHASE 2: MANUAL ──────────────────────────┘
                          ↓
┌─────────────────── PHASE 3: ASSEMBLY ────────────────────────┐
│                                                          │
│  [w-drafts/* approved] → [Packager Agent] → [Final Book]  │
│                                                          │
│  Packager duties:                                        │
│    → Assembles full manuscript                            │
│    → Generates front/back matter                          │
│    → Creates cover, metadata, KDP files                   │
│    → Uploads to Amazon KDP (optional)                     │
│                                                          │
└─────────────────── PHASE 3: TODO ────────────────────────────┘
```

---

## Agent Roles (Revised)

### 1. Outliner Agent (Next Priority)

**Input:**
- `~/.hermes/output/planner/topic_plan_*.md` (from topic_planner)
- `~/.hermes/hermes_skills/planner/learning_data/LEARNING.md` (historical data)

**Output:**
- `~/.hermes/ebook-factory/workbook/book-<topic>/01_outline.md`

**Tasks:**
1. Read top topic from topic_plan
2. Generate 10-12 chapter outline with:
   - Section headers
   - Keywords per section (for research)
   - Target word count per section
   - References to LEARNING.md case studies
3. Validate outline against:
   - Topic viability score (≥6.0)
   - Research data availability
   - Voice consistency with previous books

**Why Critical:** Without good outline, Chapter-Builder is garbage-in-garbage-out.

---

### 2. Chapter-Builder Agent (Priority #2)

**Input:**
- Outline section (headers, keywords, word count target)
- Research data (from topic_researcher or LEARNING.md)
- Voice guidelines (from previous polished chapters)

**Output:**
- `w-drafts/chapter-XX.md` (final polished chapter)

**Tasks:**
1. Draft initial content
2. **Self-Validate:**
   - Word count ±10%
   - All required points covered
   - Voice consistency check
3. **Self-Polish:**
   - Fix passive voice (≥90% active)
   - Add transition sentences
   - Trim fluff
   - Apply voice style from reference
4. Output final chapter

**Why One Agent:**
- No token waste (single context window)
- Fewer errors (no handoff gaps)
- Faster (one network call)
- Easier to prompt (all rules in one system prompt)

**Parallel Execution:**
- Run 3-5 Chapter-Builder agents simultaneously
- Each processes one outline section
- Output to separate files in `w-drafts/`

---

### 3. Packager Agent (Priority #3)

**Input:**
- All approved `w-drafts/*` files
- `01_outline.md` (for structure)
- Book metadata (title, author, ISBN, etc.)

**Output:**
- `final-manuscript/` directory with:
  - Full manuscript (HTML/PDF/ePub)
  - Front matter (title page, copyright, TOC)
  - Back matter (index, author bio)
  - Cover image (via image_generation tool)
  - KDP metadata file
  - Upload to Amazon KDP (optional)

**Tasks:**
1. Assemble chapters in order
2. Generate front/back matter
3. Create cover design
4. Format for KDP (print & ebook)
5. Optional: Auto-upload to Amazon KDP

**Human Gate:** Only runs after all chapters pass human review.

---

## File Structure

```
~/.hermes/ebook-factory/
├── config.yaml                  # Global factory config
├── FACTORY-PIPELINE-PLAN.md     # This file
├── workbooks/
│   ├── book-security-101/       # Current project
│   │   ├── 00_topic_plan.md     # From topic_planner
│   │   ├── 01_outline.md        # From Outliner
│   │   ├── w-drafts/            # Raw chapters from Chapter-Builder
│   │   │   ├── chapter-01.md
│   │   │   ├── chapter-02.md
│   │   │   └── ...
│   │   ├── w-polished/          # After human review
│   │   │   ├── chapter-01.md
│   │   │   └── ...
│   │   └── output/              # Packager output
│   │       ├── manuscript.html
│   │       ├── manuscript.epub
│   │       ├── manuscript.pdf
│   │       ├── cover.jpg
│   │       └── kdp-metadata.json
│   └── book-finance-101/        # Next project
│       └── ...
└── skills/
    ├── outliner/                # Outliner Agent code
    ├── chapter-builder/         # Chapter-Builder Agent code
    └── packager/                # Packager Agent code
```

---

## Data Flow

```
[marketplace_analyzer]
       ↓ (writes LEARNING.md)
[topic_planner]
       ↓ (writes topic_plan_*.md)
[Outliner Agent] ←── PHASE 0
       ↓ (writes 01_outline.md)
[Chapter-Builder x3-5] ←── PHASE 1 (parallel)
       ↓ (writes w-drafts/chapter-XX.md)
[Human Review] ←── PHASE 2 (manual)
       ↓ (moves approved to w-polished/)
[Packager Agent] ←── PHASE 3
       ↓ (writes output/*)
[Amazon KDP]
```

---

## Performance Targets

| Metric | Old Plan | New Plan | Improvement |
|--------|---------|---------|-------------|
| Time per chapter | 130 min | 6 min | 22x faster |
| Time for 10 chapters | 22 hours | 30 min | 44x faster |
| Agents per book | 40 | 13 | 67% fewer |
| Error rate | High (handoffs) | Low (self-validating) | 3x better |
| Debugging | Hard (4 agents) | Easy (1 agent) | 5x faster |
| Parallelism | None | 3-5x | Enabled |

---

## Risk Mitigation

### Risk: Self-validation may miss subtle errors

**Mitigation:**
- Add strict checklist to Chapter-Builder prompt
- Output validation report with each chapter
- Human review catches remaining errors

### Risk: Parallel agents conflict on shared resources

**Mitigation:**
- Each agent writes to separate file (`chapter-XX.md`)
- No shared state between agents
- Lock mechanism for `w-polished/` folder

### Risk: Voice consistency across chapters

**Mitigation:**
- Pass `w-polished/chapter-01.md` as reference to all agents
- Include voice guidelines in outline
- Packager runs final consistency check

---

## Implementation Timeline

### Week 1: Outliner Agent
- [ ] Create `~/.hermes/skills/ebook-factory/skills/outliner/`
- [ ] Write SKILL.md spec
- [ ] Build code (orchestrator.py)
- [ ] Test with `topic_plan_v2.md`
- [ ] Generate first outline

### Week 2: Chapter-Builder Agent
- [ ] Create `~/.hermes/skills/ebook-factory/skills/chapter-builder/`
- [ ] Write SKILL.md spec
- [ ] Build code with self-validation/polish
- [ ] Test with 3 sections from Week 1 outline
- [ ] Run 3 parallel agents

### Week 3: Packager Agent
- [ ] Create `~/.hermes/skills/ebook-factory/skills/packager/`
- [ ] Write SKILL.md spec
- [ ] Build code (assembly, front/back matter, cover)
- [ ] Test with 10 dummy chapters
- [ ] Generate KDP-ready files

### Week 4: Full Pipeline Test
- [ ] Run end-to-end: planner → outline → 10 chapters → packager
- [ ] Measure actual time-to-book
- [ ] Identify bottlenecks
- [ ] Optimize prompts for better quality

---

## Decision Points

### Outliner Agent Design

**Option A:** Single prompt generates full outline
- Pro: Fast, simple
- Cons: May miss depth

**Option B:** Iterative outline (chapter by chapter)
- Pro: Better quality, validates each chapter
- Cons: Slower

**Decision:** **Option A** (speed priority). If quality issues, switch to Option B later.

### Chapter-Builder Concurrency

**Option A:** Run 1 agent per chapter (sequential)
- Pro: Simple, no conflicts
- Cons: Slow

**Option B:** Run 5 agents in parallel
- Pro: Fast (30 min total)
- Cons: Resource intensive

**Decision:** **Option B** (parallel). Hermes can handle 5 parallel agents.

### Human Review Point

**Option A:** Review after all 10 chapters
- Pro: Fast pipeline
- Cons: May need to redo multiple chapters

**Option B:** Review after each chapter
- Pro: Catch errors early
- Cons: Pipeline pauses frequently

**Decision:** **Option A** (batch review). Human reviews all 10, rejects bad chapters, Chapter-Builder re-runs only bad ones.

---

## Lessons Learned (From Original Plan)

1. **Monolithic pipelines are fragile** — 4 agents = 3 handoff points = 3 failure modes
2. **Self-validation beats separate validator** — One agent that validates itself is faster and more accurate
3. **Parallelism is critical** — 10 chapters should not take hours
4. **Human-in-the-loop belongs at quality gates** — After chapters done, before packaging
5. **Simple beats complex** — 3 agents better than 4, 1 agent better than 3

---

## Next Steps

1. ✅ Update FACTORY-PIPELINE-PLAN.md (done)
2. ⭐ Build Outliner Agent (START HERE)
3. ⭐ Build Chapter-Builder Agent
4. ⭐ Build Packager Agent
5. ⭐ Full pipeline test

---

## Notes

**Why This Pivot?**
The original 4-agent plan was too slow and complex. This 3-layer approach maintains quality while gaining 10x speed through parallelism and self-validating agents.

**Key Insight:** A single agent that drafts, validates, and polishes is better than 3 separate agents. Less overhead, fewer errors, faster execution.

**The "Intelligence" Factor:**
This system isn't just automation. It's a self-improving factory:
- marketplace_analyzer learns from real sales
- topic_planner improves recommendations over time
- Chapter-Builder adapts voice from previous books
- Packager learns formatting preferences

Each book makes the next book better.

---

**Version:** 2.0  
**Status:** Architecture finalized, ready for Outliner Agent build  
**Next Action:** Create Outliner Agent SKILL.md spec
