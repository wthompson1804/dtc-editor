"""
Style Polish Module

Runs the surgical linter pipeline on a document IR to ensure
DTC/AP style conformance. This is designed to be run AFTER
the holistic reauthoring pipeline to catch any style issues
in the LLM-rewritten content.

The key insight: Holistic validates per-chunk, but some issues
only emerge when chunks are assembled. This module catches those.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Set, Optional, Dict, Any
from pathlib import Path
import logging

from dtc_editor.ir import DocumentIR, Finding, EditOp
from dtc_editor.rules.load_rules import load_rule_pack, load_replacement_rules
from dtc_editor.lint import lint_dtc, lint_prose_candidates
from dtc_editor.propose import propose_from_rules
from dtc_editor.apply import apply_editops
from dtc_editor.verify import verify_invariants

logger = logging.getLogger(__name__)


@dataclass
class StylePolishConfig:
    """Configuration for the style polish pass."""
    # Rule paths (defaults to bundled rules)
    rules_dtc_path: Optional[str] = None
    rules_prose_path: Optional[str] = None

    # Protected terms to preserve
    protected_terms: Set[str] = field(default_factory=set)

    # Vale linting (optional)
    use_vale: bool = True
    vale_config_path: Optional[str] = None

    # What to include
    apply_deterministic: bool = True  # Apply deterministic fixes
    report_only: bool = False         # If True, only report findings without applying


@dataclass
class StylePolishResult:
    """Result of the style polish pass."""
    # Input/output
    input_ir: DocumentIR
    output_ir: DocumentIR

    # What was found and fixed
    findings: List[Finding]
    editops: List[EditOp]

    # Stats
    findings_count: int
    editops_applied: int
    editops_rejected: int

    # Summary for reporting
    summary: str


def run_style_polish(
    ir: DocumentIR,
    config: StylePolishConfig,
) -> StylePolishResult:
    """
    Run the surgical linter on a document IR.

    This is typically called after run_holistic_pipeline() to ensure
    the LLM-rewritten content conforms to DTC/AP style guidelines.

    Args:
        ir: Document intermediate representation (e.g., from holistic pipeline)
        config: Style polish configuration

    Returns:
        StylePolishResult with the polished IR and statistics
    """
    logger.info("Starting style polish pass")

    # Load rules
    rules_dtc_path = config.rules_dtc_path or str(
        Path(__file__).parent / "rules" / "dtc_rules.yml"
    )
    rules_prose_path = config.rules_prose_path or str(
        Path(__file__).parent / "rules" / "prose_rules.yml"
    )

    dtc_pack = load_rule_pack(rules_dtc_path)
    prose_pack = load_rule_pack(rules_prose_path)

    # Lint the document
    findings: List[Finding] = []
    findings.extend(lint_dtc(ir, dtc_pack))
    findings.extend(lint_prose_candidates(ir))

    logger.info(f"Style polish: found {len(findings)} potential issues")

    # Vale linting (if enabled)
    vale_ops: List[EditOp] = []
    if config.use_vale:
        try:
            from dtc_editor.adapters.vale_adapter import run_vale, ValeConfig

            vale_config_path = config.vale_config_path
            if not vale_config_path:
                default_vale = Path(__file__).parent.parent / "rules" / "vale" / ".vale.ini"
                if default_vale.exists():
                    vale_config_path = str(default_vale)

            if vale_config_path:
                vale_config = ValeConfig(styles_path=vale_config_path)
                vale_result = run_vale(ir, vale_config)
                findings.extend(vale_result.findings)
                vale_ops = vale_result.editops
                logger.info(f"Vale: found {len(vale_result.findings)} issues, {len(vale_ops)} auto-fixable")
        except Exception as e:
            logger.warning(f"Vale linting failed: {e}")

    # If report-only mode, return without applying changes
    if config.report_only:
        return StylePolishResult(
            input_ir=ir,
            output_ir=ir,
            findings=findings,
            editops=[],
            findings_count=len(findings),
            editops_applied=0,
            editops_rejected=0,
            summary=f"Report only: {len(findings)} findings (no changes applied)",
        )

    # Propose deterministic edits
    ops: List[EditOp] = []
    if config.apply_deterministic:
        dtc_rules = load_replacement_rules(dtc_pack)
        prose_rules = load_replacement_rules(prose_pack)
        ops = propose_from_rules(ir, dtc_rules + prose_rules, config.protected_terms)
        logger.info(f"Proposed {len(ops)} deterministic edits")

    # Add Vale-generated EditOps
    ops.extend(vale_ops)

    # Apply edits
    output_ir, ops = apply_editops(ir, ops)

    # Verify invariants
    verification_findings = verify_invariants(ops, config.protected_terms)
    findings.extend(verification_findings)

    # Calculate stats
    applied = sum(1 for o in ops if o.status == "applied")
    rejected = sum(1 for o in ops if o.status == "rejected")

    logger.info(f"Style polish complete: {applied} edits applied, {rejected} rejected")

    # Build summary
    if applied == 0:
        summary = "No style issues found or all were already correct"
    else:
        summary = f"Applied {applied} style fixes ({rejected} rejected)"

    return StylePolishResult(
        input_ir=ir,
        output_ir=output_ir,
        findings=findings,
        editops=ops,
        findings_count=len(findings),
        editops_applied=applied,
        editops_rejected=rejected,
        summary=summary,
    )


def generate_polish_report(result: StylePolishResult) -> str:
    """
    Generate a markdown report of the style polish pass.

    Args:
        result: Style polish result

    Returns:
        Markdown-formatted report
    """
    lines = []
    lines.append("## Style Polish Report")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Findings | {result.findings_count} |")
    lines.append(f"| Edits Applied | {result.editops_applied} |")
    lines.append(f"| Edits Rejected | {result.editops_rejected} |")
    lines.append("")

    if result.editops_applied > 0:
        lines.append("### Applied Fixes")
        lines.append("")
        applied = [o for o in result.editops if o.status == "applied"]
        for op in applied[:20]:  # Limit to first 20
            lines.append(f"- **{op.intent}**: `{op.before[:50]}...` → `{op.after[:50]}...`")
        if len(applied) > 20:
            lines.append(f"- ... and {len(applied) - 20} more")
        lines.append("")

    if result.findings:
        # Group findings by category
        by_category: Dict[str, List[Finding]] = {}
        for f in result.findings:
            cat = f.category or "other"
            by_category.setdefault(cat, []).append(f)

        lines.append("### Findings by Category")
        lines.append("")
        for cat, cat_findings in sorted(by_category.items()):
            lines.append(f"**{cat}** ({len(cat_findings)})")
            for f in cat_findings[:5]:
                lines.append(f"  - [{f.severity}] {f.message}")
            if len(cat_findings) > 5:
                lines.append(f"  - ... and {len(cat_findings) - 5} more")
            lines.append("")

    return "\n".join(lines)
