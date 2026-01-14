from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class PersnicketyChecklistResult:
    ok: bool
    missing: List[str]
    notes: List[str]

def assert_style_guide_coverage(rule_pack: Dict[str, Any]) -> PersnicketyChecklistResult:
    required_capabilities = [
        "dtc.title.max_words",
        "dtc.required_sections",
        "dtc.captions.figure_table_format",
        "dtc.capitalization.digital_twin_common_noun",
        "protected_terms.enabled",
        "outputs.bundle.clean_redline_changelog",
        "representation.editops",
        "verification.invariants",
        "verification.structure_inventory",
    ]
    missing = [c for c in required_capabilities if c not in (rule_pack.get("capabilities") or [])]
    notes = []
    if not missing:
        notes.append("All core DTC + representation + verification capabilities present.")
    else:
        notes.append("Missing capabilities should be added to rule pack + tests.")
    return PersnicketyChecklistResult(ok=(len(missing)==0), missing=missing, notes=notes)
