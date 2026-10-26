import os

import streamlit as st
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_groq import ChatGroq

load_dotenv()


@tool
def lookup_deadline(topic: str) -> str:
    """Look up a college deadline by topic, for example 'fafsa' or 'map'.
    Use this tool whenever the student asks about a date or a deadline."""
    fake_deadlines = {
        "fafsa": "TEST DATA ONLY: FAFSA deadline is 2099-03-01.",
        "map": "TEST DATA ONLY: MAP grant deadline is 2099-04-15.",
    }
    return fake_deadlines.get(topic.lower(), "No deadline found for that topic.")


@st.cache_resource
def get_agent():
    llm = ChatGroq(
        model=os.getenv("GROQ_MODEL"),
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0,
        max_tokens=2000,
    )
    return create_agent(
        model=llm,
        tools=[lookup_deadline],
        system_prompt=(
            "You are a college advising assistant. "
            "For any date or deadline, ONLY use the lookup_deadline tool. "
            "If the tool finds nothing, say you could not find it. Never guess a date."
        ),
    )


agent = get_agent()

st.title("FirstGen Navigator (test)")

if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

question = st.chat_input("Ask about a deadline...")
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            result = agent.invoke({"messages": st.session_state.messages})
        answer = result["messages"][-1].content
        st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})