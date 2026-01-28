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

from dtc_editor.surgical.integration import (
    # Layer 1: Structural fixes
    StructuralFixesConfig,
    StructuralFixesResult,
    run_structural_fixes,
    # Layer 2: Vale
    ValeLayerResult,
    run_vale_layer,
    # Complete style_only pipeline
    StyleOnlyConfig,
    StyleOnlyResult,
    run_style_only_pipeline,
    # Integration with holistic
    integrate_with_holistic,
    # Backward compatibility
    run_full_surgical_pipeline,
)

__all__ = [
    # === Primary Entry Points ===
    # Style-only pipeline (recommended for conformance-only)
    "StyleOnlyConfig",
    "StyleOnlyResult",
    "run_style_only_pipeline",
    # Integration with holistic pipeline
    "integrate_with_holistic",

    # === Layer 1: Structural Fixes (python-docx) ===
    "StructuralFixesConfig",
    "StructuralFixesResult",
    "run_structural_fixes",

    # === Layer 2: Vale Linting (thin IR) ===
    "ValeLayerResult",
    "run_vale_layer",

    # === Standalone DOCX Pipeline (alternative API) ===
    "SurgicalPipeline",
    "SurgicalPipelineConfig",
    "SurgicalPipelineResult",
    "run_surgical_pipeline",
    "run_surgical_pipeline_cli",

    # === Backward Compatibility ===
    "run_full_surgical_pipeline",

    # === Individual Processors ===
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
