"""
Surgical Pipeline Modules

Light-touch conformance checking with minimal changes to author's prose.
These modules handle structure, formatting, and style without rewriting content.
"""
from dtc_editor.surgical.figure_table_processor import (
    FigureTableProcessor,
    FigureTableConfig,
    FigureTableResult,
    process_figures_and_tables,
)

__all__ = [
    "FigureTableProcessor",
    "FigureTableConfig",
    "FigureTableResult",
    "process_figures_and_tables",
]
