# DTC Editorial Engine vNext2 (0.2.0)

This version strengthens adherence to three principles:

- **Representation beats intelligence**: edits are represented as explicit `EditOp` objects with stable anchors.
- **Constrain model; empower engine**: (rewrite stage remains pluggable) but engine uses deterministic apply of edit ops.
- **Verification is non-optional**: invariants + structural inventory checks + (optional) semantic drift hook.

Pipeline: **Parse → Lint → Propose EditOps → Apply EditOps → Verify → Emit Review Bundle**

Outputs per run:
1) `*.clean.docx`
2) `*.redline.docx` (via compare backend when available)
3) `*.changelog.json` + `*.changelog.txt`

## Quick start

```bash
pip install -e .
dtc-edit input.docx --out ./dtc_out --mode safe
```

## Modes
- **safe**: deterministic style/grammar rules + DTC lint + prose candidate detection + verification + bundle.
- **rewrite**: safe + LLM-proposed rewrite EditOps (stubbed; insert your model client).

## Key files
- `dtc_editor/rules/dtc_rules.yml` (DTC style + deterministic replacements)
- `dtc_editor/rules/prose_rules.yml` (deterministic prose trims)
- `dtc_editor/rules/protected_terms.yml` (protected terms)
- `dtc_editor/editops.py` (EditOp schema)
- `dtc_editor/apply.py` (deterministic applier)
- `dtc_editor/verify.py` (invariants + structure)
