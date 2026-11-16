"""The questionnaire page: one question at a time with Back / Skip / Next. Streamlit UI only;
the logic lives in app/wizard.py and app/profile.py (those are the tested parts)."""
import streamlit as st

from app import wizard
from app.profile import NOTES_MAX_CHARS
from app.strings import t


def _clear_button(strings: dict) -> None:
    questions = strings["questionnaire"]["questions"]
    st.button(
        t(strings, "buttons.clear_answers"),
        key="clear_answers_btn",
        on_click=wizard.clear_answers,
        args=(st.session_state, questions),
    )


def render(strings: dict, ui_lang: str) -> None:
    state = st.session_state
    questions = strings["questionnaire"]["questions"]
    total = len(questions)
    i = min(state["q_index"], total - 1)
    q = questions[i]
    answers = state["answers"]
    key = wizard.widget_key(q["id"], ui_lang)
    remember = dict(on_change=wizard.remember, args=(state, q))

    st.subheader(t(strings, "questionnaire.title"))
    st.caption(t(strings, "questionnaire.intro"))
    st.progress(i / total)
    st.caption(t(strings, "questionnaire.progress", n=i + 1, total=total))

    st.markdown(f"**{q['text']}**")
    st.caption(t(strings, "questionnaire.optional"))

    current = answers.get(q["id"])
    if q["type"] == "single":
        ids = [o["id"] for o in q["options"]]
        labels = {o["id"]: o["label"] for o in q["options"]}
        if current is None and q["id"] == "language":
            current = ui_lang  # pre-select the language the student is already using
        st.radio(
            q["text"],
            options=ids,
            index=ids.index(current) if current in ids else None,
            format_func=labels.get,
            key=key,
            label_visibility="collapsed",
            **remember,
        )
    elif q["type"] == "multi":
        ids = [o["id"] for o in q["options"]]
        labels = {o["id"]: o["label"] for o in q["options"]}
        st.caption(t(strings, "questionnaire.choose_up_to", max=q["max_choices"]))
        st.multiselect(
            q["text"],
            options=ids,
            default=current or [],
            format_func=labels.get,
            max_selections=q["max_choices"],
            key=key,
            label_visibility="collapsed",
            **remember,
        )
    else:  # free_text
        st.text_area(
            q["text"],
            value=current or "",
            max_chars=NOTES_MAX_CHARS,
            placeholder=t(strings, "questionnaire.notes_hint"),
            key=key,
            label_visibility="collapsed",
            **remember,
        )

    c_back, c_skip, c_next = st.columns(3)
    c_back.button(
        t(strings, "buttons.back"), key="back_btn", disabled=(i == 0),
        on_click=wizard.back, args=(state, questions), use_container_width=True,
    )
    c_skip.button(
        t(strings, "buttons.skip"), key="skip_btn",
        on_click=wizard.skip, args=(state, questions), use_container_width=True,
    )
    last = i == total - 1
    c_next.button(
        t(strings, "buttons.finish" if last else "buttons.next"), key="next_btn", type="primary",
        on_click=wizard.save_and_next, args=(state, questions), use_container_width=True,
    )
    _clear_button(strings)

