"""
Holistic Pipeline Orchestrator

Coordinates the full LLM-first pipeline:
1. Chunk document
2. Rewrite chunks in parallel
3. Validate each rewrite
4. Accept/reject/flag decisions
5. Assemble final document
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Set, Optional, Literal, Callable
import logging
import time

from dtc_editor.ir import DocumentIR, TextBlock
from dtc_editor.holistic.chunker import (
    chunk_document,
    Chunk,
    ChunkStrategy,
    ChunkingResult,
)
from dtc_editor.holistic.rewriter import (
    HolisticRewriter,
    RewriteConfig,
    RewriteResult,
)
from dtc_editor.holistic.validator import (
    Validator,
    ValidatorConfig,
    ValidationResult,
)
from dtc_editor.holistic.acronyms import AcronymTracker

logger = logging.getLogger(__name__)


@dataclass
class HolisticConfig:
    """Configuration for the holistic pipeline."""
    # API config
    api_key: str
    model: str = "claude-sonnet-4-20250514"

    # Chunking
    chunk_strategy: ChunkStrategy = "paragraph"

    # Processing
    max_concurrent: int = 4

    # Validation
    vale_config: Optional[str] = None
    protected_terms: Set[str] = field(default_factory=set)

    # Decision thresholds
    auto_accept: bool = False          # Auto-accept passing validations
    include_rejected: bool = False     # Include rejected rewrites in output (as original)


@dataclass
class ChunkDecision:
    """Decision for a single chunk."""
    chunk: Chunk
    rewrite: RewriteResult
    validation: ValidationResult
    decision: Literal["accepted", "rejected", "flagged"]
    final_text: str


@dataclass
class PipelineStats:
    """Statistics from pipeline run."""
    total_chunks: int
    rewritable_chunks: int
    accepted: int
    rejected: int
    flagged: int
    total_words_original: int
    total_words_final: int
    llm_latency_ms: float
    total_time_s: float


@dataclass
class PipelineResult:
    """Complete result of the holistic pipeline."""
    original_ir: DocumentIR
    final_ir: DocumentIR
    decisions: List[ChunkDecision]
    stats: PipelineStats
    review_needed: bool


def _apply_decisions_to_ir(
    ir: DocumentIR,
    decisions: List[ChunkDecision],
) -> DocumentIR:
    """
    Create a new IR with rewritten text applied.
    """
    # Build mapping of block_index -> new text
    block_updates = {}
    for decision in decisions:
        if decision.decision in ("accepted", "flagged"):
            # For flagged, we still apply the rewrite but note it needs review
            for block_idx in decision.chunk.block_indices:
                # If chunk spans multiple blocks, we need to handle differently
                if len(decision.chunk.block_indices) == 1:
                    block_updates[block_idx] = decision.final_text
                else:
                    # Multi-block chunk: first block gets all text, others get empty
                    if block_idx == decision.chunk.block_indices[0]:
                        block_updates[block_idx] = decision.final_text
                    else:
                        block_updates[block_idx] = ""

    # Create new blocks
    new_blocks = []
    for i, block in enumerate(ir.blocks):
        if i in block_updates:
            new_text = block_updates[i]
            if new_text:  # Skip empty blocks (merged into previous)
                new_blocks.append(TextBlock(
                    ref=block.ref,
                    style_name=block.style_name,
                    text=new_text,
                    anchor=block.anchor,
                ))
        else:
            new_blocks.append(block)

    return DocumentIR(
        title=ir.title,
        blocks=new_blocks,
        metadata=ir.metadata,
    )


def run_holistic_pipeline(
    ir: DocumentIR,
    config: HolisticConfig,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
) -> PipelineResult:
    """
    Run the full holistic rewrite pipeline.

    Args:
        ir: Document intermediate representation
        config: Pipeline configuration
        progress_callback: Optional callback(stage, completed, total)

    Returns:
        PipelineResult with final document and decisions
    """
    start_time = time.time()

    # Stage 1: Chunk the document
    logger.info(f"Chunking document with strategy: {config.chunk_strategy}")
    if progress_callback:
        progress_callback("chunking", 0, 1)

    chunking = chunk_document(ir, config.chunk_strategy)
    logger.info(f"Created {chunking.total_chunks} chunks, {chunking.total_rewritable_words} rewritable words")

    if progress_callback:
        progress_callback("chunking", 1, 1)

    # Initialize acronym tracker and scan existing definitions
    acronym_tracker = AcronymTracker()
    full_text = "\n\n".join(c.text for c in chunking.chunks if c.is_rewritable)
    acronym_tracker.scan_existing_definitions(full_text)
    logger.info(f"Acronym tracker initialized, {len(acronym_tracker.defined)} acronyms already defined")

    # Stage 2: Rewrite chunks
    logger.info("Starting holistic rewrite")
    rewriter = HolisticRewriter(
        config=RewriteConfig(
            api_key=config.api_key,
            model=config.model,
            max_concurrent=config.max_concurrent,
        ),
        protected_terms=config.protected_terms,
        acronym_tracker=acronym_tracker,
    )

    def rewrite_progress(completed, total):
        if progress_callback:
            progress_callback("rewriting", completed, total)

    rewrites = rewriter.rewrite_chunks(
        chunking.chunks,
        progress_callback=rewrite_progress,
    )

    # Stage 3: Validate each rewrite
    logger.info("Validating rewrites")
    validator = Validator(ValidatorConfig(
        vale_config=config.vale_config,
        protected_terms=config.protected_terms,
    ))

    validations = []
    for i, (chunk, rewrite) in enumerate(zip(chunking.chunks, rewrites)):
        if progress_callback:
            progress_callback("validating", i + 1, len(chunking.chunks))

        if chunk.is_rewritable and rewrite.success:
            validation = validator.validate(rewrite.original, rewrite.rewritten)
        else:
            # Non-rewritable or failed rewrite: auto-pass validation
            validation = ValidationResult(
                passed=True,
                checks=[],
                recommendation="accept",
                summary="Skipped (non-rewritable or LLM error)",
            )
        validations.append(validation)

    # Stage 4: Make decisions
    logger.info("Making accept/reject decisions")
    decisions = []
    accepted = rejected = flagged = 0

    for chunk, rewrite, validation in zip(chunking.chunks, rewrites, validations):
        if not chunk.is_rewritable:
            # Keep original for non-rewritable
            decision = "accepted"
            final_text = chunk.text
            accepted += 1
        elif not rewrite.success:
            # LLM failed, keep original
            decision = "rejected"
            final_text = chunk.text
            rejected += 1
        elif validation.recommendation == "reject":
            # Validation failed, keep original
            decision = "rejected"
            final_text = chunk.text
            rejected += 1
            logger.warning(f"Rejected {chunk.id}: {validation.summary}")
        elif validation.recommendation == "review":
            # Needs human review
            decision = "flagged"
            final_text = rewrite.rewritten if config.auto_accept else chunk.text
            flagged += 1
            logger.info(f"Flagged {chunk.id}: {validation.summary}")
        else:
            # Accept the rewrite
            decision = "accepted"
            final_text = rewrite.rewritten
            accepted += 1

        decisions.append(ChunkDecision(
            chunk=chunk,
            rewrite=rewrite,
            validation=validation,
            decision=decision,
            final_text=final_text,
        ))

    # Stage 5: Assemble final document
    logger.info("Assembling final document")
    if progress_callback:
        progress_callback("assembling", 0, 1)

    final_ir = _apply_decisions_to_ir(ir, decisions)

    if progress_callback:
        progress_callback("assembling", 1, 1)

    # Calculate stats
    total_time = time.time() - start_time
    total_latency = sum(r.latency_ms for r in rewrites if r.latency_ms)
    original_words = sum(c.word_count for c in chunking.chunks)
    final_words = sum(len(d.final_text.split()) for d in decisions)

    stats = PipelineStats(
        total_chunks=chunking.total_chunks,
        rewritable_chunks=sum(1 for c in chunking.chunks if c.is_rewritable),
        accepted=accepted,
        rejected=rejected,
        flagged=flagged,
        total_words_original=original_words,
        total_words_final=final_words,
        llm_latency_ms=total_latency,
        total_time_s=total_time,
    )

    logger.info(f"Pipeline complete: {accepted} accepted, {rejected} rejected, {flagged} flagged")
    logger.info(f"Word count: {original_words} → {final_words} ({final_words/original_words:.0%})")

    return PipelineResult(
        original_ir=ir,
        final_ir=final_ir,
        decisions=decisions,
        stats=stats,
        review_needed=flagged > 0,
    )


def generate_review_report(result: PipelineResult, compliance=None) -> str:
    """
    Generate a human-readable review report.

    Args:
        result: Pipeline result with rewrite decisions
        compliance: Optional template compliance result
    """
    lines = [
        "# Holistic Rewrite Review Report",
        "",
        "## Summary",
        f"- Total chunks: {result.stats.total_chunks}",
        f"- Rewritable: {result.stats.rewritable_chunks}",
        f"- Accepted: {result.stats.accepted}",
        f"- Rejected: {result.stats.rejected}",
        f"- Flagged for review: {result.stats.flagged}",
        f"- Word count: {result.stats.total_words_original} → {result.stats.total_words_final}",
        f"- Processing time: {result.stats.total_time_s:.1f}s",
        "",
    ]

    # Add template compliance section if provided
    if compliance is not None:
        lines.append("## Template Compliance")
        lines.append("")
        lines.append(f"**Compliance Score:** {compliance.score:.0%}")
        lines.append("")

        if compliance.issues:
            lines.append("### Issues Found")
            lines.append("")
            for issue in compliance.issues:
                lines.append(f"- {issue}")
            lines.append("")

        if compliance.missing_styles:
            lines.append("### Missing Styles")
            lines.append("")
            for style in compliance.missing_styles:
                lines.append(f"- {style}")
            lines.append("")

        if hasattr(compliance, 'recommendation') and compliance.recommendation:
            lines.append("### Recommendation")
            lines.append("")
            if compliance.recommendation == "full_reconstruct":
                lines.append("Consider applying DTC template styles to this document for full compliance.")
            elif compliance.recommendation == "minor_fixes":
                lines.append("Minor style adjustments needed for full compliance.")
            else:
                lines.append(f"{compliance.recommendation}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # Show flagged items first
    flagged = [d for d in result.decisions if d.decision == "flagged"]
    if flagged:
        lines.append("## Items Requiring Review")
        lines.append("")
        for d in flagged:
            lines.append(f"### {d.chunk.id} ({d.chunk.section_title})")
            lines.append(f"**Reason:** {d.validation.summary}")
            lines.append("")
            lines.append("**Original:**")
            lines.append(f"> {d.chunk.text}")
            lines.append("")
            lines.append("**Proposed rewrite:**")
            lines.append(f"> {d.rewrite.rewritten}")
            lines.append("")
            lines.append("---")
            lines.append("")

    # Show rejected items
    rejected = [d for d in result.decisions if d.decision == "rejected"]
    if rejected:
        lines.append("## Rejected Rewrites (kept original)")
        lines.append("")
        for d in rejected[:10]:  # Limit to first 10
            lines.append(f"### {d.chunk.id}")
            lines.append(f"**Reason:** {d.validation.summary}")
            if d.rewrite.error:
                lines.append(f"**LLM Error:** {d.rewrite.error}")
            lines.append("")

    # Show sample accepted rewrites
    accepted = [d for d in result.decisions if d.decision == "accepted" and d.chunk.is_rewritable]
    if accepted:
        lines.append("## Sample Accepted Rewrites")
        lines.append("")
        for d in accepted[:5]:  # Show first 5
            lines.append(f"### {d.chunk.id} ({d.chunk.section_title})")
            lines.append("")
            lines.append("**Original:**")
            lines.append(f"> {d.chunk.text[:300]}...")
            lines.append("")
            lines.append("**Rewritten:**")
            lines.append(f"> {d.rewrite.rewritten[:300]}...")
            lines.append("")
            lines.append("---")
            lines.append("")

    return "\n".join(lines)
