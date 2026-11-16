"""The chat page: history, answer with confidence pill, source cards, next steps and contact.
Streamlit UI only; the logic is in app/render.py and app/advisor.py (the tested parts)."""
import streamlit as st

from app import advisor, render, wizard
from app.profile import describe_answers
from app.strings import t


@st.cache_resource(show_spinner=False)
def _context():
    return advisor.get_context()


@st.cache_resource(show_spinner=False)
def _agent(language: str):
    return advisor.get_agent(_context(), language)


def warm_up() -> None:
    """Called on every page: starts loading the search model in the background (once)."""
    advisor.warm_up(_context())


def _pick_example(text: str) -> None:
    st.session_state["pending_question"] = text


def _new_conversation() -> None:
    st.session_state["messages"] = []


def _auto(text: str, **kw) -> None:
    st.markdown(render.auto_dir_html(text, **kw), unsafe_allow_html=True)


def _show_assistant(strings: dict, msg: dict) -> None:
    if msg["fallback"]:
        st.warning(t(strings, "chat.busy"))
        return

    level = msg["confidence"]
    st.markdown(render.confidence_pill_html(t(strings, f"chat.confidence.{level}.label"), level),
                unsafe_allow_html=True)
    st.caption(t(strings, f"chat.confidence.{level}.hint"))
    st.write(msg["answer"])

    st.markdown(f"**{t(strings, 'chat.sources')}**")
    if not msg["cards"]:
        st.caption(t(strings, "chat.no_sources"))
    for card in msg["cards"]:
        with st.container(border=True):
            st.caption(t(strings, "chat.kinds." + card["kind"]))
            _auto(card["title"], bold=True)
            if card["detail"]:
                _auto(card["detail"], muted=True)
            if card["snippet"]:
                _auto(card["snippet"])
            if card["hours"]:
                st.caption(t(strings, "chat.hours", hours=card["hours"]))
            bits = []
            if card["url"]:
                bits.append(f"[{t(strings, 'chat.open_source')}]({card['url']})")
            if card["retrieved_date"]:
                bits.append(t(strings, "chat.retrieved", date=render.isolate_ltr(card["retrieved_date"])))
            if bits:
                st.markdown(" · ".join(bits))
            st.caption(f"`{card['source_id']}`")

    if msg["next_steps"]:
        st.markdown(f"**{t(strings, 'chat.next_steps')}**")
        st.markdown("\n".join(f"- {s}" for s in msg["next_steps"]))

    contact = msg["contact"]
    if contact:
        lines = [f"**{t(strings, 'chat.contact')}:** {contact['office']}"]
        if render.safe_url(contact.get("url")):
            lines.append(contact["url"])
        if contact.get("phone"):
            lines.append(contact["phone"])
        st.info("  \n".join(lines))


def _show_message(strings: dict, msg: dict) -> None:
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.write(msg["content"])
    else:
        with st.chat_message("assistant"):
            _show_assistant(strings, msg)


def render_page(strings: dict, lang: str) -> None:
    state = st.session_state
    state.setdefault("messages", [])
    questions = strings["questionnaire"]["questions"]

    st.subheader(t(strings, "chat.title"))
    st.button(t(strings, "plan.open"), key="open_plan_btn", on_click=wizard.open_plan, args=(state,))

    with st.expander(t(strings, "chat.your_answers")):
        for question_text, shown in describe_answers(strings, state["answers"]):
            st.markdown(f"- **{question_text}** {shown}")
        st.button(t(strings, "chat.edit_answers"), key="edit_answers_btn",
                  on_click=wizard.back, args=(state, questions))
        st.button(t(strings, "buttons.clear_answers"), key="chat_clear_btn",
                  on_click=wizard.clear_answers, args=(state, questions))
    if state["messages"]:
        st.button(t(strings, "chat.new_conversation"), key="new_conv_btn", on_click=_new_conversation)

    for msg in state["messages"]:
        _show_message(strings, msg)

    typed = st.chat_input(t(strings, "chat.placeholder"))
    question = typed or state.pop("pending_question", None)

    if not state["messages"] and not question:  # example questions only on an empty, idle chat
        st.caption(t(strings, "chat.examples_title"))
        for i, example in enumerate(strings["chat"]["examples"]):
            st.button(example, key=f"example_{i}", on_click=_pick_example, args=(example,))

    if not question:
        return

    user_msg = {"role": "user", "content": question}
    _show_message(strings, user_msg)
    with st.chat_message("assistant"):
        try:
            with st.spinner(t(strings, "chat.thinking")):
                result, seconds = advisor.answer(_agent(lang), question, lang)
            reply = render.assistant_message(result, seconds)
        except Exception as e:  # e.g. GROQ_API_KEY missing, or the index is not built
            st.error(t(strings, "chat.error", error=f"{type(e).__name__}: {e}"))
            return
        _show_assistant(strings, reply)
    state["messages"] += [user_msg, reply]
