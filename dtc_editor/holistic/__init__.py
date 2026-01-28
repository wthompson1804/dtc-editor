"""
Holistic Rewrite Pipeline

LLM-first approach where the LLM rewrites paragraphs holistically,
and Vale rules serve as post-validators rather than issue detectors.
"""
from dtc_editor.holistic.chunker import chunk_document, Chunk, ChunkStrategy
from dtc_editor.holistic.rewriter import HolisticRewriter, RewriteResult
from dtc_editor.holistic.validator import Validator, ValidationResult
from dtc_editor.holistic.orchestrator import (
    run_holistic_pipeline,
    HolisticConfig,
    PipelineResult,
    PipelineStats,
    StylePolishStats,
    generate_review_report,
)

__all__ = [
    "chunk_document",
    "Chunk",
    "ChunkStrategy",
    "HolisticRewriter",
    "RewriteResult",
    "Validator",
    "ValidationResult",
    "run_holistic_pipeline",
    "HolisticConfig",
    "PipelineResult",
    "PipelineStats",
    "StylePolishStats",
    "generate_review_report",
]
