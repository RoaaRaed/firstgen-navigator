"""Navigation state for the questionnaire (which question, which page). No Streamlit imports.

`state` is st.session_state in the app and a plain dict in the tests: both work the same way.
"""
from __future__ import annotations

from app.student_answers import set_answer
from app.strings import LANGUAGES

PAGES = ("home", "questionnaire", "chat", "plan")


def widget_key(question_id: str, lang: str = "en") -> str:
    """Streamlit widget key. It includes the language on purpose: when the student switches
    language the options get new labels, and a fresh key makes the browser redraw them
    (otherwise a multi-select kept showing the old English labels)."""
    return f"q_{question_id}_{lang}"


def _current_key(state, question_id: str) -> str:
    return widget_key(question_id, state.get("lang", "en"))


def _forget_widgets(state, question_id: str) -> None:
    for lang in LANGUAGES:
        state.pop(widget_key(question_id, lang), None)


def remember(state, question: dict) -> None:
    """Called whenever the student changes a widget, so the pick is stored in `answers`
    straight away and survives a language switch or a trip to another question."""
    state["answers"] = set_answer(state["answers"], question, state.get(_current_key(state, question["id"])))


def init_state(state) -> None:
    for key, default in (("page", "home"), ("q_index", 0)):
        if key not in state:
            state[key] = default
    if "answers" not in state:
        state["answers"] = {}


def start(state) -> None:
    state["page"] = "questionnaire"
    state["q_index"] = 0


def _advance(state, total: int) -> None:
    if state["q_index"] + 1 >= total:
        state["page"] = "chat"
    else:
        state["q_index"] += 1


def save_and_next(state, questions: list[dict]) -> None:
    """Next / Finish: keep what the student picked on this question, then move on."""
    q = questions[state["q_index"]]
    state["answers"] = set_answer(state["answers"], q, state.get(_current_key(state, q["id"])))
    _advance(state, len(questions))


def skip(state, questions: list[dict]) -> None:
    """Skip: forget any answer for this question, then move on."""
    q = questions[state["q_index"]]
    state["answers"] = set_answer(state["answers"], q, None)
    _forget_widgets(state, q["id"])
    _advance(state, len(questions))


def back(state, questions: list[dict]) -> None:
    """Back: keep the current pick (so it is not lost), then go one question earlier."""
    q = questions[state["q_index"]]
    state["answers"] = set_answer(state["answers"], q, state.get(_current_key(state, q["id"])))
    if state["q_index"] > 0:
        state["q_index"] -= 1
    state["page"] = "questionnaire"


def open_plan(state) -> None:
    state["page"] = "plan"


def open_chat(state) -> None:
    state["page"] = "chat"


def clear_answers(state, questions: list[dict]) -> None:
    """'Clear my answers': forget everything (the answers AND the chat, which may repeat them) and go
    back to the first question."""
    state["answers"] = {}
    state["messages"] = []
    state.pop("pending_question", None)
    for q in questions:
        _forget_widgets(state, q["id"])
    state["q_index"] = 0
    state["page"] = "questionnaire"
