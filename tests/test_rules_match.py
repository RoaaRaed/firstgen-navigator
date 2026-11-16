"""match_rules: which rules from rules.yaml apply to a student's answers."""
from pathlib import Path

import pytest

from core.rules import load_rules, match_rules, rule_matches

RULES = load_rules(Path("institutions/demo-ccc/rules.yaml"))


def ids(answers):
    return [r.id for r in match_rules(RULES, answers)]


def test_no_answers_match_nothing():
    assert ids({}) == []


def test_single_choice_condition():
    assert ids({"work_hours": "over_30"}) == ["working_over_20"]
    assert ids({"work_hours": "h1_10"}) == []


def test_family_rule_matches_either_caring_option_but_not_other():
    assert ids({"family": "children"}) == ["caregiver"]
    assert ids({"family": "parents_siblings"}) == ["caregiver"]
    assert ids({"family": "other"}) == []


def test_match_any_rule_fires_on_stage_or_on_multi_choice_need():
    assert ids({"stage": "transfer"}) == ["transfer_student"]
    assert ids({"needs": ["paying", "transfer"]}) == ["transfer_student"]
    assert ids({"stage": "first_year", "needs": ["paying"]}) == []


def test_multi_choice_answer_checks_every_pick():
    assert ids({"needs": ["classes", "deadlines"]}) == ["deadlines_first"]


def test_most_important_rule_comes_first_and_ties_keep_file_order():
    got = ids({"financial_aid": "not_eligible_or_unsure", "work_hours": "over_30",
               "family": "children", "stage": "applying"})
    assert got[0] == "financial_aid_unsure"                       # priority 1
    assert got == ["financial_aid_unsure", "working_over_20", "caregiver", "deadlines_first"]


def test_unknown_values_and_questions_are_ignored():
    assert ids({"work_hours": "banana", "nonsense": "x", "needs": None}) == []


def test_match_all_needs_every_condition():
    rule = next(r for r in RULES.rules if r.id == "working_over_20")
    two = rule.model_copy(update={"match": "all", "conditions": rule.conditions + [
        rule.conditions[0].model_copy(update={"question": "family", "any_of": ["children"]})]})
    assert not rule_matches(two, {"work_hours": "over_30"})
    assert rule_matches(two, {"work_hours": "over_30", "family": "children"})
