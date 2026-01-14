from __future__ import annotations
from typing import List, Set, Dict, Any, Tuple
import re
from dtc_editor.editops import EditOp
from dtc_editor.ir import Finding, StructureInventory

REQ_WORDS = {"SHALL","MUST","MAY","SHOULD"}

def _extract_numbers(s: str) -> List[str]:
    return re.findall(r"\b\d+(?:\.\d+)?%?\b|\$\d+(?:\.\d+)?", s)

def _extract_citations(s: str) -> List[str]:
    return re.findall(r"\[\d+\]|\(\d{4}\)|et al\.", s)

def verify_invariants(ops: List[EditOp], protected_terms: Set[str]) -> List[Finding]:
    findings: List[Finding] = []
    for op in ops:
        if op.status != "applied":
            continue
        before = op.before
        after = op.after

        # numbers unchanged
        if _extract_numbers(before) != _extract_numbers(after):
            findings.append(Finding(
                rule_id="inv.number_change",
                severity="critical",
                category="invariant",
                message="Numbers/units changed during edit.",
                before=before, after=after,
                risk_tier="high",
                details={"editop_id": op.id, "rule_id": op.rule_id},
            ))

        # citations unchanged (pattern-based)
        if _extract_citations(before) != _extract_citations(after):
            findings.append(Finding(
                rule_id="inv.citation_change",
                severity="critical",
                category="invariant",
                message="Citations changed during edit.",
                before=before, after=after,
                risk_tier="high",
                details={"editop_id": op.id, "rule_id": op.rule_id},
            ))

        # normative keywords unchanged
        bw = set(re.findall(r"\b(?:SHALL|MUST|MAY|SHOULD)\b", before))
        aw = set(re.findall(r"\b(?:SHALL|MUST|MAY|SHOULD)\b", after))
        if bw != aw:
            findings.append(Finding(
                rule_id="inv.requirement_keyword_change",
                severity="critical",
                category="invariant",
                message="Normative keywords changed (SHALL/MUST/MAY/SHOULD).",
                before=before, after=after,
                risk_tier="high",
                details={"editop_id": op.id, "rule_id": op.rule_id},
            ))

        # protected terms not removed (best-effort)
        for t in list(protected_terms)[:2000]:
            if t and t in before and t not in after:
                findings.append(Finding(
                    rule_id="inv.protected_term_violation",
                    severity="critical",
                    category="invariant",
                    message=f"Protected term removed/altered: {t}",
                    before=before, after=after,
                    risk_tier="high",
                    details={"editop_id": op.id, "rule_id": op.rule_id, "term": t},
                ))
                break

    return findings

def verify_structure(pre: StructureInventory, post: StructureInventory) -> List[Finding]:
    findings: List[Finding] = []
    # Table count should not decrease in safe mode
    if post.table_count < pre.table_count:
        findings.append(Finding(
            rule_id="struct.table_count_decrease",
            severity="critical",
            category="structure",
            message="Table count decreased after edits.",
            risk_tier="high",
            details={"before": str(pre.table_count), "after": str(post.table_count)},
        ))

    # Paragraph count should not decrease dramatically (heuristic)
    if post.paragraph_count + 5 < pre.paragraph_count:
        findings.append(Finding(
            rule_id="struct.paragraph_count_decrease",
            severity="warning",
            category="structure",
            message="Paragraph count decreased significantly after edits.",
            risk_tier="medium",
            details={"before": str(pre.paragraph_count), "after": str(post.paragraph_count)},
        ))

    # Heading inventory styles should remain (heuristic)
    if len(post.headings) + 3 < len(pre.headings):
        findings.append(Finding(
            rule_id="struct.heading_count_decrease",
            severity="warning",
            category="structure",
            message="Heading count decreased significantly after edits.",
            risk_tier="medium",
            details={"before": str(len(pre.headings)), "after": str(len(post.headings))},
        ))

    return findings
