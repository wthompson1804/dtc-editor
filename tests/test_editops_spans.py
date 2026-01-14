from dtc_editor.rules.load_rules import load_rule_pack, load_replacement_rules
from dtc_editor.ir import DocumentIR, TextBlock, BlockRef
from dtc_editor.propose import propose_from_rules
from dtc_editor.apply import apply_editops

def test_span_replace_editop():
    pack = load_rule_pack("dtc_editor/rules/dtc_rules.yml")
    rules = load_replacement_rules(pack)
    ir = DocumentIR(title="Test", blocks=[
        TextBlock(ref=BlockRef("paragraph",0,0), style_name="Normal", text="We did this in order to improve.", anchor="a"*16)
    ])
    ops = propose_from_rules(ir, rules, protected_terms=set())
    assert any(o.rule_id == "clarity.in_order_to.to" for o in ops)
    ir2, ops2 = apply_editops(ir, ops)
    assert "to improve" in ir2.blocks[0].text
    assert any(o.status == "applied" for o in ops2)
