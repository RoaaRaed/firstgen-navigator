"""Smoke test of the chat page with a stand-in for Streamlit: catches typos and wrong keys in
the page code without a browser. The real look is checked by running the app."""
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app import render, strings
from core.schema import AdvisorAnswer, Citation


def fake_streamlit(state, typed=None):
    st = MagicMock()
    st.session_state = state
    st.cache_resource = lambda **kw: (lambda f: f)  # no caching in the test
    st.chat_input.return_value = typed
    return st


@pytest.fixture
def load_page(monkeypatch):
    def _load(state, typed=None):
        st = fake_streamlit(state, typed)
        monkeypatch.setitem(sys.modules, "streamlit", st)
        import app

        sys.modules.pop("app.chat_page", None)
        if hasattr(app, "chat_page"):  # `from app import x` would otherwise return the old module
            delattr(app, "chat_page")
        from app import chat_page

        return chat_page, st
    yield _load
    import app

    sys.modules.pop("app.chat_page", None)
    if hasattr(app, "chat_page"):
        delattr(app, "chat_page")


def base_state(**extra):
    return {"answers": {"stage": "applying"}, "q_index": 7, "page": "chat", "lang": "en", **extra}


def good_result():
    return SimpleNamespace(
        answer=AdvisorAnswer(answer="The MAP grant closes soon.", confidence="High",
                             citations=[Citation(source_id="state-isac-map::03", label="MAP")],
                             next_steps=["File early"]),
        tool_calls=[{"name": "search_knowledge_base", "args": {}, "result": {"results": [
            {"source_id": "state-isac-map::03", "title": "MAP", "source_url": "https://isac.org", "text": "x"}]}}])


@pytest.mark.parametrize("lang", ["en", "ar"])
def test_empty_chat_shows_examples_and_no_error(load_page, lang):
    page, st = load_page(base_state(lang=lang))
    page.render_page(strings.load_strings(lang), lang)
    assert st.button.call_count >= 3  # the three example questions
    st.error.assert_not_called()


def test_a_question_is_answered_and_stored(load_page, monkeypatch):
    state = base_state()
    page, st = load_page(state, typed="When is the MAP deadline?")
    monkeypatch.setattr(page.advisor, "answer", lambda agent, q, lang: (good_result(), 2.0))
    monkeypatch.setattr(page, "_agent", lambda lang: object())
    page.render_page(strings.load_strings("en"), "en")
    assert [m["role"] for m in state["messages"]] == ["user", "assistant"]
    assert state["messages"][1]["cards"][0]["url"] == "https://isac.org"
    st.error.assert_not_called()


def test_an_example_button_becomes_the_question(load_page, monkeypatch):
    state = base_state(pending_question="Where can I get help with food?")
    page, st = load_page(state, typed=None)
    seen = []
    monkeypatch.setattr(page.advisor, "answer", lambda agent, q, lang: (seen.append(q) or good_result(), 1.0))
    monkeypatch.setattr(page, "_agent", lambda lang: object())
    page.render_page(strings.load_strings("en"), "en")
    assert seen == ["Where can I get help with food?"] and "pending_question" not in state


def test_a_crash_shows_an_error_and_keeps_the_history_clean(load_page, monkeypatch):
    state = base_state()
    page, st = load_page(state, typed="hi")

    def boom(*a):
        raise RuntimeError("GROQ_API_KEY is not set")

    monkeypatch.setattr(page.advisor, "answer", boom)
    monkeypatch.setattr(page, "_agent", lambda lang: object())
    page.render_page(strings.load_strings("en"), "en")
    st.error.assert_called_once()
    assert "GROQ_API_KEY" in st.error.call_args.args[0]
    assert state["messages"] == []


def test_a_fallback_answer_shows_the_friendly_warning_not_the_raw_text(load_page):
    from tests.fake_langchain import install

    install()
    from core.agent import _safe_fallback

    fallback = render.assistant_message(SimpleNamespace(answer=_safe_fallback("RateLimitError"), tool_calls=[]), 1.0)
    state = base_state(messages=[{"role": "user", "content": "q"}, fallback])
    page, st = load_page(state)
    page.render_page(strings.load_strings("ar"), "ar")
    st.warning.assert_called_once()
    assert "RateLimitError" not in str(st.write.call_args_list)


def test_page_warm_up_hands_the_context_to_advisor(load_page, monkeypatch):
    page, _ = load_page(base_state())
    got = []
    monkeypatch.setattr(page, "_context", lambda: "the-context")
    monkeypatch.setattr(page.advisor, "warm_up", lambda ctx: got.append(ctx))
    page.warm_up()
    assert got == ["the-context"]
