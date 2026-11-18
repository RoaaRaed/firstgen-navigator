"""core/compact.py: the short text the model reads for each tool result."""
import json

from core import compact
from core.tools import load_context
from core.tools import lookup_deadlines, match_programs, escalate_to_human, search_knowledge_base
import datetime as dt
from types import SimpleNamespace


def _hits(n=8):
    meta = {"doc_id": "state-isac-alternative-application", "title": "Alternative Application for Illinois Financial Aid",
            "section": "Alternative Application for Illinois Financial Aid > What is the Alternative Application?",
            "layer": "state", "source_url": "https://www.isac.org/students/alternative-application/",
            "retrieved_date": "2026-10-29", "effective_term": ""}
    text = "The Retention of Illinois Students & Equity (RISE) Act allows certain students who are not eligible for federal aid to apply " * 2
    return [SimpleNamespace(chunk_id=f"state-isac-alternative-application::{i:02d}", doc_id="d", score=0.86 - i / 100,
                            text=text, metadata=meta) for i in range(n)]


def ctx():
    r = SimpleNamespace(search=lambda q, k=8, layer=None, **kw: _hits(k))
    return load_context("demo-ccc", retriever=r, today=dt.date(2026, 11, 18))


def test_search_text_is_much_shorter_than_the_json_and_keeps_what_matters():
    full = search_knowledge_base(ctx(), "alternative application")
    text = compact.for_model("search_knowledge_base", full)
    json_len = len(json.dumps(full, ensure_ascii=False))
    assert len(text) < 0.65 * json_len
    first = text.splitlines()[0]
    assert first.startswith("[state-isac-alternative-application::00]")
    assert "retrieved 2026-10-29" in first and "term: not stated" in first and "state;" in first
    assert "http" not in text and "0.86" not in text
    assert first.count("Alternative Application for Illinois Financial Aid") == 1   # the title is not repeated


def test_deadlines_text_has_the_date_the_past_flag_and_today():
    full = lookup_deadlines(ctx(), term="Spring 2027", topic="first day")
    text = compact.for_model("lookup_deadlines", full)
    assert text.splitlines()[0] == "today: 2026-11-18"
    assert "[deadlines:ccc-spring27-first-day-16wk] 2027-01-11 (upcoming)" in text
    assert "http" not in text and len(text) < 0.6 * len(json.dumps(full))


def test_programs_and_escalate_text_keep_phone_hours_office_and_id():
    c = ctx()
    text = compact.for_model("match_programs", match_programs(c, tags=["caregiver"]))
    assert "[programs:" in text and "http" not in text
    esc = compact.for_model("escalate_to_human", escalate_to_human(c, "financial_aid"))
    assert esc.startswith("topic: financial_aid; matched: true") and "[programs:ccc-financial-aid-offices]" in esc


def test_nothing_found_says_so_and_keeps_the_hint():
    text = compact.for_model("lookup_deadlines", lookup_deadlines(ctx(), term="Winter 2031"))
    assert text.startswith("found: none") and "Winter 2031" in text and "available_terms" in text
    assert compact.for_model("search_knowledge_base", {"found": False, "error": "query is empty", "results": []}) \
        == "found: none. query is empty"


def test_an_odd_result_never_raises():
    assert compact.for_model("search_knowledge_base", {"results": [{"oops": 1}]}) == '{"results":[{"oops":1}]}'
    assert compact.for_model("unknown_tool", {"a": "ب"}) == '{"a":"ب"}'


def test_unlisted_hours_are_left_out_but_real_hours_and_phone_stay():
    r = {"source_id": "programs:x", "name": "X", "category": "food", "for": ["all students"], "description": "d",
         "contact_office": "Office", "contact_phone": "312-555-0100", "hours": "not listed; check the page"}
    assert "hours" not in compact._program_line(r) and "phone: 312-555-0100" in compact._program_line(r)
    r["hours"] = "Mon-Fri 9-5"
    assert "hours: Mon-Fri 9-5" in compact._program_line(r)
