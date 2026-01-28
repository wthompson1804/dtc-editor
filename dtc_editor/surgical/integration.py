"""
Surgical Pipeline Integration - Explicit Layered Architecture

This module implements a clean separation of concerns:

Layer 1: python-docx (Structural) - ALWAYS runs
    - Chapter numbering on H1 headings
    - Figure/table caption processing (Chapter-Sequence labels)
    - Acronym expansion (first-use)
    Works directly on DOCX for structure changes that are hard/impossible in IR

Layer 2: Thin IR + Vale - ALWAYS runs for style_only mode
    - Extract minimal IR from structurally-fixed DOCX
    - Run Vale linting
    - Apply Vale EditOps
    - Emit back to DOCX

Layer 3: Full IR (Holistic) - ONLY for holistic/rewrite modes
    - Full chunking, LLM rewriting, style polish
    - Handled by the holistic module, not here

Recommended workflows:

    style_only:
        Input DOCX → run_style_only_pipeline() → Output DOCX

    holistic/combined:
        Input DOCX → integrate_with_holistic() → Fixed DOCX path
                   → run_holistic_pipeline() → Output IR
                   → emit_clean_docx() → Output DOCX
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from pathlib import Path
import tempfile
import shutil
import logging
import os
from datetime import datetime

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


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class StructuralFixesConfig:
    """Configuration for Layer 1: python-docx structural fixes."""
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
class StyleOnlyConfig:
    """Configuration for the complete style_only pipeline."""
    # Layer 1: Structural fixes
    structural: StructuralFixesConfig = field(default_factory=StructuralFixesConfig)

    # Layer 2: Vale linting
    enable_vale: bool = True
    vale_config_path: Optional[str] = None

    # Output options
    create_redline: bool = True
    redline_author: str = "DTC Editor"


# =============================================================================
# Result Classes
# =============================================================================

@dataclass
class StructuralFixesResult:
    """Result of Layer 1: python-docx structural fixes."""
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


@dataclass
class ValeLayerResult:
    """Result of Layer 2: Vale linting via thin IR."""
    status: str = "skipped"  # "ok", "skipped", "failed"
    findings_count: int = 0
    editops_applied: int = 0
    editops_rejected: int = 0
    message: str = ""


@dataclass
class StyleOnlyResult:
    """Complete result of the style_only pipeline."""
    # Layer results
    structural: StructuralFixesResult
    vale: ValeLayerResult

    # Outputs
    clean_path: str = ""
    redline_path: Optional[str] = None

    # Metadata
    input_path: str = ""
    timestamp: str = ""
    processing_time_ms: float = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for reporting."""
        return {
            "metadata": {
                "input_path": self.input_path,
                "clean_path": self.clean_path,
                "redline_path": self.redline_path,
                "timestamp": self.timestamp,
                "processing_time_ms": self.processing_time_ms,
            },
            "structural": self.structural.to_dict(),
            "vale": {
                "status": self.vale.status,
                "findings_count": self.vale.findings_count,
                "editops_applied": self.vale.editops_applied,
                "editops_rejected": self.vale.editops_rejected,
                "message": self.vale.message,
            },
            "summary": {
                "structural_changes": self.structural.total_changes,
                "structural_issues": self.structural.total_issues,
                "vale_edits": self.vale.editops_applied,
            },
        }


# =============================================================================
# Layer 1: python-docx Structural Fixes
# =============================================================================

def run_structural_fixes(
    input_path: str,
    output_path: Optional[str] = None,
    config: Optional[StructuralFixesConfig] = None,
) -> StructuralFixesResult:
    """
    Layer 1: Run DOCX-level structural fixes.

    This processes the document directly with python-docx for changes that
    are difficult or impossible to make via the IR (adding paragraphs,
    modifying captions, handling drawings, etc.).

    Args:
        input_path: Path to input DOCX
        output_path: Path for output DOCX (None = use temp file)
        config: Optional configuration

    Returns:
        StructuralFixesResult with output path and statistics
    """
    if config is None:
        config = StructuralFixesConfig()

    logger.info(f"Layer 1 (Structural): Processing {input_path}")

    # Load document
    doc = Document(input_path)

    result = StructuralFixesResult()

    # Stage 1: Chapter Numbering
    if config.enable_chapter_numbering:
        logger.info("  Stage 1/3: Chapter numbering")
        ch_config = config.chapter_config or ChapterNumbererConfig()
        processor = ChapterNumberer(ch_config)
        result.chapter_result = processor.process(doc)
        result.total_changes += result.chapter_result.chapters_numbered
        result.total_changes += result.chapter_result.chapters_renumbered
        result.total_issues += len(result.chapter_result.issues)

    # Stage 2: Figure/Table Processing
    if config.enable_figure_table_processing:
        logger.info("  Stage 2/3: Figure/table captions")
        fig_config = config.figure_table_config or FigureTableConfig()
        processor = FigureTableProcessor(fig_config)
        result.figure_table_result = processor.process(doc)
        result.total_changes += result.figure_table_result.captions_added
        result.total_changes += result.figure_table_result.captions_corrected
        result.total_issues += len(result.figure_table_result.issues)

    # Stage 3: Acronym Expansion
    if config.enable_acronym_expansion:
        logger.info("  Stage 3/3: Acronym expansion")
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
        os.close(fd)
        result.output_path = temp_path

    # Save document
    doc.save(result.output_path)
    logger.info(f"Layer 1 complete: {result.total_changes} changes, saved to {result.output_path}")

    return result


# =============================================================================
# Layer 2: Thin IR + Vale
# =============================================================================

def run_vale_layer(
    input_path: str,
    output_path: str,
    vale_config_path: Optional[str] = None,
) -> ValeLayerResult:
    """
    Layer 2: Run Vale linting via thin IR extraction.

    This extracts a minimal IR from the DOCX just to run Vale, then applies
    the resulting EditOps and emits back to DOCX. This is more lightweight
    than the full pipeline.

    Args:
        input_path: Path to input DOCX (typically from Layer 1)
        output_path: Path for output DOCX
        vale_config_path: Optional path to Vale config

    Returns:
        ValeLayerResult with statistics
    """
    logger.info(f"Layer 2 (Vale): Processing {input_path}")

    result = ValeLayerResult()

    try:
        # Import IR-related modules
        from dtc_editor.adapters.docx_adapter import extract_ir_and_inventory, emit_clean_docx
        from dtc_editor.adapters.vale_adapter import run_vale, ValeConfig
        from dtc_editor.apply import apply_editops

        # Extract thin IR
        logger.info("  Extracting IR for Vale")
        ir, inventory = extract_ir_and_inventory(input_path)

        # Configure Vale for surgical mode
        vale_config = ValeConfig(
            styles_path=vale_config_path,
            pipeline_mode="surgical",  # Use surgical rules only
        )

        # Run Vale
        logger.info("  Running Vale linter")
        vale_result = run_vale(ir, vale_config)

        if vale_result.status == "skipped":
            result.status = "skipped"
            result.message = vale_result.message
            # Just copy input to output
            shutil.copy2(input_path, output_path)
            return result

        if vale_result.status == "failed":
            result.status = "failed"
            result.message = vale_result.message
            # Just copy input to output
            shutil.copy2(input_path, output_path)
            return result

        result.findings_count = len(vale_result.findings)

        # Apply EditOps if any
        if vale_result.editops:
            logger.info(f"  Applying {len(vale_result.editops)} Vale EditOps")
            ir, ops = apply_editops(ir, vale_result.editops)
            result.editops_applied = sum(1 for o in ops if o.status == "applied")
            result.editops_rejected = sum(1 for o in ops if o.status == "rejected")

        # Emit to output
        logger.info(f"  Emitting to {output_path}")
        emit_clean_docx(input_path, ir, output_path)

        result.status = "ok"
        result.message = f"Vale: {result.findings_count} findings, {result.editops_applied} edits applied"
        logger.info(f"Layer 2 complete: {result.message}")

        return result

    except Exception as e:
        logger.error(f"Layer 2 (Vale) failed: {e}")
        result.status = "failed"
        result.message = str(e)
        # Copy input to output so pipeline can continue
        shutil.copy2(input_path, output_path)
        return result


# =============================================================================
# Complete Style-Only Pipeline
# =============================================================================

def run_style_only_pipeline(
    input_path: str,
    output_dir: str,
    config: Optional[StyleOnlyConfig] = None,
) -> StyleOnlyResult:
    """
    Run the complete style_only pipeline (Layers 1 + 2).

    This is the main entry point for style-conformance processing without
    LLM rewriting. It runs:
    1. Layer 1: python-docx structural fixes
    2. Layer 2: Vale linting via thin IR

    Args:
        input_path: Path to input DOCX
        output_dir: Directory for output files
        config: Optional configuration

    Returns:
        StyleOnlyResult with all outputs and statistics
    """
    import time
    start_time = time.time()

    if config is None:
        config = StyleOnlyConfig()

    # Prepare output paths
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    stem = Path(input_path).stem
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    bundle_dir = out_path / f"{stem}_{ts}"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    original_copy = str(bundle_dir / f"{stem}.original.docx")
    clean_path = str(bundle_dir / f"{stem}.clean.docx")
    redline_path = str(bundle_dir / f"{stem}.redline.docx") if config.create_redline else None

    # Copy original
    shutil.copy2(input_path, original_copy)

    # Layer 1: Structural fixes
    logger.info("=" * 60)
    logger.info("STYLE-ONLY PIPELINE: Layer 1 (Structural)")
    logger.info("=" * 60)

    structural_result = run_structural_fixes(
        input_path=input_path,
        output_path=None,  # Use temp file
        config=config.structural,
    )

    # Layer 2: Vale
    logger.info("=" * 60)
    logger.info("STYLE-ONLY PIPELINE: Layer 2 (Vale)")
    logger.info("=" * 60)

    vale_result = ValeLayerResult(status="skipped", message="Vale disabled")
    if config.enable_vale:
        vale_result = run_vale_layer(
            input_path=structural_result.output_path,
            output_path=clean_path,
            vale_config_path=config.vale_config_path,
        )
    else:
        # Just copy structural output to clean
        shutil.copy2(structural_result.output_path, clean_path)

    # Clean up temp file from Layer 1
    if "/tmp" in structural_result.output_path or "\\Temp\\" in structural_result.output_path:
        try:
            Path(structural_result.output_path).unlink()
        except Exception:
            pass

    # Create redline if requested
    if config.create_redline and redline_path:
        logger.info("Creating redline document")
        try:
            from dtc_editor.redline import create_redline
            create_redline(
                original_copy,
                clean_path,
                redline_path,
                author=config.redline_author,
            )
        except Exception as e:
            logger.warning(f"Failed to create redline: {e}")
            redline_path = None

    # Build result
    end_time = time.time()

    result = StyleOnlyResult(
        structural=structural_result,
        vale=vale_result,
        clean_path=clean_path,
        redline_path=redline_path,
        input_path=input_path,
        timestamp=datetime.utcnow().isoformat() + "Z",
        processing_time_ms=(end_time - start_time) * 1000,
    )

    logger.info("=" * 60)
    logger.info("STYLE-ONLY PIPELINE: Complete")
    logger.info(f"  Structural changes: {structural_result.total_changes}")
    logger.info(f"  Vale edits: {vale_result.editops_applied}")
    logger.info(f"  Output: {clean_path}")
    logger.info("=" * 60)

    return result


# =============================================================================
# Integration with Holistic Pipeline
# =============================================================================

def integrate_with_holistic(
    input_path: str,
    config: Optional[StructuralFixesConfig] = None,
) -> str:
    """
    Pre-process DOCX for the holistic pipeline (Layer 1 only).

    Call this before run_holistic_pipeline() to ensure structural
    fixes are applied first. The holistic pipeline will then do its
    own full IR extraction and LLM rewriting.

    Args:
        input_path: Path to input DOCX
        config: Structural fixes config

    Returns:
        Path to structurally-fixed DOCX (temp file)
    """
    logger.info("Preparing document for holistic pipeline")
    result = run_structural_fixes(input_path, config=config)
    return result.output_path


def run_full_surgical_pipeline(
    input_path: str,
    output_dir: str,
    config: Optional[StructuralFixesConfig] = None,
    # Pass-through to existing pipeline (for backward compatibility)
    use_vale: bool = True,
    vale_config_path: Optional[str] = None,
    use_llm: bool = False,
    anthropic_api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run complete surgical pipeline (backward-compatible entry point).

    For new code, prefer:
    - run_style_only_pipeline() for style_only mode
    - integrate_with_holistic() + run_holistic_pipeline() for holistic mode

    Args:
        input_path: Path to input DOCX
        output_dir: Directory for output files
        config: Structural fixes config
        use_vale: Enable Vale linting
        vale_config_path: Path to Vale config
        use_llm: Enable LLM proposals (uses old pipeline)
        anthropic_api_key: API key for LLM

    Returns:
        Combined result dict with structural and IR-level stats
    """
    if use_llm:
        # Use legacy flow with full IR pipeline
        from dtc_editor.pipeline import run_pipeline

        structural_result = run_structural_fixes(input_path, config=config)

        pipeline_result = run_pipeline(
            input_docx=structural_result.output_path,
            out_dir=output_dir,
            mode="rewrite",
            use_vale=use_vale,
            vale_config_path=vale_config_path,
            use_llm=True,
            anthropic_api_key=anthropic_api_key,
        )

        # Clean up temp file
        if "/tmp" in structural_result.output_path:
            try:
                Path(structural_result.output_path).unlink()
            except Exception:
                pass

        pipeline_result["structural_fixes"] = structural_result.to_dict()
        return pipeline_result

    else:
        # Use new clean style_only flow
        style_config = StyleOnlyConfig(
            structural=config or StructuralFixesConfig(),
            enable_vale=use_vale,
            vale_config_path=vale_config_path,
        )

        result = run_style_only_pipeline(input_path, output_dir, style_config)

        # Convert to legacy format for compatibility
        return {
            "timestamp_utc": result.timestamp,
            "mode": "style_only",
            "artifacts": {
                "original_docx": result.input_path,
                "clean_docx": result.clean_path,
                "redline_docx": result.redline_path,
            },
            "structural_fixes": result.structural.to_dict(),
            "vale": {
                "status": result.vale.status,
                "findings": result.vale.findings_count,
                "editops_applied": result.vale.editops_applied,
            },
            "stats": {
                "structural_changes": result.structural.total_changes,
                "vale_edits": result.vale.editops_applied,
            },
        }
