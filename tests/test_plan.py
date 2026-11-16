"""build_plan with the real demo-ccc data (CSV/YAML files; no model, no network)."""
import datetime as dt

import pytest

from app import plan as plan_mod
from app import strings
from core.rules import load_rules
from core.tools import load_context

TODAY = dt.date(2026, 11, 16)
FULL = {"stage": "applying", "work_hours": "over_30", "family": "children",
        "financial_aid": "not_eligible_or_unsure", "needs": ["paying", "deadlines"],
        "notes": "I work nights."}


@pytest.fixture(scope="module")
def ctx():
    c = load_context("demo-ccc")
    c.today = TODAY
    return c


@pytest.fixture(scope="module")
def rules(ctx):
    return load_rules(ctx.root / "rules.yaml")


def build(ctx, rules, answers, lang="en"):
    return plan_mod.build_plan(ctx, rules, strings.load_strings(lang), answers, lang, "City Colleges", today=TODAY)


def test_steps_come_from_the_matching_rules_in_priority_order(ctx, rules):
    p = build(ctx, rules, FULL)
    assert p.matched_rules[0] == "financial_aid_unsure"
    assert p.steps[0].startswith("Read how the FAFSA works")
    assert len(p.steps) == len(set(p.steps)) == 6


def test_steps_are_in_the_plans_language(ctx, rules):
    ar = build(ctx, rules, FULL, "ar")
    assert ar.lang == "ar" and ar.steps[0].startswith("اقرأ كيف بيشتغل")
    assert not any(s.startswith("Read how") for s in ar.steps)


def test_no_answers_means_no_steps_and_no_programs_but_still_dates(ctx, rules):
    p = build(ctx, rules, {})
    assert p.steps == [] and p.about == [] and p.matched_rules == []
    assert p.deadlines and p.programs == [] and p.contacts == []


def test_about_lists_only_answered_questions(ctx, rules):
    p = build(ctx, rules, {"stage": "applying", "notes": "hi"})
    assert p.about == [("Where are you right now?", "Applying now"),
                       ("Anything else you want the advisor to know?", "hi")]


def test_deadlines_are_upcoming_sorted_and_limited(ctx, rules):
    p = build(ctx, rules, FULL)
    dates = [d["date"] for d in p.deadlines]
    assert dates == sorted(dates) and all(d >= TODAY.isoformat() for d in dates)
    assert 0 < len(p.deadlines) <= plan_mod.MAX_DEADLINES
    assert all(d["url"].startswith("http") for d in p.deadlines)


def test_deadlines_follow_the_students_stage(ctx, rules):
    by_id = {d.id: d for d in ctx.deadlines}
    transfer = build(ctx, rules, {"stage": "transfer"})
    for d in transfer.deadlines:
        assert by_id[d["id"]].applies_to in ("transfer", "all")


def test_a_later_today_hides_past_deadlines(ctx, rules):
    far = plan_mod.build_plan(ctx, rules, strings.load_strings("en"), FULL, "en", "x", today=dt.date(2030, 1, 1))
    assert far.deadlines == []


def test_programs_are_real_rows_and_limited(ctx, rules):
    p = build(ctx, rules, FULL)
    ids = {x.id for x in ctx.programs}
    assert 0 < len(p.programs) <= plan_mod.MAX_PROGRAMS
    assert all(x["id"] in ids and x["name"] and x["office"] for x in p.programs)


def test_the_plan_never_lists_immigration_programs_even_when_a_rule_ranks_them(ctx, rules):
    p = build(ctx, rules, FULL)
    by_id = {x.id: x for x in ctx.programs}
    assert all(by_id[x["id"]].category not in plan_mod.PRIVATE_CATEGORIES for x in p.programs + p.contacts)
    text = " ".join(x["name"].lower() for x in p.programs + p.contacts)
    assert "undocumented" not in text and "non-eligible" not in text


def test_handoff_contact_comes_from_handoffs_yaml(ctx, rules):
    p = build(ctx, rules, {"financial_aid": "not_eligible_or_unsure"})
    assert [c["id"] for c in p.contacts] == ["ccc-financial-aid-offices"]
    assert p.contacts[0]["office"] and p.contacts[0]["url"].startswith("http")


def test_no_handoff_rule_means_no_contacts(ctx, rules):
    assert build(ctx, rules, {"work_hours": "over_30"}).contacts == []


def test_arabic_dates_use_slashes_so_the_numbers_keep_their_order():
    assert plan_mod.format_date("2026-11-16", "ar") == "2026/11/16"
    assert plan_mod.format_date("2026-11-16", "en") == "2026-11-16"
