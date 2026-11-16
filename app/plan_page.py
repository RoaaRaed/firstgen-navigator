"""The My Plan page: the plan on screen and a PDF download. Streamlit UI only; the plan itself
is built in app/plan.py and the PDF in app/pdf.py (the tested parts)."""
import datetime as dt

import streamlit as st

from app import advisor, pdf, render, wizard
from app import plan as plan_mod
from app.chat_page import _auto, _context
from app.strings import t


@st.cache_resource(show_spinner=False)
def _ruleset():
    return advisor.get_ruleset(_context())


def _link(url: str) -> None:
    if render.safe_url(url):
        st.markdown(render.link_html(url), unsafe_allow_html=True)


def render_page(strings: dict, lang: str) -> None:
    state = st.session_state
    questions = strings["questionnaire"]["questions"]
    plan = plan_mod.build_plan(_context(), _ruleset(), strings, state["answers"], lang,
                               advisor.INSTITUTION_NAME, today=dt.date.today())

    st.subheader(t(strings, "plan.title"))
    st.caption(t(strings, "plan.subtitle"))
    st.caption(t(strings, "plan.prepared", date=render.isolate_ltr(plan_mod.format_date(plan.prepared_on, lang))))

    try:
        data = pdf.plan_to_pdf(plan, strings, lang)
    except Exception as e:  # e.g. the two Arabic PDF packages are not installed
        st.warning(t(strings, "plan.pdf_error", error=f"{type(e).__name__}: {e}"))
    else:
        st.download_button(t(strings, "plan.download"), data=data, file_name=f"my-plan-{lang}.pdf",
                           mime="application/pdf", type="primary", key="download_plan_btn")

    if plan.about:
        with st.expander(t(strings, "plan.about")):
            for question_text, shown in plan.about:
                st.markdown(f"- **{question_text}** {shown}")

    st.markdown(f"#### {t(strings, 'plan.steps')}")
    if plan.steps:
        st.markdown("\n".join(f"{i}. {step}" for i, step in enumerate(plan.steps, 1)))
    else:
        st.info(t(strings, "plan.empty"))

    if plan.deadlines:
        st.markdown(f"#### {t(strings, 'plan.dates')}")
        for d in plan.deadlines:
            with st.container(border=True):
                _auto(d["item"], bold=True)
                _auto(f"{d['date']} \u00b7 {d['term']}", muted=True)
                _link(d["url"])

    for key, entries in (("plan.programs", plan.programs), ("plan.contacts", plan.contacts)):
        if not entries:
            continue
        st.markdown(f"#### {t(strings, key)}")
        for p in entries:
            with st.container(border=True):
                _auto(p["name"] if key == "plan.programs" else p["office"], bold=True)
                if key == "plan.programs":
                    _auto(p["office"], muted=True)
                if p["phone"]:
                    st.caption(t(strings, "plan.phone", phone=render.isolate_ltr(p["phone"])))
                if p["hours"]:
                    st.caption(t(strings, "plan.hours", hours=p["hours"]))
                _link(p["url"])

    st.button(t(strings, "plan.back_to_chat"), key="plan_back_chat_btn",
              on_click=wizard.open_chat, args=(state,))
    st.button(t(strings, "chat.edit_answers"), key="plan_edit_btn",
              on_click=wizard.back, args=(state, questions))
    st.button(t(strings, "buttons.clear_answers"), key="plan_clear_btn",
              on_click=wizard.clear_answers, args=(state, questions))
