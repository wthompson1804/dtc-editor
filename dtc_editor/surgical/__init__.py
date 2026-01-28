"""
Surgical Pipeline Modules

Light-touch conformance checking with minimal changes to author's prose.
These modules handle structure, formatting, and style without rewriting content.

Main entry point: run_surgical_pipeline()

Stages:
1. Chapter Numbering - Add/correct chapter numbers on H1 headings
2. Figure/Table Captions - Apply Chapter-Sequence labels (Figure X-Y)
3. Acronym Expansion - Expand first-use acronyms
"""
from dtc_editor.surgical.figure_table_processor import (
    FigureTableProcessor,
    FigureTableConfig,
    FigureTableResult,
    process_figures_and_tables,
)

from dtc_editor.surgical.chapter_numberer import (
    ChapterNumberer,
    ChapterNumbererConfig,
    ChapterNumbererResult,
    number_chapters,
    analyze_chapters,
)

from dtc_editor.surgical.acronym_expander import (
    AcronymExpander,
    AcronymExpanderConfig,
    AcronymExpanderResult,
    expand_acronyms,
    analyze_acronyms,
)

from dtc_editor.surgical.pipeline import (
    SurgicalPipeline,
    SurgicalPipelineConfig,
    SurgicalPipelineResult,
    run_surgical_pipeline,
    run_surgical_pipeline_cli,
)

__all__ = [
    # Pipeline
    "SurgicalPipeline",
    "SurgicalPipelineConfig",
    "SurgicalPipelineResult",
    "run_surgical_pipeline",
    "run_surgical_pipeline_cli",
    # Figure/Table
    "FigureTableProcessor",
    "FigureTableConfig",
    "FigureTableResult",
    "process_figures_and_tables",
    # Chapter Numbering
    "ChapterNumberer",
    "ChapterNumbererConfig",
    "ChapterNumbererResult",
    "number_chapters",
    "analyze_chapters",
    # Acronym Expansion
    "AcronymExpander",
    "AcronymExpanderConfig",
    "AcronymExpanderResult",
    "expand_acronyms",
    "analyze_acronyms",
]
