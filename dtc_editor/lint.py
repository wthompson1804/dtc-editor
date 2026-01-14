from __future__ import annotations
from typing import List, Dict, Any
import re
from dtc_editor.ir import DocumentIR, Finding

_THROAT_CLEARING = [
    r"^As has been",
    r"^It is important to note that\b",
    r"^It should be noted that\b",
    r"^The fact that\b",
]

def _subordinate_clause_count(s: str) -> int:
    markers = [" which ", " that ", " because ", " although ", " whereas ", " while ", " since ", " if ", " when "]
    count = 0
    lower = f" {s.lower()} "
    for m in markers:
        count += lower.count(m)
    count += s.count(",") // 2
    return count

def lint_dtc(ir: DocumentIR, dtc_cfg: Dict[str, Any]) -> List[Finding]:
    findings: List[Finding] = []
    max_words = int(((dtc_cfg.get("validators") or {}).get("title") or {}).get("max_words", 7))

    if ir.title:
        wc = len([w for w in ir.title.split() if w.strip()])
        if wc > max_words:
            findings.append(Finding(
                rule_id="dtc.title.too_long",
                severity="warning",
                category="dtc_style",
                message=f"Title exceeds {max_words} words (found {wc}).",
                before=ir.title,
                risk_tier="medium",
                details={"max_words": str(max_words), "word_count": str(wc)},
            ))

    req_cfg = ((dtc_cfg.get("validators") or {}).get("required_sections") or [])
    whole = "\n\n".join([b.text for b in ir.blocks]).lower()
    for item in req_cfg:
        name = str(item.get("name", "")).strip()
        sev = str(item.get("severity", "warning")).lower()
        if name and name.lower() not in whole:
            findings.append(Finding(
                rule_id="dtc.required_section.missing",
                severity="critical" if sev == "critical" else "warning",
                category="dtc_style",
                message=f"Missing section: {name}",
                risk_tier="high" if sev == "critical" else "medium",
                details={"section": name},
            ))

    # Caption lint
    for block in ir.blocks:
        txt = block.text
        for m in re.finditer(r"\bFigure\s+(\d+)(?!-)", txt):
            findings.append(Finding(
                rule_id="dtc.captions.figure_format",
                severity="warning",
                category="dtc_style",
                message="Figure caption should use Chapter-Figure format (e.g., Figure 3-1).",
                ref=block.ref,
                before=txt[max(0, m.start()-25):m.end()+25],
                risk_tier="low",
                details={"anchor": block.anchor},
            ))
        for m in re.finditer(r"\bTable\s+(\d+)(?!-)", txt):
            findings.append(Finding(
                rule_id="dtc.captions.table_format",
                severity="warning",
                category="dtc_style",
                message="Table caption should use Chapter-Table format (e.g., Table 3-1).",
                ref=block.ref,
                before=txt[max(0, m.start()-25):m.end()+25],
                risk_tier="low",
                details={"anchor": block.anchor},
            ))

    # Digital twin capitalization lint
    cap_cfg = ((dtc_cfg.get("validators") or {}).get("capitalization") or {})
    if cap_cfg.get("digital_twin_common_noun", True):
        patt = re.compile(r"\b(a|an|the)\s+Digital Twin\b(?!\s+Consortium)", re.IGNORECASE)
        for block in ir.blocks:
            for m in patt.finditer(block.text):
                snippet = block.text[max(0, m.start()-25):min(len(block.text), m.end()+25)]
                findings.append(Finding(
                    rule_id="dtc.capitalization.digital_twin_common_noun",
                    severity="info",
                    category="dtc_style",
                    message="Common noun 'digital twin' should be lowercase (except proper nouns).",
                    ref=block.ref,
                    before=snippet,
                    risk_tier="low",
                    details={"anchor": block.anchor},
                ))
    return findings

def lint_prose_candidates(ir: DocumentIR) -> List[Finding]:
    findings: List[Finding] = []
    for block in ir.blocks:
        if not block.text.strip():
            continue
        sentences = re.split(r"(?<=[.!?])\s+", block.text.strip())
        for s in sentences:
            if len(s.split()) < 6:
                continue
            wc = len(s.split())
            cc = _subordinate_clause_count(s)
            if wc > 35 or cc > 2:
                findings.append(Finding(
                    rule_id="prose.runon_or_complex",
                    severity="warning",
                    category="prose_quality",
                    message=f"Possible run-on/complex sentence (words={wc}, clauses~={cc}).",
                    ref=block.ref,
                    before=s,
                    risk_tier="medium" if wc <= 55 else "high",
                    details={"words": str(wc), "clause_estimate": str(cc), "anchor": block.anchor},
                ))
            for pat in _THROAT_CLEARING:
                if re.search(pat, s):
                    findings.append(Finding(
                        rule_id="prose.throat_clearing_opening",
                        severity="info",
                        category="prose_quality",
                        message="Throat-clearing / pompous opening.",
                        ref=block.ref,
                        before=s,
                        risk_tier="low",
                        details={"anchor": block.anchor},
                    ))
                    break
    return findings
