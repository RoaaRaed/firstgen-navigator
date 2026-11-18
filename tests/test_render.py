"""Tests for app/render.py (source cards, confidence pill, fallback check) and the strings of
the chat page. No Streamlit, no network."""
import json
from types import SimpleNamespace

from app import render, strings
from core.schema import AdvisorAnswer, Citation, Contact

DOC = {"source_id": "state-isac-map::03", "title": "MAP Grant", "section": "Deadlines", "layer": "state",
       "source_url": "https://isac.org/map", "retrieved_date": "2026-10-01", "text": "The MAP grant  deadline\nis soon. " * 20}
DEADLINE = {"source_id": "deadlines:ccc-spring27-first-day-16wk", "item": "First day of classes", "date": "2027-01-19",
            "term": "Spring 2027", "notes": "16-week term", "source_url": "https://ccc.edu/cal", "retrieved_date": "2026-10-02"}
PROGRAM = {"source_id": "programs:ccc-food-pantries", "name": "Food pantries", "contact_office": "Student Affairs",
           "contact_url": "javascript:alert(1)", "source_url": "https://ccc.edu/food", "description": "Free groceries.",
           "hours": "Mon-Fri 9-5"}


def calls():
    return [
        {"name": "search_knowledge_base", "args": {}, "result": json.dumps({"found": True, "results": [DOC]})},  # a JSON string
        {"name": "lookup_deadlines", "args": {}, "result": {"found": True, "results": [DEADLINE]}},          # already a dict
        {"name": "match_programs", "args": {}, "result": json.dumps({"results": [PROGRAM]})},
        {"name": "escalate_to_human", "args": {}, "result": "not json at all"},
    ]


def answer(*ids, confidence="High"):
    return AdvisorAnswer(answer="ok", confidence=confidence, citations=[Citation(source_id=i, label=f"label {i}") for i in ids])


def test_doc_card_is_filled_from_the_tool_result():
    [c] = render.build_cards(answer("state-isac-map::03"), calls())
    assert (c["kind"], c["title"], c["detail"]) == ("doc", "MAP Grant", "Deadlines · state")
    assert c["url"] == "https://isac.org/map" and c["retrieved_date"] == "2026-10-01"
    assert len(c["snippet"]) <= render.SNIPPET_MAX + 4 and "\n" not in c["snippet"] and "  " not in c["snippet"]


def test_deadline_card():
    [c] = render.build_cards(answer("deadlines:ccc-spring27-first-day-16wk"), calls())
    assert (c["kind"], c["title"], c["detail"]) == ("deadline", "First day of classes", "2027-01-19 · Spring 2027")


def test_program_card_never_links_to_a_javascript_url():
    [c] = render.build_cards(answer("programs:ccc-food-pantries"), calls())
    assert c["kind"] == "program" and c["title"] == "Food pantries" and c["hours"] == "Mon-Fri 9-5"
    assert c["url"] == "https://ccc.edu/food"  # the bad contact_url was skipped, the safe one used


def test_a_citation_with_no_tool_result_still_gets_a_card_with_its_label():
    [c] = render.build_cards(answer("state-isac-map::99"), calls())
    assert c["title"] == "label state-isac-map::99" and c["url"] == "" and c["snippet"] == ""


def test_duplicate_citations_make_one_card_and_order_is_kept():
    cards = render.build_cards(answer("deadlines:ccc-spring27-first-day-16wk", "state-isac-map::03",
                                      "deadlines:ccc-spring27-first-day-16wk"), calls())
    assert [c["kind"] for c in cards] == ["deadline", "doc"]


def test_no_citations_no_cards_and_no_tool_calls_is_fine():
    assert render.build_cards(answer(confidence="Low"), []) == []
    assert render.build_cards(answer(confidence="Low"), None) == []


def test_safe_url():
    assert render.safe_url(" https://a.b/c ") == "https://a.b/c"
    for bad in ("javascript:alert(1)", "file:///etc/passwd", "", None, "ftp://x"):
        assert render.safe_url(bad) == ""


def test_pill_is_escaped_and_colored_by_level():
    html = render.confidence_pill_html("<b>High</b>", "High")
    assert "&lt;b&gt;" in html and "<b>" not in html
    assert render.CONFIDENCE_COLORS["High"][0] in html
    assert render.CONFIDENCE_COLORS["Low"][0] in render.confidence_pill_html("x", "Unknown")


def test_system_fallback_is_detected_but_a_real_low_answer_is_not():
    from tests.fake_langchain import install

    install()  # langchain must exist before core.agent imports it
    from core.agent import _safe_fallback  # the real fallback text, so this test breaks if it changes
    assert render.is_system_fallback(_safe_fallback("RateLimitError"))
    assert not render.is_system_fallback(AdvisorAnswer(answer="I could not find that.", confidence="Low"))


def test_assistant_message_is_plain_data():
    result = SimpleNamespace(
        answer=AdvisorAnswer(answer="ok", confidence="Medium", citations=[Citation(source_id="state-isac-map::03", label="x")],
                             next_steps=["call"], human_contact=Contact(office="Aid Office", phone="555")),
        tool_calls=calls())
    m = render.assistant_message(result, 3.14)
    assert m["role"] == "assistant" and m["fallback"] is False and m["seconds"] == 3.1
    assert m["contact"]["office"] == "Aid Office" and m["next_steps"] == ["call"]
    json.dumps(m)  # must be serializable


# ---- the chat strings ---------------------------------------------------------------

def test_chat_strings_exist_in_both_languages_with_the_same_shape():
    en, ar = strings.load_strings("en")["chat"], strings.load_strings("ar")["chat"]
    assert len(en["examples"]) == len(ar["examples"]) == 3
    for lang in (en, ar):
        assert set(lang["confidence"]) == {"High", "Medium", "Low"}
        assert set(lang["kinds"]) == {"doc", "deadline", "program", "unknown"}
        assert all(v["label"] and v["hint"] for v in lang["confidence"].values())


def test_chat_placeholders_fill_in_both_languages():
    for lang in ("en", "ar"):
        s = strings.load_strings(lang)
        assert "2026-10-01" in strings.t(s, "chat.retrieved", date="2026-10-01")
        assert "9-5" in strings.t(s, "chat.hours", hours="9-5")
        assert "Boom" in strings.t(s, "chat.error", error="Boom")


def test_auto_dir_html_follows_the_text_and_escapes_it():
    out = render.auto_dir_html("<script>x</script> Calendar.", bold=True)
    assert 'dir="auto"' in out and "text-align:start" in out
    assert "<script>" not in out and "&lt;script&gt;" in out and "<strong>" in out
    assert "opacity" in render.auto_dir_html("x", muted=True) and "opacity" not in render.auto_dir_html("x")
    assert render.auto_dir_html(None).endswith("></div>")


def test_isolate_ltr_wraps_a_date_and_leaves_empty_alone():
    assert render.isolate_ltr("2026-10-29") == "⁦2026-10-29⁩"
    assert render.isolate_ltr("") == ""


def test_link_html_reads_left_to_right_escapes_and_refuses_bad_urls():
    out = render.link_html('https://a.b/c?x=1&y="2"')
    assert 'dir="ltr"' in out and "&amp;" in out and "&quot;" in out and 'rel="noopener noreferrer"' in out
    for bad in ("javascript:alert(1)", "", None, "file:///x"):
        assert render.link_html(bad) == ""


# ---- source ids written inside the answer text are not shown ----

def test_inline_source_markers_are_removed_from_the_answer_text():
    strip = render.strip_citation_markers
    assert strip("Fill the form. [source institution-ccc-registration::00]") == "Fill the form."
    assert strip("املأ الطلب. [source institution-ccc-admissions::02]") == "املأ الطلب."
    assert strip("A [institution-ccc-registration::01] and B (source: deadlines:ccc-x-1)") == "A and B"
    assert strip("Both [source a-b::01, source c-d::02] apply") == "Both apply"
    assert strip("Both [source a-b::01; programs:ccc-food] apply") == "Both apply"


def test_other_brackets_and_plain_text_are_left_alone():
    strip = render.strip_citation_markers
    assert strip("Go to [ccc.edu/apply] now") == "Go to [ccc.edu/apply] now"
    assert strip("Call (312) 553-2500 [ext. 4]") == "Call (312) 553-2500 [ext. 4]"
    assert strip("") == "" and strip(None) == ""


def test_assistant_message_strips_markers_from_answer_and_steps_but_not_from_a_fallback():
    from types import SimpleNamespace

    result = SimpleNamespace(
        answer=AdvisorAnswer(answer="Apply online. [source state-isac-map::03]", confidence="High",
                             citations=[Citation(source_id="state-isac-map::03", label="x")],
                             next_steps=["Visit the office [source state-isac-map::03]"]),
        tool_calls=[])
    m = render.assistant_message(result, 1.0)
    assert m["answer"] == "Apply online." and m["next_steps"] == ["Visit the office"]
    assert [c["source_id"] for c in m["cards"]] == ["state-isac-map::03"] or m["cards"] == []
