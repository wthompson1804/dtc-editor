from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass(frozen=True)
class BlockRef:
    block_type: str   # "paragraph" | "heading"
    doc_index: int    # index in document traversal
    block_index: int  # index among same-type blocks

@dataclass
class TextBlock:
    ref: BlockRef
    style_name: str
    text: str
    anchor: str  # stable-ish hash anchor for locating this block

@dataclass
class DocumentIR:
    title: str = ""
    blocks: List[TextBlock] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)

@dataclass
class Finding:
    rule_id: str
    severity: str  # info|warning|critical
    message: str
    ref: Optional[BlockRef] = None
    category: str = "general"
    risk_tier: str = "low"
    before: Optional[str] = None
    after: Optional[str] = None
    details: Dict[str, str] = field(default_factory=dict)

@dataclass
class StructureInventory:
    headings: List[str] = field(default_factory=list)
    heading_styles: List[str] = field(default_factory=list)
    paragraph_count: int = 0
    table_count: int = 0
    has_abstract: bool = False
    has_references: bool = False
    has_authors: bool = False
