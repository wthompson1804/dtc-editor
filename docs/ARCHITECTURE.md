# DTC Editor System Architecture

## Overview

The DTC Editor provides two distinct editing experiences for technical documents:

| Module | Purpose | Changes | Use When |
|--------|---------|---------|----------|
| **A) Prose Linter** | DTC/AP guideline conformance | Minimal, surgical fixes | You want to keep your prose but fix style violations |
| **B) Reauthoring** | Comprehensive readability improvement | Substantive paragraph rewrites | You want to fundamentally improve readability |

Users can run **one, the other, or both sequentially**.

---

## System Architecture Diagram

```
                              USER INPUT
                                  │
                                  ▼
                    ┌─────────────────────────┐
                    │      .docx File         │
                    └───────────┬─────────────┘
                                │
                    ┌───────────▼─────────────┐
                    │    DOCX ADAPTER         │
                    │  extract_ir_and_inventory()
                    │  load_protected_terms() │
                    └───────────┬─────────────┘
                                │
                    ┌───────────▼─────────────┐
                    │     DocumentIR          │
                    │  (Intermediate Rep)     │
                    └───────────┬─────────────┘
                                │
           ┌────────────────────┼────────────────────┐
           │                    │                    │
           ▼                    ▼                    ▼
    ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
    │   MODE A    │      │   MODE B    │      │  MODE A+B   │
    │   LINTER    │      │ REAUTHORING │      │  COMBINED   │
    │   ONLY      │      │    ONLY     │      │             │
    └──────┬──────┘      └──────┬──────┘      └──────┬──────┘
           │                    │                    │
           │                    │         ┌─────────┴─────────┐
           │                    │         │                   │
           │                    │         ▼                   │
           │                    │    ┌─────────────┐          │
           │                    │    │ REAUTHORING │          │
           │                    │    │  (Stage 1)  │          │
           │                    │    └──────┬──────┘          │
           │                    │           │                 │
           │                    │           ▼                 │
           │                    │    ┌─────────────┐          │
           │                    │    │   LINTER    │          │
           │                    │    │  (Stage 2)  │          │
           │                    │    │ Style Polish│          │
           │                    │    └──────┬──────┘          │
           │                    │           │                 │
           ▼                    ▼           ▼                 │
    ┌─────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                      OUTPUT GENERATION                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ clean.docx  │  │redline.docx │  │ review.md   │          │
│  └─────────────┘  └─────────────┘  └─────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

---

## Module A: Prose Linter (Surgical Pipeline)

### Purpose
Light-touch editing that brings documents into DTC/AP style conformance without changing the author's voice or restructuring content.

### How It Works

```
DocumentIR
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                    LINT STAGE                                │
│                                                              │
│  ┌─────────────────┐  ┌─────────────────┐                   │
│  │ DTC Rules       │  │ Prose Rules     │                   │
│  │ (dtc_rules.yml) │  │ (prose_rules.yml)                   │
│  └────────┬────────┘  └────────┬────────┘                   │
│           │                    │                            │
│           └────────┬───────────┘                            │
│                    │                                        │
│  ┌─────────────────▼─────────────────┐                      │
│  │         Vale Linter               │                      │
│  │  30+ YAML rules as DETECTORS      │                      │
│  │  - Passive voice                  │                      │
│  │  - Nominalizations                │                      │
│  │  - Hedging language               │                      │
│  │  - Wordy phrases                  │                      │
│  └─────────────────┬─────────────────┘                      │
│                    │                                        │
│                    ▼                                        │
│              [Findings]                                     │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                   PROPOSE STAGE                              │
│                                                              │
│  ┌─────────────────────────────────────────┐                │
│  │ Deterministic Replacements              │                │
│  │ "in order to" → "to"                    │                │
│  │ "at this point in time" → "now"         │                │
│  │ "due to the fact that" → "because"      │                │
│  └─────────────────────────────────────────┘                │
│                                                              │
│  ┌─────────────────────────────────────────┐                │
│  │ LLM Fixes (--mode rewrite only)         │                │
│  │ For flagged prose_quality findings      │                │
│  │ Sentence-level rewrites                 │                │
│  └─────────────────────────────────────────┘                │
│                    │                                        │
│                    ▼                                        │
│               [EditOps]                                     │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                    APPLY STAGE                               │
│                                                              │
│  - Sort EditOps by position (descending)                    │
│  - Apply span-level replacements                            │
│  - Preserve document structure                              │
│  - Check protected terms not modified                       │
│                    │                                        │
│                    ▼                                        │
│            [Modified IR]                                    │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                   VERIFY STAGE                               │
│                                                              │
│  - Invariants: protected terms unchanged                    │
│  - Structure: paragraph/heading counts match                │
│  - No content loss                                          │
└─────────────────────────────────────────────────────────────┘
```

### Key DTC Rules Enforced
- "digital twin" lowercase (except "Digital Twin Consortium")
- Figure/Table captions: `Figure X-Y: Caption.`
- Title max 7 words
- APA reference format
- Proper heading hierarchy

### When To Use
- Final editorial pass before publication
- Quick conformance check
- When you want to preserve author's voice

---

## Module B: Reauthoring (Holistic Pipeline)

### Purpose
Substantive prose improvement that rewrites paragraphs for clarity and readability while preserving technical content.

### How It Works

```
DocumentIR
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                   CHUNK STAGE                                │
│                                                              │
│  Strategy Options:                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ paragraph   │  │  section    │  │  adaptive   │         │
│  │ (safest)    │  │ (coherent)  │  │ (balanced)  │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                              │
│  Each chunk includes:                                       │
│  - Main text to rewrite                                     │
│  - 100-word context window (before/after)                   │
│  - Section title for context                                │
│  - Metadata (rewritable flag, word count)                   │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                  REWRITE STAGE                               │
│                                                              │
│  ┌─────────────────────────────────────────┐                │
│  │        Claude Sonnet 4 LLM              │                │
│  │        Temperature: 0.4                 │                │
│  │        Parallel: 2 concurrent           │                │
│  └─────────────────────────────────────────┘                │
│                                                              │
│  System Prompt (Orwell-inspired):                           │
│  - Use active voice, strong verbs                           │
│  - Cut unnecessary words                                    │
│  - Avoid jargon and abstract starts                         │
│  - Preserve all technical content                           │
│  - Keep numbers, citations, references                      │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                 VALIDATE STAGE                               │
│                                                              │
│  Per-Chunk Validation (Vale as VALIDATOR):                  │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ Numbers     │  │ Citations   │  │ Protected   │         │
│  │ Preserved   │  │ Preserved   │  │ Terms       │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ Length      │  │ Vale Rules  │  │ Changes     │         │
│  │ Reasonable  │  │ Pass        │  │ Made        │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│                                                              │
│  If Vale issues found → LLM retry with feedback             │
│                                                              │
│  Decisions: ACCEPT | REVIEW | REJECT                        │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                 ASSEMBLE STAGE                               │
│                                                              │
│  - Accepted chunks → use rewritten text                     │
│  - Rejected chunks → use original text                      │
│  - Flagged chunks → configurable (auto-accept or original)  │
│  - Track acronyms across document                           │
└─────────────────────────────────────────────────────────────┘
```

### Key Innovation
**Vale rules transition from DETECTORS (surgical) to VALIDATORS (holistic).**

The LLM rewrites freely based on prose quality principles, then Vale validates the output doesn't violate style rules.

### When To Use
- Documents with dense, hard-to-read prose
- Technical papers needing readability improvement
- When substantive rewriting is acceptable

---

## Combined Mode: Holistic + Style Polish

### Purpose
Get the best of both worlds: substantive readability improvements PLUS final DTC/AP style conformance.

### How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                    STAGE 1: REAUTHORING                      │
│                                                              │
│  DocumentIR → Chunk → Rewrite → Validate → Assemble         │
│                                                              │
│  Output: Reauthored IR (improved readability)               │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  STAGE 2: STYLE POLISH                       │
│                                                              │
│  Reauthored IR → Lint → Propose → Apply → Verify            │
│                                                              │
│  - Catches style issues in assembled document               │
│  - Fixes cross-chunk style problems                         │
│  - Ensures DTC/AP conformance of LLM output                 │
│                                                              │
│  Output: Final IR (readable + conformant)                   │
└─────────────────────────────────────────────────────────────┘
```

### Why This Matters
The holistic pipeline validates per-chunk, but some issues only emerge when chunks are combined:
- Repeated acronym definitions
- Inconsistent capitalization across sections
- Style violations introduced by LLM that passed per-chunk validation

The style polish pass catches these.

---

## Module Independence

The architecture ensures **strict modularity** so each module can be improved independently:

```
┌─────────────────────────────────────────────────────────────┐
│                    SHARED LAYER                              │
│                                                              │
│  ir.py          - DocumentIR, TextBlock, Finding, EditOp    │
│  docx_adapter   - Parse/emit DOCX files                     │
│  vale_adapter   - Run Vale linter                           │
│  protected_terms - Load protected terminology               │
└─────────────────────────────────────────────────────────────┘
        │                                    │
        ▼                                    ▼
┌──────────────────────┐          ┌──────────────────────┐
│  MODULE A: LINTER    │          │  MODULE B: HOLISTIC  │
│                      │          │                      │
│  lint.py             │          │  holistic/           │
│  propose.py          │          │    chunker.py        │
│  apply.py            │          │    rewriter.py       │
│  verify.py           │          │    validator.py      │
│  rules/*.yml         │          │    orchestrator.py   │
│                      │          │    prompts.py        │
│  Entry: run_pipeline │          │                      │
│                      │          │  Entry: run_holistic_│
│                      │          │         pipeline     │
└──────────────────────┘          └──────────────────────┘
        │                                    │
        │    ┌───────────────────────────────┘
        │    │
        ▼    ▼
┌──────────────────────┐
│   STYLE POLISH       │
│   (Bridges both)     │
│                      │
│   style_polish.py    │
│   - Takes holistic   │
│     output           │
│   - Runs surgical    │
│     linter           │
│   - Returns clean IR │
└──────────────────────┘
```

### Development Independence

| If you're improving... | You can safely modify... | Without affecting... |
|------------------------|-------------------------|----------------------|
| Linter rules | `rules/*.yml`, `lint.py`, `propose.py` | Holistic pipeline |
| LLM rewriting | `holistic/rewriter.py`, `holistic/prompts.py` | Linter logic |
| Validation | `holistic/validator.py` | Proposal logic |
| Vale rules | `rules/vale/styles/` | Core pipeline code |

---

## User Interface Modes

### CLI
```bash
# Linter only (light touch)
dtc-edit doc.docx --mode safe
dtc-edit doc.docx --mode rewrite --use-llm  # with LLM fixes

# Reauthoring only (deep rewrite)
dtc-edit doc.docx --mode holistic

# Combined (deep rewrite + style polish)
dtc-edit doc.docx --mode holistic --style-polish
```

### Streamlit UI
```
┌─────────────────────────────────────────────────────────────┐
│                    DTC Editor                                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Editing Mode:                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ○ Style Conformance Only                            │   │
│  │   (Fix DTC/AP guideline violations, minimal changes)│   │
│  │                                                      │   │
│  │ ○ Readability Rewrite                               │   │
│  │   (Substantive rewrites for clarity)                │   │
│  │                                                      │   │
│  │ ● Readability + Style Polish (Recommended)          │   │
│  │   (Rewrite for clarity, then ensure conformance)    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Tradeoffs

| Approach | Pros | Cons |
|----------|------|------|
| **Linter Only** | Fast, predictable, preserves voice | Limited improvement |
| **Holistic Only** | Major readability gains | May miss some style rules |
| **Combined** | Best quality, comprehensive | Slower, higher API cost |

---

## Future Work

1. **Linter improvements** can be made in `rules/` and `lint.py` without touching holistic
2. **LLM prompt tuning** can be done in `holistic/prompts.py` independently
3. **New Vale rules** added to `rules/vale/styles/` work in both modes automatically
4. **Style polish** can be enhanced to handle specific cross-chunk issues
