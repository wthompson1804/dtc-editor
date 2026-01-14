from dtc_editor.rules.load_rules import load_rule_pack
from dtc_editor.persnicketybot import assert_style_guide_coverage

def test_persnickety():
    pack = load_rule_pack("dtc_editor/rules/dtc_rules.yml")
    res = assert_style_guide_coverage(pack)
    assert res.ok
