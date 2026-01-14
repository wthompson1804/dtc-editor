from __future__ import annotations
from typing import Dict, Any, List
import json

def write_json(path: str, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

def write_txt(path: str, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(render_txt(payload))

def render_txt(payload: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"Review Bundle — {payload.get('timestamp_utc')}")
    lines.append("")
    a = payload.get("artifacts", {})
    lines.append("Artifacts")
    lines.append(f"- Original: {a.get('original_docx')}")
    lines.append(f"- Clean:    {a.get('clean_docx')}")
    lines.append(f"- Redline:  {a.get('redline_docx') or '[not generated]'}")
    lines.append("")
    p = payload.get("persnicketybot", {})
    lines.append("PersnicketyBot")
    lines.append(f"- OK: {p.get('ok')}")
    if p.get("missing"):
        lines.append(f"- Missing: {', '.join(p.get('missing'))}")
    for n in p.get("notes", []) or []:
        lines.append(f"- Note: {n}")
    lines.append("")
    r = payload.get("redline_engine", {})
    lines.append("Redline Generation")
    lines.append(f"- Backend: {r.get('backend')}")
    lines.append(f"- Status:  {r.get('status')}")
    lines.append(f"- Notes:   {r.get('message')}")
    lines.append("")
    stats = payload.get("stats", {})
    lines.append("Stats")
    for k, v in stats.items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    findings = payload.get("findings", []) or []
    if findings:
        lines.append("Findings")
        for fnd in findings[:60]:
            lines.append(f"- [{fnd['severity'].upper()}] {fnd['category']} {fnd['rule_id']}: {fnd['message']}")
        if len(findings) > 60:
            lines.append(f"... plus {len(findings)-60} more.")
        lines.append("")
    ops = payload.get("editops", []) or []
    if ops:
        lines.append("EditOps (first 50)")
        for op in ops[:50]:
            lines.append(f"- {op['status']}: {op['rule_id']} ({op['intent']}) @ anchor={op['target']['anchor']}")
    return "\n".join(lines)
