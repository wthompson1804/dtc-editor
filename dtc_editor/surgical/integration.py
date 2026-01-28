"""
Surgical Pipeline Integration

Bridges the new surgical modules (which work on DOCX) with the existing
IR-based pipeline. This module provides entry points that:

1. Pre-process DOCX with structural fixes (chapters, figures, acronyms)
2. Then hand off to the existing IR-based pipeline
3. Or post-process after the existing pipeline

The key insight: Structural changes (adding captions, numbering chapters)
are best done at the DOCX level BEFORE IR extraction, because:
- IR doesn't capture all DOCX structure (drawings, field codes)
- Adding paragraphs is easier in DOCX than modifying IR block indices

Text-level changes (Vale rules, clarity edits) work better on IR
because they have stable anchors and span-based editing.

Recommended workflow:
    Input DOCX
    → run_structural_fixes() [DOCX-level, new modules]
    → extract_ir_and_inventory() [Create IR]
    → run_pipeline() or run_holistic_pipeline() [IR-level, existing]
    → emit_clean_docx() [IR back to DOCX]
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from pathlib import Path
import tempfile
import shutil
import logging

from docx import Document

from dtc_editor.surgical.chapter_numberer import (
    ChapterNumberer,
    ChapterNumbererConfig,
    ChapterNumbererResult,
)
from dtc_editor.surgical.figure_table_processor import (
    FigureTableProcessor,
    FigureTableConfig,
    FigureTableResult,
)
from dtc_editor.surgical.acronym_expander import (
    AcronymExpander,
    AcronymExpanderConfig,
    AcronymExpanderResult,
)

logger = logging.getLogger(__name__)


@dataclass
class StructuralFixesConfig:
    """Configuration for structural fixes (DOCX-level processing)."""
    # Enable/disable individual processors
    enable_chapter_numbering: bool = True
    enable_figure_table_processing: bool = True
    enable_acronym_expansion: bool = True

    # Processor-specific configs (optional)
    chapter_config: Optional[ChapterNumbererConfig] = None
    figure_table_config: Optional[FigureTableConfig] = None
    acronym_config: Optional[AcronymExpanderConfig] = None

    # Save intermediate file for debugging
    save_intermediate: bool = False
    intermediate_suffix: str = "_structural"


@dataclass
class StructuralFixesResult:
    """Result of structural fixes."""
    # Individual results
    chapter_result: Optional[ChapterNumbererResult] = None
    figure_table_result: Optional[FigureTableResult] = None
    acronym_result: Optional[AcronymExpanderResult] = None

    # Aggregate
    total_changes: int = 0
    total_issues: int = 0

    # Output path (may be temp file or saved intermediate)
    output_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for reporting."""
        result = {
            "total_changes": self.total_changes,
            "total_issues": self.total_issues,
            "output_path": self.output_path,
            "chapters": None,
            "figures_tables": None,
            "acronyms": None,
        }

        if self.chapter_result:
            result["chapters"] = {
                "found": self.chapter_result.chapters_found,
                "numbered": self.chapter_result.chapters_numbered,
                "renumbered": self.chapter_result.chapters_renumbered,
            }

        if self.figure_table_result:
            result["figures_tables"] = {
                "figures_found": self.figure_table_result.figures_found,
                "tables_found": self.figure_table_result.tables_found,
                "captions_added": self.figure_table_result.captions_added,
                "captions_corrected": self.figure_table_result.captions_corrected,
            }

        if self.acronym_result:
            result["acronyms"] = {
                "found": self.acronym_result.acronyms_found,
                "expansions_made": self.acronym_result.expansions_made,
            }

        return result


def run_structural_fixes(
    input_path: str,
    output_path: Optional[str] = None,
    config: Optional[StructuralFixesConfig] = None,
) -> StructuralFixesResult:
    """
    Run DOCX-level structural fixes before IR extraction.

    This is the bridge between the new surgical modules and the existing
    IR-based pipeline. It should be called BEFORE extract_ir_and_inventory().

    Args:
        input_path: Path to input DOCX
        output_path: Path for output DOCX (None = use temp file)
        config: Optional configuration

    Returns:
        StructuralFixesResult with output path and statistics
    """
    if config is None:
        config = StructuralFixesConfig()

    logger.info(f"Running structural fixes on: {input_path}")

    # Load document
    doc = Document(input_path)

    result = StructuralFixesResult()

    # Stage 1: Chapter Numbering
    if config.enable_chapter_numbering:
        logger.info("Structural fix 1/3: Chapter numbering")
        ch_config = config.chapter_config or ChapterNumbererConfig()
        processor = ChapterNumberer(ch_config)
        result.chapter_result = processor.process(doc)
        result.total_changes += result.chapter_result.chapters_numbered
        result.total_changes += result.chapter_result.chapters_renumbered
        result.total_issues += len(result.chapter_result.issues)

    # Stage 2: Figure/Table Processing
    if config.enable_figure_table_processing:
        logger.info("Structural fix 2/3: Figure/table captions")
        fig_config = config.figure_table_config or FigureTableConfig()
        processor = FigureTableProcessor(fig_config)
        result.figure_table_result = processor.process(doc)
        result.total_changes += result.figure_table_result.captions_added
        result.total_changes += result.figure_table_result.captions_corrected
        result.total_issues += len(result.figure_table_result.issues)

    # Stage 3: Acronym Expansion
    if config.enable_acronym_expansion:
        logger.info("Structural fix 3/3: Acronym expansion")
        acr_config = config.acronym_config or AcronymExpanderConfig()
        processor = AcronymExpander(acr_config)
        result.acronym_result = processor.process(doc)
        result.total_changes += result.acronym_result.expansions_made
        result.total_issues += len(result.acronym_result.issues)

    # Determine output path
    if output_path:
        result.output_path = output_path
    elif config.save_intermediate:
        stem = Path(input_path).stem
        parent = Path(input_path).parent
        result.output_path = str(parent / f"{stem}{config.intermediate_suffix}.docx")
    else:
        # Use temp file
        fd, temp_path = tempfile.mkstemp(suffix=".docx")
        import os
        os.close(fd)
        result.output_path = temp_path

    # Save document
    doc.save(result.output_path)
    logger.info(f"Structural fixes saved to: {result.output_path}")

    return result


def run_full_surgical_pipeline(
    input_path: str,
    output_dir: str,
    config: Optional[StructuralFixesConfig] = None,
    # Pass-through to existing pipeline
    use_vale: bool = True,
    vale_config_path: Optional[str] = None,
    use_llm: bool = False,
    anthropic_api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run the complete surgical pipeline: structural fixes + IR-level edits.

    This is the recommended entry point for surgical (conformance-only) processing.

    Flow:
    1. run_structural_fixes() - DOCX-level (chapters, figures, acronyms)
    2. extract_ir_and_inventory() - Create IR from fixed DOCX
    3. run_pipeline() - IR-level (Vale rules, clarity edits)
    4. Outputs: clean.docx, redline.docx, etc.

    Args:
        input_path: Path to input DOCX
        output_dir: Directory for output files
        config: Structural fixes config
        use_vale: Enable Vale linting
        vale_config_path: Path to Vale config
        use_llm: Enable LLM proposals
        anthropic_api_key: API key for LLM

    Returns:
        Combined result dict with structural and IR-level stats
    """
    from dtc_editor.pipeline import run_pipeline

    # Step 1: Structural fixes (DOCX-level)
    structural_result = run_structural_fixes(input_path, config=config)

    # Step 2: Run existing IR-level pipeline on the structurally-fixed DOCX
    pipeline_result = run_pipeline(
        input_docx=structural_result.output_path,
        out_dir=output_dir,
        mode="rewrite" if use_llm else "safe",
        use_vale=use_vale,
        vale_config_path=vale_config_path,
        use_llm=use_llm,
        anthropic_api_key=anthropic_api_key,
    )

    # Clean up temp file if used
    if not config or not config.save_intermediate:
        temp_path = structural_result.output_path
        if temp_path and Path(temp_path).exists() and "/tmp" in temp_path:
            try:
                Path(temp_path).unlink()
            except Exception:
                pass

    # Combine results
    pipeline_result["structural_fixes"] = structural_result.to_dict()

    return pipeline_result


def integrate_with_holistic(
    input_path: str,
    config: Optional[StructuralFixesConfig] = None,
) -> str:
    """
    Pre-process DOCX for the holistic pipeline.

    Call this before run_holistic_pipeline() to ensure structural
    fixes are applied first.

    Args:
        input_path: Path to input DOCX
        config: Structural fixes config

    Returns:
        Path to structurally-fixed DOCX (temp file)
    """
    result = run_structural_fixes(input_path, config=config)
    return result.output_path
