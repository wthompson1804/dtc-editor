from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List
import yaml

@dataclass
class ReplacementRule:
    id: str
    category: str
    rationale: str
    search: str
    replace: str
    case_insensitive: bool = True
    whole_word: bool = False
    requires_review: bool = False
    risk_tier: str = "low"

def load_rule_pack(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def load_replacement_rules(rule_pack: Dict[str, Any]) -> List[ReplacementRule]:
    rules: List[ReplacementRule] = []
    for r in rule_pack.get("replacement_rules", []) or []:
        rules.append(ReplacementRule(
            id=r["id"],
            category=r.get("category", "general"),
            rationale=r.get("rationale", ""),
            search=r["search"],
            replace=r["replace"],
            case_insensitive=bool(r.get("case_insensitive", True)),
            whole_word=bool(r.get("whole_word", False)),
            requires_review=bool(r.get("requires_review", False)),
            risk_tier=str(r.get("risk_tier", "low")),
        ))
    return rules
