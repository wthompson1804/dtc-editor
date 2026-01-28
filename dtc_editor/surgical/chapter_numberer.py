"""
Chapter Numberer for Surgical Pipeline

Handles:
1. Detection of H1 headings (Heading 1 style)
2. Adding sequential chapter numbers to unnumbered chapters
3. Preserving special chapters without numbers (Abstract, References, etc.)
4. Normalizing existing chapter numbers to sequential order

Reference: dtc_editor/rules/surgical_rules_manifest.yml (structure.chapters.numbered)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Set, Optional, Dict
from pathlib import Path
import re
import logging

from docx import Document
from docx.shared import Pt
from docx.oxml.ns import qn

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ChapterHeading:
    """Information about a chapter heading."""
    para_index: int
    original_text: str
    existing_number: Optional[str]  # "1", "2.0", etc. if numbered
    title_text: str  # Text after number (or full text if unnumbered)
    is_special: bool  # True for Abstract, References, etc.
    assigned_number: Optional[int]  # New number to assign


@dataclass
class ChapterNumbererConfig:
    """Configuration for chapter numbering."""
    # Special chapters that don't get numbers
    # NOTE: "Introduction" IS numbered (it's Chapter 1 typically)
    # Only truly special sections like References should be unnumbered
    unnumbered_chapters: Set[str] = field(default_factory=lambda: {
        "abstract",
        "executive summary",
        "references",
        "authors",
        "authors & legal notice",
        "appendix",
        "annex",
        "acknowledgments",
        "acknowledgements",
        "glossary",
        "table of contents",
        "toc",
    })

    # Format for chapter numbers
    number_format: str = "{number}"  # Could be "{number}." or "{number}.0"

    # Whether to add separator between number and title
    separator: str = " "  # Space between "1" and "Introduction"

    # Whether to fix already-numbered chapters that are out of sequence
    renumber_existing: bool = True


@dataclass
class ChapterNumbererResult:
    """Result of chapter numbering."""
    chapters_found: int
    chapters_numbered: int
    chapters_renumbered: int
    special_chapters: int
    changes: List[Dict]
    issues: List[str]


# =============================================================================
# Main Processor Class
# =============================================================================

class ChapterNumberer:
    """
    Adds/corrects chapter numbers in a DOCX document.

    Workflow:
    1. Scan document for H1 headings (Heading 1 style)
    2. Identify special chapters (Abstract, References, etc.)
    3. Assign sequential numbers to content chapters
    4. Update heading text with proper numbers
    """

    def __init__(self, config: ChapterNumbererConfig):
        self.config = config
        self.chapters: List[ChapterHeading] = []
        self.doc: Optional[Document] = None

    def process(self, doc: Document) -> ChapterNumbererResult:
        """
        Process all chapter headings in the document.

        Args:
            doc: python-docx Document object

        Returns:
            ChapterNumbererResult with statistics and changes
        """
        self.doc = doc
        self.chapters = []

        changes = []
        issues = []

        # Step 1: Scan all H1 headings
        self._scan_headings()
        logger.info(f"Found {len(self.chapters)} chapter headings")

        # Step 2: Assign numbers
        self._assign_numbers()

        # Step 3: Apply changes
        chapters_numbered = 0
        chapters_renumbered = 0
        special_chapters = 0

        for chapter in self.chapters:
            if chapter.is_special:
                special_chapters += 1
                continue

            if chapter.assigned_number is None:
                continue

            # Determine what change is needed
            if chapter.existing_number is None:
                # Add new number
                result = self._add_chapter_number(chapter)
                if result:
                    chapters_numbered += 1
                    changes.append({
                        "type": "chapter_numbered",
                        "para_index": chapter.para_index,
                        "title": chapter.title_text,
                        "new_number": chapter.assigned_number,
                    })
            elif self.config.renumber_existing:
                # Check if renumbering needed
                try:
                    existing = int(chapter.existing_number.rstrip('.'))
                    if existing != chapter.assigned_number:
                        result = self._renumber_chapter(chapter)
                        if result:
                            chapters_renumbered += 1
                            changes.append({
                                "type": "chapter_renumbered",
                                "para_index": chapter.para_index,
                                "title": chapter.title_text,
                                "old_number": existing,
                                "new_number": chapter.assigned_number,
                            })
                except ValueError:
                    # Complex number like "2.1" - log and skip
                    issues.append(f"Complex chapter number '{chapter.existing_number}' at '{chapter.title_text}'")

        return ChapterNumbererResult(
            chapters_found=len(self.chapters),
            chapters_numbered=chapters_numbered,
            chapters_renumbered=chapters_renumbered,
            special_chapters=special_chapters,
            changes=changes,
            issues=issues,
        )

    # =========================================================================
    # Scanning Methods
    # =========================================================================

    def _scan_headings(self) -> None:
        """Scan document for H1 headings."""
        for i, para in enumerate(self.doc.paragraphs):
            style_name = para.style.name.lower() if para.style else ""

            # Check for Heading 1 style
            if "heading 1" not in style_name:
                continue

            text = para.text.strip()
            if not text:
                continue

            # Parse existing number if present
            existing_number = None
            title_text = text

            # Pattern: "1 Introduction" or "1. Introduction" or "1.0 Introduction"
            match = re.match(r'^(\d+(?:\.\d+)?\.?)\s+(.+)$', text)
            if match:
                existing_number = match.group(1)
                title_text = match.group(2)

            # Check if this is a special chapter
            title_lower = title_text.lower().strip()
            is_special = any(
                special in title_lower or title_lower in special
                for special in self.config.unnumbered_chapters
            )

            self.chapters.append(ChapterHeading(
                para_index=i,
                original_text=text,
                existing_number=existing_number,
                title_text=title_text,
                is_special=is_special,
                assigned_number=None,
            ))

    def _assign_numbers(self) -> None:
        """Assign sequential numbers to non-special chapters."""
        current_number = 1

        for chapter in self.chapters:
            if chapter.is_special:
                chapter.assigned_number = None
            else:
                chapter.assigned_number = current_number
                current_number += 1

    # =========================================================================
    # Modification Methods
    # =========================================================================

    def _add_chapter_number(self, chapter: ChapterHeading) -> bool:
        """Add number to an unnumbered chapter heading."""
        if chapter.assigned_number is None:
            return False

        para = self.doc.paragraphs[chapter.para_index]

        # Format new number
        number_str = self.config.number_format.format(number=chapter.assigned_number)
        new_text = f"{number_str}{self.config.separator}{chapter.title_text}"

        # Preserve formatting by updating runs
        self._update_paragraph_text(para, new_text)

        logger.info(f"Added chapter number: '{chapter.original_text}' → '{new_text}'")
        return True

    def _renumber_chapter(self, chapter: ChapterHeading) -> bool:
        """Update number of an already-numbered chapter."""
        if chapter.assigned_number is None:
            return False

        para = self.doc.paragraphs[chapter.para_index]

        # Format new number
        number_str = self.config.number_format.format(number=chapter.assigned_number)
        new_text = f"{number_str}{self.config.separator}{chapter.title_text}"

        # Preserve formatting by updating runs
        self._update_paragraph_text(para, new_text)

        logger.info(f"Renumbered chapter: '{chapter.original_text}' → '{new_text}'")
        return True

    def _update_paragraph_text(self, para, new_text: str) -> None:
        """
        Update paragraph text while trying to preserve formatting.

        This is tricky because Word stores text in multiple runs with
        different formatting. We try to preserve the first run's formatting.
        """
        # Get formatting from first run if available
        first_run = para.runs[0] if para.runs else None
        font_name = None
        font_size = None
        font_bold = None

        if first_run:
            font_name = first_run.font.name
            font_size = first_run.font.size
            font_bold = first_run.font.bold

        # Clear and rewrite
        para.clear()
        run = para.add_run(new_text)

        # Restore formatting
        if font_name:
            run.font.name = font_name
        if font_size:
            run.font.size = font_size
        if font_bold is not None:
            run.font.bold = font_bold


# =============================================================================
# Convenience Function
# =============================================================================

def number_chapters(
    docx_path: str,
    output_path: str,
    config: Optional[ChapterNumbererConfig] = None,
) -> ChapterNumbererResult:
    """
    Add/correct chapter numbers in a DOCX file.

    Args:
        docx_path: Path to input DOCX
        output_path: Path to save output DOCX
        config: Optional configuration

    Returns:
        ChapterNumbererResult with statistics
    """
    if config is None:
        config = ChapterNumbererConfig()

    doc = Document(docx_path)
    processor = ChapterNumberer(config)
    result = processor.process(doc)

    doc.save(output_path)

    return result


# =============================================================================
# Analysis Function (for diagnostics)
# =============================================================================

def analyze_chapters(docx_path: str) -> List[Dict]:
    """
    Analyze chapter structure without making changes.

    Returns list of chapter info dicts for inspection.
    """
    doc = Document(docx_path)
    config = ChapterNumbererConfig()
    processor = ChapterNumberer(config)

    processor.doc = doc
    processor._scan_headings()
    processor._assign_numbers()

    chapters = []
    for ch in processor.chapters:
        chapters.append({
            "para_index": ch.para_index,
            "original": ch.original_text,
            "existing_number": ch.existing_number,
            "title": ch.title_text,
            "is_special": ch.is_special,
            "assigned_number": ch.assigned_number,
        })

    return chapters
