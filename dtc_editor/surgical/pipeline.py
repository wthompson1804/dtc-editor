"""
Surgical Pipeline - Integrated DTC Conformance Processor

Runs all surgical edits in the correct order:
1. Chapter Numbering - Establish document structure
2. Figure/Table Captions - Apply Chapter-Sequence labels
3. Acronym Expansion - Expand first-use acronyms
4. Vale Linting - Apply deterministic style fixes

This module provides the main entry point for the surgical pipeline.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from pathlib import Path
import logging
import json
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
# Data Classes
# =============================================================================

@dataclass
class SurgicalPipelineConfig:
    """Configuration for the surgical pipeline."""
    # Enable/disable individual processors
    enable_chapter_numbering: bool = True
    enable_figure_table_processing: bool = True
    enable_acronym_expansion: bool = True
    enable_vale_linting: bool = True

    # Processor configs (optional - uses defaults if not provided)
    chapter_config: Optional[ChapterNumbererConfig] = None
    figure_table_config: Optional[FigureTableConfig] = None
    acronym_config: Optional[AcronymExpanderConfig] = None

    # Vale config
    vale_config_path: Optional[str] = None

    # Output options
    generate_report: bool = True
    report_format: str = "json"  # "json" or "text"


@dataclass
class SurgicalPipelineResult:
    """Complete result of surgical pipeline processing."""
    # Individual results
    chapter_result: Optional[ChapterNumbererResult] = None
    figure_table_result: Optional[FigureTableResult] = None
    acronym_result: Optional[AcronymExpanderResult] = None
    vale_findings: List[Dict] = field(default_factory=list)

    # Aggregate statistics
    total_changes: int = 0
    total_issues: int = 0

    # Metadata
    input_file: str = ""
    output_file: str = ""
    processing_time_ms: float = 0
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for serialization."""
        result = {
            "metadata": {
                "input_file": self.input_file,
                "output_file": self.output_file,
                "processing_time_ms": self.processing_time_ms,
                "timestamp": self.timestamp,
            },
            "summary": {
                "total_changes": self.total_changes,
                "total_issues": self.total_issues,
            },
            "chapters": None,
            "figures_tables": None,
            "acronyms": None,
            "vale": None,
        }

        if self.chapter_result:
            result["chapters"] = {
                "chapters_found": self.chapter_result.chapters_found,
                "chapters_numbered": self.chapter_result.chapters_numbered,
                "chapters_renumbered": self.chapter_result.chapters_renumbered,
                "special_chapters": self.chapter_result.special_chapters,
                "changes": self.chapter_result.changes,
                "issues": self.chapter_result.issues,
            }

        if self.figure_table_result:
            result["figures_tables"] = {
                "figures_found": self.figure_table_result.figures_found,
                "tables_found": self.figure_table_result.tables_found,
                "captions_added": self.figure_table_result.captions_added,
                "captions_corrected": self.figure_table_result.captions_corrected,
                "sources_added": self.figure_table_result.sources_added,
                "references_fixed": self.figure_table_result.references_fixed,
                "changes": self.figure_table_result.changes,
                "issues": self.figure_table_result.issues,
            }

        if self.acronym_result:
            result["acronyms"] = {
                "acronyms_found": self.acronym_result.acronyms_found,
                "expansions_made": self.acronym_result.expansions_made,
                "already_expanded": self.acronym_result.already_expanded,
                "unknown_acronyms": self.acronym_result.unknown_acronyms,
                "changes": self.acronym_result.changes,
                "issues": self.acronym_result.issues,
            }

        if self.vale_findings:
            result["vale"] = {
                "findings_count": len(self.vale_findings),
                "findings": self.vale_findings[:20],  # Limit for readability
            }

        return result

    def to_text_report(self) -> str:
        """Generate human-readable text report."""
        lines = [
            "=" * 60,
            "DTC SURGICAL PIPELINE REPORT",
            "=" * 60,
            f"Input:  {self.input_file}",
            f"Output: {self.output_file}",
            f"Time:   {self.processing_time_ms:.0f}ms",
            f"Date:   {self.timestamp}",
            "",
            "-" * 60,
            "SUMMARY",
            "-" * 60,
            f"Total changes: {self.total_changes}",
            f"Total issues:  {self.total_issues}",
            "",
        ]

        if self.chapter_result:
            lines.extend([
                "-" * 60,
                "CHAPTER NUMBERING",
                "-" * 60,
                f"Chapters found:     {self.chapter_result.chapters_found}",
                f"Chapters numbered:  {self.chapter_result.chapters_numbered}",
                f"Chapters renumbered: {self.chapter_result.chapters_renumbered}",
                f"Special chapters:   {self.chapter_result.special_chapters}",
                "",
            ])

        if self.figure_table_result:
            lines.extend([
                "-" * 60,
                "FIGURES & TABLES",
                "-" * 60,
                f"Figures found:      {self.figure_table_result.figures_found}",
                f"Tables found:       {self.figure_table_result.tables_found}",
                f"Captions added:     {self.figure_table_result.captions_added}",
                f"Captions corrected: {self.figure_table_result.captions_corrected}",
                f"Sources added:      {self.figure_table_result.sources_added}",
                "",
            ])

        if self.acronym_result:
            lines.extend([
                "-" * 60,
                "ACRONYM EXPANSION",
                "-" * 60,
                f"Acronyms found:     {self.acronym_result.acronyms_found}",
                f"Expansions made:    {self.acronym_result.expansions_made}",
                f"Already expanded:   {self.acronym_result.already_expanded}",
                f"Unknown acronyms:   {len(self.acronym_result.unknown_acronyms)}",
                "",
            ])
            if self.acronym_result.unknown_acronyms:
                lines.append("Unknown: " + ", ".join(self.acronym_result.unknown_acronyms[:10]))
                lines.append("")

        if self.vale_findings:
            lines.extend([
                "-" * 60,
                "VALE FINDINGS",
                "-" * 60,
                f"Total findings: {len(self.vale_findings)}",
                "",
            ])

        lines.append("=" * 60)
        return "\n".join(lines)


# =============================================================================
# Main Pipeline Class
# =============================================================================

class SurgicalPipeline:
    """
    Integrated surgical pipeline for DTC document conformance.

    Processes documents through multiple stages:
    1. Chapter numbering
    2. Figure/table caption processing
    3. Acronym expansion
    4. Vale linting (optional)

    Each stage is optional and can be configured independently.
    """

    def __init__(self, config: SurgicalPipelineConfig):
        self.config = config

    def process(
        self,
        input_path: str,
        output_path: str,
    ) -> SurgicalPipelineResult:
        """
        Process a document through the surgical pipeline.

        Args:
            input_path: Path to input DOCX file
            output_path: Path for output DOCX file

        Returns:
            SurgicalPipelineResult with all processing statistics
        """
        import time
        start_time = time.time()

        result = SurgicalPipelineResult(
            input_file=input_path,
            output_file=output_path,
            timestamp=datetime.utcnow().isoformat() + "Z",
        )

        # Load document
        doc = Document(input_path)
        logger.info(f"Loaded document: {input_path}")

        # Stage 1: Chapter Numbering
        if self.config.enable_chapter_numbering:
            logger.info("Stage 1: Chapter Numbering")
            ch_config = self.config.chapter_config or ChapterNumbererConfig()
            processor = ChapterNumberer(ch_config)
            result.chapter_result = processor.process(doc)
            result.total_changes += result.chapter_result.chapters_numbered
            result.total_changes += result.chapter_result.chapters_renumbered
            result.total_issues += len(result.chapter_result.issues)

        # Stage 2: Figure/Table Processing
        if self.config.enable_figure_table_processing:
            logger.info("Stage 2: Figure/Table Processing")
            fig_config = self.config.figure_table_config or FigureTableConfig()
            processor = FigureTableProcessor(fig_config)
            result.figure_table_result = processor.process(doc)
            result.total_changes += result.figure_table_result.captions_added
            result.total_changes += result.figure_table_result.captions_corrected
            result.total_changes += result.figure_table_result.sources_added
            result.total_issues += len(result.figure_table_result.issues)

        # Stage 3: Acronym Expansion
        if self.config.enable_acronym_expansion:
            logger.info("Stage 3: Acronym Expansion")
            acr_config = self.config.acronym_config or AcronymExpanderConfig()
            processor = AcronymExpander(acr_config)
            result.acronym_result = processor.process(doc)
            result.total_changes += result.acronym_result.expansions_made
            result.total_issues += len(result.acronym_result.issues)

        # Stage 4: Vale Linting (optional - requires Vale installation)
        if self.config.enable_vale_linting:
            logger.info("Stage 4: Vale Linting (skipped - not implemented in pipeline)")
            # Note: Vale linting would require saving doc, running vale, parsing results
            # For now, this is handled separately by the vale_adapter

        # Save output
        doc.save(output_path)
        logger.info(f"Saved output: {output_path}")

        # Calculate timing
        end_time = time.time()
        result.processing_time_ms = (end_time - start_time) * 1000

        return result


# =============================================================================
# Convenience Functions
# =============================================================================

def run_surgical_pipeline(
    input_path: str,
    output_path: str,
    config: Optional[SurgicalPipelineConfig] = None,
) -> SurgicalPipelineResult:
    """
    Run the surgical pipeline on a document.

    Args:
        input_path: Path to input DOCX
        output_path: Path to save output DOCX
        config: Optional configuration

    Returns:
        SurgicalPipelineResult with all statistics
    """
    if config is None:
        config = SurgicalPipelineConfig()

    pipeline = SurgicalPipeline(config)
    return pipeline.process(input_path, output_path)


def run_surgical_pipeline_cli(
    input_path: str,
    output_path: Optional[str] = None,
    report_path: Optional[str] = None,
    verbose: bool = False,
) -> None:
    """
    CLI wrapper for surgical pipeline.

    Args:
        input_path: Path to input DOCX
        output_path: Path for output (default: input_surgical.docx)
        report_path: Path for report (default: no report file)
        verbose: Enable verbose logging
    """
    if verbose:
        logging.basicConfig(level=logging.INFO, format="%(message)s")
    else:
        logging.basicConfig(level=logging.WARNING)

    # Default output path
    if output_path is None:
        input_stem = Path(input_path).stem
        output_path = str(Path(input_path).parent / f"{input_stem}_surgical.docx")

    # Run pipeline
    print(f"Processing: {input_path}")
    result = run_surgical_pipeline(input_path, output_path)

    # Print report
    print(result.to_text_report())

    # Save report if requested
    if report_path:
        with open(report_path, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
        print(f"Report saved: {report_path}")

    print(f"\nOutput: {output_path}")


# =============================================================================
# Main entry point
# =============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m dtc_editor.surgical.pipeline <input.docx> [output.docx]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    run_surgical_pipeline_cli(input_file, output_file, verbose=True)
