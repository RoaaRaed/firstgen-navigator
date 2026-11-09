"""Tests for the four advisor tools. Real tables, fake search index (no model needed)."""
import datetime as dt
from pathlib import Path

import pytest

from core.retriever import Hit
from core.tools import (escalate_to_human, load_context, lookup_deadlines, match_programs,
                        search_knowledge_base)
from core.tools.escalate import resolve_topic

TODAY = dt.date(2026, 11, 9)


class FakeRetriever:
    def __init__(self):
        self.calls = []

    def search(self, query, k=5, layer=None, **kw):
        self.calls.append({"query": query, "k": k, "layer": layer})
        meta = {"doc_id": "state-isac-map", "title": "MAP", "section": "MAP > Eligibility",
                "layer": "state", "source_url": "https://www.isac.org/map", "retrieved_date": "2026-10-29",
                "effective_term": ""}
        return [Hit("state-isac-map::03", "state-isac-map", 0.86, "word " * 400, meta)]


@pytest.fixture
def ctx():
    return load_context("demo-ccc", retriever=FakeRetriever(), today=TODAY)


# ---------- search_knowledge_base ----------

def test_search_returns_citable_source_ids_and_metadata(ctx):
    out = search_knowledge_base(ctx, "What is MAP?")
    r = out["results"][0]
    assert out["found"] and r["source_id"] == "state-isac-map::03"
    assert r["source_url"] and r["retrieved_date"] and r["effective_term"] == "not stated"
    assert len(r["text"]) <= 154  # long chunks are shortened


def test_search_uses_8_results_and_passes_layer(ctx):
    search_knowledge_base(ctx, "MAP", layer="state")
    assert ctx.retriever.calls[-1] == {"query": "MAP", "k": 8, "layer": "state"}
    search_knowledge_base(ctx, "MAP", layer="all")
    assert ctx.retriever.calls[-1]["layer"] is None


def test_search_rejects_bad_input_without_crashing(ctx):
    assert search_knowledge_base(ctx, "MAP", layer="city")["found"] is False
    assert search_knowledge_base(ctx, "   ")["found"] is False


# ---------- lookup_deadlines ----------

def test_drop_means_withdrawal(ctx):
    out = lookup_deadlines(ctx, term="Spring 2027", topic="drop")
    ids = [r["source_id"] for r in out["results"]]
    assert ids[0] == "deadlines:ccc-spring27-withdrawal-16wk"
    assert out["results"][0]["date"] == "2027-04-08"


def test_spring_first_day(ctx):
    out = lookup_deadlines(ctx, term="spring 2027", topic="first day")
    assert out["results"][0]["source_id"] == "deadlines:ccc-spring27-first-day-16wk"
    assert out["results"][0]["date"] == "2027-01-11"


def test_past_dates_are_flagged(ctx):
    out = lookup_deadlines(ctx, topic="court ruling")
    row = next(r for r in out["results"] if r["source_id"] == "deadlines:state-court-ruling-2026-07-24")
    assert row["is_past"] is True


def test_unknown_term_lists_available_terms(ctx):
    out = lookup_deadlines(ctx, term="Summer 2030")
    assert out["found"] is False and "Spring 2027" in out["available_terms"]


def test_unknown_topic_is_not_found(ctx):
    out = lookup_deadlines(ctx, topic="bookstore hours")
    assert out["found"] is False and out["results"] == []


# ---------- match_programs ----------

def test_caregiver_gets_childcare_and_food(ctx):
    out = match_programs(ctx, tags=["caregiver"], categories=["food", "childcare"])
    ids = [r["source_id"] for r in out["results"]]
    assert ids[0] == "programs:ccc-child-care-referrals"
    assert "programs:ccc-food-pantries" in ids


def test_fafsa_unsure_gets_alternative_application(ctx):
    out = match_programs(ctx, tags=["fafsa_ineligible_or_unsure"])
    ids = {r["source_id"] for r in out["results"]}
    assert {"programs:il-alternative-application", "programs:ccc-undocumented-student-services"} <= ids


def test_unknown_tags_are_reported_not_crashing(ctx):
    out = match_programs(ctx, tags=["rich"], categories=["parking"])
    assert out["found"] is False and set(out["ignored"]) == {"rich", "parking"}


# ---------- escalate_to_human ----------

def test_handoff_topics_point_to_real_programs(ctx):
    for key, cfg in ctx.handoffs["topics"].items():
        for pid in [cfg["program"]] + ([cfg["also"]] if cfg.get("also") else []):
            assert ctx.program(pid) is not None, f"handoffs.yaml topic '{key}' -> unknown program '{pid}'"
    assert ctx.handoffs["default"] in ctx.handoffs["topics"]


def test_immigration_handoff_is_sensitive_and_cites_contacts(ctx):
    out = escalate_to_human(ctx, "DACA")
    assert out["topic"] == "immigration" and out["sensitive"] is True
    assert out["contacts"][0]["source_id"] == "programs:ccc-undocumented-student-services"


def test_topic_matching(ctx):
    assert resolve_topic(ctx.handoffs, "financial aid office") == ("financial_aid", True)
    assert resolve_topic(ctx.handoffs, "Child care") == ("childcare", True)
    assert resolve_topic(ctx.handoffs, "parking") == ("academic", False)


# ---------- all tools ----------

def test_every_result_has_a_source_id(ctx):
    outs = [search_knowledge_base(ctx, "MAP"), lookup_deadlines(ctx, topic="FAFSA"),
            match_programs(ctx, categories=["financial"])]
    for out in outs:
        assert out["results"] and all(r["source_id"] for r in out["results"])
    assert all(c["source_id"].startswith("programs:") for c in escalate_to_human(ctx, "food")["contacts"])


def test_tools_have_docstrings_for_the_agent():
    for fn in (search_knowledge_base, lookup_deadlines, match_programs, escalate_to_human):
        assert fn.__doc__ and "Args:" in fn.__doc__ and "Returns:" in fn.__doc__
