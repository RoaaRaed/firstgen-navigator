"""Smoke test of the My Plan page with a stand-in for Streamlit (the real look is checked by
running the app)."""
import datetime as dt
import sys
from unittest.mock import MagicMock

import pytest

from app import strings
from core.rules import load_rules
from core.tools import load_context

ANSWERS = {"stage": "applying", "work_hours": "over_30", "family": "children",
           "financial_aid": "not_eligible_or_unsure", "needs": ["paying", "deadlines"]}
MODULES = ("app.plan_page", "app.chat_page")


def _forget(import_name_parts=MODULES):
    import app

    for name in import_name_parts:
        sys.modules.pop(name, None)
        if hasattr(app, name.split(".")[1]):
            delattr(app, name.split(".")[1])


@pytest.fixture
def load_page(monkeypatch):
    def _load(state):
        st = MagicMock()
        st.session_state = state
        st.cache_resource = lambda **kw: (lambda f: f)
        monkeypatch.setitem(sys.modules, "streamlit", st)
        _forget()
        from app import plan_page

        ctx = load_context("demo-ccc")
        monkeypatch.setattr(plan_page, "_context", lambda: ctx)
        monkeypatch.setattr(plan_page, "_ruleset", lambda: load_rules(ctx.root / "rules.yaml"))
        return plan_page, st
    yield _load
    _forget()


def state(**extra):
    return {"answers": dict(ANSWERS), "q_index": 7, "page": "plan", "lang": "en", **extra}


@pytest.mark.parametrize("lang", ["en", "ar"])
def test_plan_page_shows_the_plan_and_offers_the_pdf(load_page, monkeypatch, lang):
    page, st = load_page(state(lang=lang))
    monkeypatch.setattr(page.pdf, "plan_to_pdf", lambda plan, s, l: b"%PDF-fake")
    page.render_page(strings.load_strings(lang), lang)
    st.download_button.assert_called_once()
    assert st.download_button.call_args.kwargs["data"] == b"%PDF-fake"
    assert st.download_button.call_args.kwargs["mime"] == "application/pdf"
    assert st.download_button.call_args.kwargs["file_name"] == f"my-plan-{lang}.pdf"
    st.warning.assert_not_called()


def test_a_pdf_failure_shows_a_warning_and_the_page_still_works(load_page, monkeypatch):
    page, st = load_page(state())

    def boom(plan, s, l):
        raise RuntimeError("pip install arabic-reshaper python-bidi")

    monkeypatch.setattr(page.pdf, "plan_to_pdf", boom)
    page.render_page(strings.load_strings("en"), "en")
    st.download_button.assert_not_called()
    st.warning.assert_called_once()
    assert "arabic-reshaper" in st.warning.call_args.args[0]
    assert st.markdown.called  # the plan itself is still shown


def test_a_student_with_no_answers_sees_the_hint(load_page, monkeypatch):
    page, st = load_page(state(answers={}))
    monkeypatch.setattr(page.pdf, "plan_to_pdf", lambda plan, s, l: b"%PDF")
    page.render_page(strings.load_strings("en"), "en")
    st.info.assert_called_once()


def test_the_plan_page_buttons_go_back_to_chat_or_answers(load_page, monkeypatch):
    page, st = load_page(state())
    monkeypatch.setattr(page.pdf, "plan_to_pdf", lambda plan, s, l: b"%PDF")
    page.render_page(strings.load_strings("en"), "en")
    keys = [c.kwargs.get("key") for c in st.button.call_args_list]
    assert keys == ["plan_back_chat_btn", "plan_edit_btn", "plan_clear_btn"]


def test_open_plan_and_open_chat_switch_pages():
    from app import wizard

    s = {"page": "chat"}
    wizard.open_plan(s)
    assert s["page"] == "plan"
    wizard.open_chat(s)
    assert s["page"] == "chat"


def test_plan_strings_exist_in_both_languages():
    for lang in ("en", "ar"):
        s = strings.load_strings(lang)
        for key in ("title", "open", "about", "steps", "dates", "programs", "contacts", "download", "empty"):
            assert strings.t(s, f"plan.{key}").strip() and strings.t(s, f"plan.{key}") != f"plan.{key}"
        assert "2026" in strings.t(s, "plan.prepared", date="2026-11-16")
        assert "5" in strings.t(s, "plan.page", n=5)
