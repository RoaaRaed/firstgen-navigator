import os
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


llm = ChatGroq(
    model=os.getenv("GROQ_MODEL"),
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0,
    max_tokens=2000,
)

agent = create_agent(
    model=llm,
    tools=[lookup_deadline],
    system_prompt=(
        "You are a college advising assistant. "
        "For any date or deadline, ONLY use the lookup_deadline tool. "
        "If the tool finds nothing, say you could not find it. Never guess a date."
    ),
)

questions = [
    "When is the FAFSA deadline?",
    "What is the deadline for the Pell Grant?",
    "ما هو الموعد النهائي لمنحة MAP؟",
    "Hi, how are you?",
]

for q in questions:
    print("\nQ:", q)
    result = agent.invoke({"messages": [{"role": "user", "content": q}]})
    for msg in result["messages"]:
        if msg.type == "ai" and msg.tool_calls:
            for call in msg.tool_calls:
                print("  [tool call]  ", call["name"], call["args"])
        elif msg.type == "tool":
            print("  [tool result]", msg.content)
        elif msg.type == "ai":
            print("  [answer]     ", msg.content)