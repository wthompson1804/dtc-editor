from __future__ import annotations
from typing import List, Dict, Tuple
from dtc_editor.ir import DocumentIR
from dtc_editor.editops import EditOp

def apply_editops(ir: DocumentIR, ops: List[EditOp]) -> Tuple[DocumentIR, List[EditOp]]:
    # Group ops by block anchor for deterministic application
    by_anchor: Dict[str, List[EditOp]] = {}
    for op in ops:
        by_anchor.setdefault(op.target.anchor, []).append(op)

    for block in ir.blocks:
        bops = by_anchor.get(block.anchor)
        if not bops:
            continue
        # sort spans descending so offsets remain valid
        span_ops = [o for o in bops if o.op == "replace_span" and o.target.span_start is not None and o.target.span_end is not None]
        span_ops.sort(key=lambda o: (o.target.span_start or 0), reverse=True)

        text = block.text
        for op in span_ops:
            start, end = op.target.span_start, op.target.span_end
            if start is None or end is None or start < 0 or end > len(text) or start >= end:
                op.status = "failed"
                continue
            if text[start:end] != op.before:
                op.status = "rejected"
                op.verification["reason"] = "before_mismatch"
                continue
            text = text[:start] + op.after + text[end:]
            op.status = "applied"
        block.text = text

        # block-level replacements (rare; future)
        for op in [o for o in bops if o.op == "replace_block"]:
            if block.text != op.before:
                op.status = "rejected"
                op.verification["reason"] = "block_before_mismatch"
            else:
                block.text = op.after
                op.status = "applied"

    return ir, ops
