"""Week 5: nothing a student types or answers may be saved or written to a log.

The app keeps the questionnaire answers and the chat only in the browser session (memory), and
"Clear my answers" forgets both. These tests guard that: no file/database/logging code in the app,
and nothing from the question or the profile reaches the terminal (a deployed app's terminal is a
server log).
"""
import re
from pathlib import Path

from tests.fake_langchain import install

install()
import core.agent as agent  # noqa: E402
from tests.fake_langchain import FakeMsg  # noqa: E402
from tests.test_agent import _answer, ctx  # noqa: E402

SECRET = "Sara Khalil lives at 5 Main Street"


def test_the_app_code_has_no_logging_database_or_file_writing():
    banned = re.compile(r"import logging|logging\.|sqlite3|json\.dump|\.write_text\(|\.write_bytes\(|open\([^)]*['\"][wax]b?['\"]|to_csv|pickle")
    for path in Path("app").glob("*.py"):
        found = banned.findall(path.read_text(encoding="utf-8"))
        assert not found, f"{path} writes or logs something: {found}"


def test_a_full_turn_prints_nothing_from_the_question_or_the_profile(capsys, monkeypatch):
    monkeypatch.delenv("ADVISOR_DEBUG_QUERIES", raising=False)
    ai = FakeMsg("ai", "", tool_calls=[{"id": "1", "name": "search_knowledge_base", "args": {"query": SECRET}}])
    ai.usage_metadata = {"input_tokens": 100, "output_tokens": 10}
    record = install(agent_trace=[ai, FakeMsg("ai", "an answer about MAP")], structured_answer=_answer())
    a = agent.build_agent(ctx(), llm=record["llm"])
    agent.run_agent(a, SECRET, language="en", profile=f"Profile: {SECRET}")
    out = capsys.readouterr()
    assert "Sara" not in out.out + out.err and "Main Street" not in out.out + out.err
    assert "[tools] search_knowledge_base" in out.out
