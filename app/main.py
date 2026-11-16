"""FirstGen Navigator - Streamlit entry point.  Run:  streamlit run app/main.py"""
import sys
from pathlib import Path

# `streamlit run app/main.py` puts the app/ folder on the import path, not the project root,
# so `import core...` and `import app...` would fail (same cause as the earlier
# "No module named core"). Put the project root on the path first.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from app import chat_page, questionnaire, wizard  # noqa: E402
from app.strings import LANGUAGES, load_strings, normalize, page_css, t  # noqa: E402

st.set_page_config(page_title="FirstGen Navigator", page_icon="🧭", layout="centered")

wizard.init_state(st.session_state)
chat_page.warm_up()  # load the search model in the background while the student answers questions

# Language toggle. key="lang" stores the choice in session state, so it survives reruns.
st.session_state.setdefault("lang", "en")
lang = normalize(
    st.radio(
        "Language / اللغة",
        options=list(LANGUAGES),
        format_func=LANGUAGES.get,
        horizontal=True,
        key="lang",
    )
)
strings = load_strings(lang)

css = page_css(lang)
if css:
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

st.title(t(strings, "app.title"))
page = st.session_state["page"]

if page == "home":
    st.write(t(strings, "app.subtitle"))
    st.info(t(strings, "disclosure"))
    st.button(t(strings, "buttons.start"), type="primary", on_click=wizard.start, args=(st.session_state,))
elif page == "questionnaire":
    questionnaire.render(strings, lang)
else:  # "chat": the questionnaire is finished
    chat_page.render_page(strings, lang)
