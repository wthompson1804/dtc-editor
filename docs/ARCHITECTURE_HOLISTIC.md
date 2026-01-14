# Holistic Rewrite Pipeline Architecture

## Overview

This document describes the **inverted pipeline** architecture where LLM rewrites come first, and rules serve as validators rather than detectors.

## Pipeline Comparison

### Current Architecture (Surgical)
```
Document
    ↓
Extract IR (paragraphs, blocks)
    ↓
Vale DETECTS issues ──────────────┐
    ↓                             │
Rules DETECT issues ──────────────┤
    ↓                             │
LLM fixes FLAGGED sentences ←─────┘
    ↓
Apply targeted EditOps
    ↓
Output (patchwork fixes)
```

### New Architecture (Holistic)
```
Document
    ↓
Extract IR (paragraphs, blocks)
    ↓
Chunk into rewritable units
    ↓
┌─────────────────────────────────┐
│  For each chunk:                │
│    ↓                            │
│  LLM REWRITES holistically      │
│    ↓                            │
│  Validators CHECK constraints:  │
│    - Protected terms preserved? │
│    - Numbers/citations intact?  │
│    - Semantic drift detected?   │
│    - Vale rules as guardrails   │
│    ↓                            │
│  Accept / Reject / Flag         │
└─────────────────────────────────┘
    ↓
Assemble validated chunks
    ↓
Output (coherent rewrite)
```

## Core Components

### 1. Chunker (`dtc_editor/holistic/chunker.py`)

Breaks document into rewritable units with context.

```python
@dataclass
class Chunk:
    id: str
    blocks: List[TextBlock]      # The blocks to rewrite
    context_before: str          # Previous paragraph(s) for context
    context_after: str           # Following paragraph(s) for context
    section_title: str           # Current section heading
    protected_terms: Set[str]    # Terms that must be preserved

ChunkStrategy = Literal["paragraph", "section", "adaptive"]
```

**Strategies:**
- `paragraph`: One paragraph per chunk (safest, most granular)
- `section`: Full section per chunk (better coherence, higher risk)
- `adaptive`: Small paragraphs grouped, large ones split

### 2. Holistic Rewriter (`dtc_editor/holistic/rewriter.py`)

LLM-powered rewriter with strong guardrails in the prompt.

```python
@dataclass
class RewriteConfig:
    model: str = "claude-sonnet-4-20250514"
    temperature: float = 0.4
    max_tokens: int = 4096
    style_goals: List[str]       # What to improve
    constraints: List[str]       # What to preserve

@dataclass
class RewriteResult:
    chunk_id: str
    original: str
    rewritten: str
    confidence: float            # LLM's self-assessed confidence
    changes_made: List[str]      # Summary of changes
```

**Prompt Structure:**
```
SYSTEM: Editorial guidelines + absolute constraints
USER:
  - Section context: {section_title}
  - Previous: {context_before}
  - REWRITE THIS: {chunk_text}
  - Following: {context_after}
  - Protected terms: {terms}
```

### 3. Validator (`dtc_editor/holistic/validator.py`)

Post-rewrite constraint checking. Vale rules run here as guardrails.

```python
@dataclass
class ValidationConfig:
    vale_config: str
    protected_terms: Set[str]
    max_length_change: float = 0.5   # Max 50% length reduction
    require_all_numbers: bool = True
    require_all_citations: bool = True

@dataclass
class ValidationResult:
    passed: bool
    checks: Dict[str, CheckResult]   # Individual check results
    severity: Literal["ok", "warning", "error"]
    recommendation: Literal["accept", "review", "reject"]

class CheckResult:
    name: str
    passed: bool
    details: str
```

**Validation Checks:**
1. `numbers_preserved` - All numbers from original present in rewrite
2. `citations_preserved` - All Figure/Table refs preserved
3. `terms_preserved` - Protected terms not altered
4. `length_reasonable` - Not drastically shorter (content loss)
5. `vale_critical` - No critical Vale errors introduced
6. `semantic_similarity` - Embedding similarity above threshold (optional)

### 4. Orchestrator (`dtc_editor/holistic/orchestrator.py`)

Coordinates the full pipeline with parallel processing.

```python
@dataclass
class HolisticPipelineConfig:
    chunk_strategy: ChunkStrategy = "paragraph"
    max_parallel: int = 4
    auto_accept_threshold: float = 0.95
    require_human_review: bool = True

@dataclass
class PipelineResult:
    original_ir: DocumentIR
    rewritten_ir: DocumentIR
    chunk_results: List[ChunkResult]
    stats: PipelineStats

@dataclass
class ChunkResult:
    chunk: Chunk
    rewrite: RewriteResult
    validation: ValidationResult
    decision: Literal["accepted", "rejected", "flagged"]
    final_text: str              # Either rewritten or original
```

**Flow:**
```python
def run_holistic_pipeline(ir: DocumentIR, config: HolisticPipelineConfig) -> PipelineResult:
    # 1. Chunk the document
    chunks = chunk_document(ir, config.chunk_strategy)

    # 2. Parallel rewrite all chunks
    rewrites = parallel_rewrite(chunks, config.max_parallel)

    # 3. Validate each rewrite
    validations = [validate(r) for r in rewrites]

    # 4. Make accept/reject decisions
    decisions = [decide(v, config) for v in validations]

    # 5. Assemble final document
    final_ir = assemble(ir, decisions)

    return PipelineResult(...)
```

### 5. Diff Generator (`dtc_editor/holistic/diff.py`)

Generates human-readable diffs for review.

```python
@dataclass
class DiffBlock:
    chunk_id: str
    original: str
    rewritten: str
    changes: List[Change]        # Semantic changes detected
    recommendation: str

def generate_review_document(results: List[ChunkResult]) -> str:
    """Generate markdown document for human review."""
```

## File Structure

```
dtc_editor/
  holistic/
    __init__.py
    chunker.py          # Document chunking strategies
    rewriter.py         # LLM holistic rewriter
    validator.py        # Post-rewrite validation
    orchestrator.py     # Pipeline coordination
    diff.py             # Diff generation for review
    prompts.py          # Holistic rewrite prompts
```

## CLI Integration

```bash
# New mode: holistic
dtc-edit document.docx --mode holistic --use-llm --anthropic-api-key KEY

# Options
--chunk-strategy paragraph|section|adaptive
--auto-accept              # Accept all passing validations without review
--review-file review.md    # Output review document for human approval
--confidence-threshold 0.9 # Min confidence to auto-accept
```

## Validation as Guardrails (Key Insight)

The fundamental shift: **Vale rules change from DETECTORS to VALIDATORS**.

### Current Role (Detector)
```yaml
# Vale finds this and triggers LLM fix
NounStack:
  message: "Dense noun phrase detected"
  action: flag_for_llm_fix
```

### New Role (Validator)
```yaml
# Vale checks LLM output doesn't introduce problems
TechnicalTerms:
  message: "Technical term altered"
  action: reject_rewrite

CitationFormat:
  message: "Citation format broken"
  action: reject_rewrite
```

### New Validator Rules Needed

```yaml
# rules/vale/validators/

TermPreservation.yml:
  # Flag if protected terms were changed

NumberPreservation.yml:
  # Flag if numbers don't match original

CitationIntegrity.yml:
  # Flag if Figure/Table refs malformed

NoHallucination.yml:
  # Flag if new technical claims added
```

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Meaning drift | Semantic similarity check, human review |
| Lost content | Length check, number preservation |
| Broken citations | Citation regex validator |
| Hallucination | No-new-claims check, human review |
| Style inconsistency | Section context in prompt |
| Cost | Chunk-level caching, skip unchanged |

## Migration Path

### Phase 1: Parallel Operation
- Add `--mode holistic` alongside existing modes
- Keep surgical mode as fallback
- Compare outputs on test documents

### Phase 2: Hybrid Mode
- Use holistic for body paragraphs
- Use surgical for technical sections (tables, lists, citations)
- Best of both worlds

### Phase 3: Default Holistic
- Make holistic the default mode
- Surgical available via `--mode surgical`
- Mature validation layer

## Success Metrics

1. **Prose quality score** (automated): Flesch-Kincaid, Vale issue count
2. **Preservation accuracy**: % of protected terms/numbers preserved
3. **Human satisfaction**: Review approval rate
4. **Efficiency**: Time to produce quality output
5. **Cost per document**: API tokens used
