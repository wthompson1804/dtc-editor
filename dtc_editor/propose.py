from __future__ import annotations
from typing import List, Set
import re
from dtc_editor.ir import DocumentIR
from dtc_editor.rules.load_rules import ReplacementRule
from dtc_editor.editops import EditOp, Target
import hashlib

def _mk_id(seed: str) -> str:
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]

def propose_from_rules(ir: DocumentIR, rules: List[ReplacementRule], protected_terms: Set[str]) -> List[EditOp]:
    ops: List[EditOp] = []
    for block in ir.blocks:
        txt = block.text
        for rule in rules:
            # if search string appears within protected term, skip
            s = rule.search.lower()
            if any(s in t.lower() for t in protected_terms):
                continue

            flags = re.IGNORECASE if rule.case_insensitive else 0
            pattern = re.compile((rf"\b{re.escape(rule.search)}\b" if rule.whole_word else re.escape(rule.search)), flags)

            # create one EditOp per occurrence with span
            for occ, m in enumerate(pattern.finditer(txt), start=1):
                before = txt[m.start():m.end()]
                after = rule.replace
                op_id = _mk_id(f"{rule.id}|{block.anchor}|{m.start()}|{m.end()}|{occ}")
                ops.append(EditOp(
                    id=op_id,
                    op="replace_span",
                    target=Target(anchor=block.anchor, doc_index=block.ref.doc_index, block_type=block.ref.block_type,
                                  span_start=m.start(), span_end=m.end(), occurrence=occ),
                    intent=rule.category,
                    engine="deterministic_rule",
                    rule_id=rule.id,
                    rationale=rule.rationale,
                    before=before,
                    after=after,
                    confidence=1.0,
                    requires_review=rule.requires_review,
                    risk_tier=rule.risk_tier,
                ))
    return ops
