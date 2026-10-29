from pathlib import Path

import pytest

from core.rules import check_references, load_rules

ROOT = Path("institutions/demo-ccc")
RULES = ROOT / "rules.yaml"
EN = Path("app/i18n/en.json")


def test_five_rules_load():
    assert len(load_rules(RULES).rules) == 5


def test_every_reference_exists():
    assert check_references(load_rules(RULES), EN, ROOT / "kb") == []


def test_every_next_step_is_bilingual():
    for rule in load_rules(RULES).rules:
        for step in rule.next_steps:
            assert step.en.strip() and step.ar.strip()


def test_unsure_rule_never_asks_status_and_hands_off():
    rule = next(r for r in load_rules(RULES).rules if r.id == "financial_aid_unsure")
    assert rule.handoff is not None
    assert any("immigration status" in m for m in rule.must_not)


def test_bad_option_id_is_caught(tmp_path):
    bad = tmp_path / "rules.yaml"
    bad.write_text(
        "version: 0\nrules:\n  - id: x\n    description: d\n    conditions:\n"
        "      - question: work_hours\n        any_of: [over_999]\n",
        encoding="utf-8",
    )
    problems = check_references(load_rules(bad), EN, ROOT / "kb")
    assert any("over_999" in p for p in problems)


def test_unknown_tag_is_rejected(tmp_path):
    bad = tmp_path / "rules.yaml"
    bad.write_text(
        "version: 0\nrules:\n  - id: x\n    description: d\n    add_profile_tags: [rich]\n"
        "    conditions:\n      - question: stage\n        any_of: [transfer]\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_rules(bad)
