from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, Literal

OpType = Literal["replace_span", "replace_block", "noop", "proposed_only"]

@dataclass
class Target:
    anchor: str                  # stable-ish block anchor
    doc_index: int               # fallback address
    block_type: str              # paragraph|heading
    span_start: Optional[int] = None
    span_end: Optional[int] = None
    occurrence: Optional[int] = None  # nth match in block

@dataclass
class EditOp:
    id: str
    op: OpType
    target: Target
    intent: str                  # clarity|dtc_style|grammar|prose_rewrite
    engine: str                  # deterministic_rule|llm_proposal|human
    rule_id: str
    rationale: str
    before: str
    after: str
    confidence: Optional[float] = None
    requires_review: bool = True
    risk_tier: str = "low"
    verification: Dict[str, Any] = field(default_factory=dict)
    status: str = "proposed"     # proposed|applied|rejected|failed

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
