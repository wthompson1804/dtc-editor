from __future__ import annotations
from typing import Dict, Any, List
from pathlib import Path
from datetime import datetime
from shutil import copy2

from dtc_editor.persnicketybot import assert_style_guide_coverage
from dtc_editor.rules.load_rules import load_rule_pack, load_replacement_rules
from dtc_editor.adapters.docx_adapter import extract_ir_and_inventory, emit_clean_docx, load_protected_terms
from dtc_editor.lint import lint_dtc, lint_prose_candidates
from dtc_editor.propose import propose_from_rules
from dtc_editor.apply import apply_editops
from dtc_editor.verify import verify_invariants, verify_structure
from dtc_editor.redline import create_redline
from dtc_editor.changelog import write_json, write_txt

def run_pipeline(
    *,
    input_docx: str,
    out_dir: str,
    mode: str = "safe",
    author: str = "DTC Editorial Engine",
    prefer_compare_backend: str | None = None,
    rules_dtc_path: str | None = None,
    rules_prose_path: str | None = None,
    protected_terms_path: str | None = None,
    # LLM options
    use_llm: bool = False,
    anthropic_api_key: str | None = None,
    llm_model: str = "claude-sonnet-4-20250514",
    # Google Docs export options
    export_google_docs: bool = False,
    google_credentials: str | None = None,
    google_folder_id: str | None = None,
    # Vale options
    use_vale: bool = False,
    vale_config_path: str | None = None,
) -> Dict[str, Any]:
    ts = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)

    stem = Path(input_docx).stem
    bundle = out / f"{stem}_{ts.replace('-','').replace(':','').replace('T','_')}"
    bundle.mkdir(parents=True, exist_ok=True)

    original_copy = str(bundle / f"{stem}.original.docx")
    clean_path = str(bundle / f"{stem}.clean.docx")
    redline_path = str(bundle / f"{stem}.redline.docx")
    changelog_json = str(bundle / f"{stem}.changelog.json")
    changelog_txt = str(bundle / f"{stem}.changelog.txt")

    copy2(input_docx, original_copy)

    rules_dtc_path = rules_dtc_path or str(Path(__file__).parent / "rules" / "dtc_rules.yml")
    rules_prose_path = rules_prose_path or str(Path(__file__).parent / "rules" / "prose_rules.yml")
    protected_terms_path = protected_terms_path or str(Path(__file__).parent / "rules" / "protected_terms.yml")

    dtc_pack = load_rule_pack(rules_dtc_path)
    prose_pack = load_rule_pack(rules_prose_path)
    protected_terms = load_protected_terms(protected_terms_path)

    checklist = assert_style_guide_coverage(dtc_pack)

    # Parse + pre inventory
    ir, pre_inv = extract_ir_and_inventory(original_copy)

    # Lint
    findings = []
    findings.extend(lint_dtc(ir, dtc_pack))
    findings.extend(lint_prose_candidates(ir))

    # Vale linting (if enabled)
    vale_stats = {"status": "skipped", "findings": 0, "editops": 0}
    vale_ops = []
    if use_vale:
        from dtc_editor.adapters.vale_adapter import run_vale, ValeConfig
        vale_config = ValeConfig(
            styles_path=vale_config_path or str(Path(__file__).parent.parent / "rules" / "vale" / ".vale.ini"),
        )
        vale_result = run_vale(ir, vale_config)
        vale_stats = {
            "status": vale_result.status,
            "findings": len(vale_result.findings),
            "editops": len(vale_result.editops),
            "message": vale_result.message,
        }
        findings.extend(vale_result.findings)
        vale_ops = vale_result.editops

    # Propose deterministic edit ops
    dtc_rules = load_replacement_rules(dtc_pack)
    prose_rules = load_replacement_rules(prose_pack)
    ops = propose_from_rules(ir, dtc_rules + prose_rules, protected_terms)

    # Add Vale-generated EditOps
    ops.extend(vale_ops)

    # LLM proposal step (only in "rewrite" mode with API key)
    llm_stats = {"attempted": 0, "generated": 0}
    if use_llm and mode == "rewrite" and anthropic_api_key:
        from dtc_editor.llm.client import ClaudeClient, LLMConfig
        from dtc_editor.llm.propose_llm import propose_from_llm

        client = ClaudeClient(LLMConfig(
            api_key=anthropic_api_key,
            model=llm_model,
        ))
        prose_findings = [f for f in findings if f.category == "prose_quality"]
        llm_stats["attempted"] = len(prose_findings)
        llm_ops = propose_from_llm(ir, findings, client, protected_terms)
        llm_stats["generated"] = len(llm_ops)
        ops.extend(llm_ops)

    # Apply deterministically
    ir, ops = apply_editops(ir, ops)

    # Emit clean
    emit_clean_docx(original_copy, ir, clean_path)

    # Post inventory (re-parse emitted doc)
    ir2, post_inv = extract_ir_and_inventory(clean_path)

    # Verification
    findings.extend(verify_invariants(ops, protected_terms))
    findings.extend(verify_structure(pre_inv, post_inv))

    # Redline
    redline = create_redline(original_copy, clean_path, redline_path, author=author, prefer_backend=prefer_compare_backend)

    # Google Docs export (if requested)
    google_result = None
    if export_google_docs and google_credentials:
        from dtc_editor.adapters.google_adapter import upload_to_google_drive, GoogleExportConfig
        google_config = GoogleExportConfig(
            credentials_path=google_credentials,
            folder_id=google_folder_id,
        )
        google_result = upload_to_google_drive(clean_path, google_config, title=ir.title or stem)

    # Build artifacts dict
    artifacts = {
        "original_docx": original_copy,
        "clean_docx": clean_path,
        "redline_docx": (redline_path if redline.status == "ok" else None),
    }
    if google_result and google_result.status == "ok":
        artifacts["google_doc_url"] = google_result.web_view_link

    payload: Dict[str, Any] = {
        "timestamp_utc": ts,
        "mode": mode,
        "persnicketybot": {"ok": checklist.ok, "missing": checklist.missing, "notes": checklist.notes},
        "artifacts": artifacts,
        "redline_engine": {"backend": redline.backend, "status": redline.status, "message": redline.message},
        "google_export": {
            "status": google_result.status if google_result else "skipped",
            "file_id": google_result.file_id if google_result else None,
            "web_view_link": google_result.web_view_link if google_result else None,
            "message": google_result.message if google_result else "Export not requested",
        } if export_google_docs else None,
        "llm": {
            "enabled": use_llm and mode == "rewrite",
            "model": llm_model if use_llm else None,
            "prose_candidates_attempted": llm_stats["attempted"],
            "editops_generated": llm_stats["generated"],
        },
        "vale": vale_stats if use_vale else None,
        "stats": {
            "editops_total": len(ops),
            "editops_applied": sum(1 for o in ops if o.status=="applied"),
            "editops_rejected": sum(1 for o in ops if o.status=="rejected"),
            "editops_llm": sum(1 for o in ops if o.engine=="llm_proposal"),
            "editops_vale": sum(1 for o in ops if o.engine=="vale"),
            "findings_total": len(findings),
        },
        "structure": {"pre": pre_inv.__dict__, "post": post_inv.__dict__},
        "findings": [ _finding_to_dict(f) for f in findings ],
        "editops": [ o.to_dict() for o in ops ],
    }

    write_json(changelog_json, payload)
    write_txt(changelog_txt, payload)
    return payload

def _finding_to_dict(f):
    return {
        "rule_id": f.rule_id, "severity": f.severity, "category": f.category, "message": f.message,
        "ref": None if f.ref is None else {"block_type": f.ref.block_type, "doc_index": f.ref.doc_index, "block_index": f.ref.block_index},
        "before": f.before, "after": f.after, "risk_tier": f.risk_tier, "details": f.details,
    }
