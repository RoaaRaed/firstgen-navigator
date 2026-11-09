"""Tests core/agent.py's own wiring: which tool arguments reach our ctx-bound functions, how a
tool-calling trace becomes tool_calls, and how a bad structured response is turned into a
safe fallback instead of crashing. LangChain itself is faked (see tests/fake_langchain.py) -
these tests need no network, model, or API key. They prove OUR code is correct; they do not
prove LangChain's or Groq's own behavior - that is confirmed on a machine with real network
access and a real key, exactly like core/ingest.py and core/retriever.py were before this.
"""
import datetime as dt

from tests.fake_langchain import install

install()  # langchain_core/langchain_groq/langchain.agents must exist before core.agent imports them
import core.agent as agent  # noqa: E402  (import after the fake install, on purpose)

from core.retriever import Hit  # noqa: E402
from core.schema import AdvisorAnswer, Citation  # noqa: E402
from core.tools import load_context  # noqa: E402
from tests.fake_langchain import FakeMsg  # noqa: E402


class FakeRetriever:
    def search(self, query, k=5, layer=None, **kw):
        meta = {"doc_id": "state-isac-map", "title": "MAP", "section": "Eligibility",
                "layer": "state", "source_url": "https://www.isac.org/map",
                "retrieved_date": "2026-10-29", "effective_term": ""}
        return [Hit("state-isac-map::03", "state-isac-map", 0.86, "word " * 50, meta)]


def ctx():
    return load_context("demo-ccc", retriever=FakeRetriever(), today=dt.date(2026, 11, 9))


def test_build_langchain_tools_exposes_exactly_the_four_tools_bound_to_ctx():
    tools = agent.build_langchain_tools(ctx())
"""Tests core/agent.py's own wiring: which tool arguments reach our ctx-bound functions, how a
tool-calling trace becomes tool_calls, and how a bad structured response is turned into a
safe fallback instead of crashing. LangChain itself is faked (see tests/fake_langchain.py) -
these tests need no network, model, or API key. They prove OUR code is correct; they do not
prove LangChain's or Groq's own behavior - that is confirmed on a machine with real network
access and a real key, exactly like core/ingest.py and core/retriever.py were before this.
"""
import datetime as dt

from tests.fake_langchain import install

install()  # langchain_core/langchain_groq/langchain.agents must exist before core.agent imports them
import core.agent as agent  # noqa: E402  (import after the fake install, on purpose)

from core.retriever import Hit  # noqa: E402
from core.schema import AdvisorAnswer, Citation  # noqa: E402
from core.tools import load_context  # noqa: E402
from tests.fake_langchain import FakeMsg  # noqa: E402


class FakeRetriever:
    def search(self, query, k=5, layer=None, **kw):
        meta = {"doc_id": "state-isac-map", "title": "MAP", "section": "Eligibility",
                "layer": "state", "source_url": "https://www.isac.org/map",
                "retrieved_date": "2026-10-29", "effective_term": ""}
        return [Hit("state-isac-map::03", "state-isac-map", 0.86, "word " * 50, meta)]


def ctx():
    return load_context("demo-ccc", retriever=FakeRetriever(), today=dt.date(2026, 11, 9))


def test_build_langchain_tools_exposes_exactly_the_four_tools_bound_to_ctx():
    tools = agent.build_langchain_tools(ctx())
    names = {t.name for t in tools}
    assert names == {"search_knowledge_base", "lookup_deadlines",
                     "match_programs", "escalate_to_human"}
    for t in tools:
        assert t.description and "Args:" in t.description


def test_each_wrapped_tool_calls_the_right_underlying_function_with_ctx_bound():
    search_t, deadlines_t, programs_t, escalate_t = agent.build_langchain_tools(ctx())

    out = search_t(query="MAP grant")
    assert out["found"] and out["results"][0]["source_id"] == "state-isac-map::03"

    out = deadlines_t(term="Spring 2027", topic="drop")
    assert out["results"][0]["source_id"] == "deadlines:ccc-spring27-withdrawal-16wk"

    out = programs_t(tags=["caregiver"])
    assert out["found"]

    out = escalate_t(topic="DACA")
    assert out["topic"] == "immigration" and out["sensitive"] is True


def test_build_agent_passes_tools_system_prompt_and_model_through():
    record = install()
    fake_llm = object()
    a = agent.build_agent(ctx(), language="en", llm=fake_llm)
    assert record["build_agent_kwargs"]["model"] is fake_llm
    assert len(record["build_agent_kwargs"]["tools"]) == 4
    assert "search_knowledge_base" in record["build_agent_kwargs"]["system_prompt"]
    assert a.llm is fake_llm


def test_run_agent_pairs_tool_calls_with_their_results_in_order():
    trace = [
        FakeMsg("human", "When can I drop a class in spring?"),
        FakeMsg("ai", "", tool_calls=[{"id": "1", "name": "lookup_deadlines",
                                      "args": {"term": "Spring 2027", "topic": "drop"}}]),
        FakeMsg("tool", '{"found": true}', tool_call_id="1", name="lookup_deadlines"),
        FakeMsg("ai", "You can drop until April 8, 2027."),
    ]
    good = AdvisorAnswer(answer="You can drop until April 8, 2027.",
                         citations=[Citation(source_id="deadlines:ccc-spring27-withdrawal-16wk",
                                             label="Spring 2027 withdrawal deadline")],
                         confidence="High", next_steps=[])
    record = install(agent_trace=trace, structured_answer=good)
    a = agent.build_agent(ctx(), llm=record["llm"])
    result = agent.run_agent(a, "When can I drop a class in spring?")

    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["name"] == "lookup_deadlines"
    assert result.tool_calls[0]["args"] == {"term": "Spring 2027", "topic": "drop"}
    assert result.tool_calls[0]["result"] == '{"found": true}'
    assert result.raw_text == "You can drop until April 8, 2027."
    assert result.answer is good
    assert record["invoke_input"] == {"messages": [{"role": "user", "content": "When can I drop a class in spring?"}]}


def test_run_agent_falls_back_safely_when_structured_output_is_invalid():
    trace = [FakeMsg("ai", "I think it's sometime in spring.")]
    record = install(agent_trace=trace, structured_error=ValueError("model returned bad json"))
    a = agent.build_agent(ctx(), llm=record["llm"])
    result = agent.run_agent(a, "When can I drop a class?")

    assert result.answer.confidence == "Low"
    assert result.answer.citations == []
    assert "model returned bad json" in result.answer.answer or "ValueError" in result.answer.answer


def test_run_agent_accepts_a_plain_dict_from_with_structured_output():
    """Some LangChain versions return a dict instead of the Pydantic instance; either must work."""
    trace = [FakeMsg("ai", "The MAP deadline is February 1, 2027.")]
    as_dict = {"answer": "The MAP priority date is February 1, 2027.",
              "citations": [{"source_id": "deadlines:state-map-priority-2027-28", "label": "MAP priority date"}],
              "confidence": "High", "next_steps": []}
    record = install(agent_trace=trace, structured_answer=as_dict)
    a = agent.build_agent(ctx(), llm=record["llm"])
    result = agent.run_agent(a, "When is the MAP priority date?")

    assert isinstance(result.answer, AdvisorAnswer)
    assert result.answer.citations[0].source_id == "deadlines:state-map-priority-2027-28"

    for t in tools:
        assert t.description and "Args:" in t.description


def test_each_wrapped_tool_calls_the_right_underlying_function_with_ctx_bound():
    search_t, deadlines_t, programs_t, escalate_t = agent.build_langchain_tools(ctx())

    out = search_t(query="MAP grant")
    assert out["found"] and out["results"][0]["source_id"] == "state-isac-map::03"

    out = deadlines_t(term="Spring 2027", topic="drop")
    assert out["results"][0]["source_id"] == "deadlines:ccc-spring27-withdrawal-16wk"

    out = programs_t(tags=["caregiver"])
    assert out["found"]

    out = escalate_t(topic="DACA")
    assert out["topic"] == "immigration" and out["sensitive"] is True


def test_build_agent_passes_tools_system_prompt_and_model_through():
    record = install()
    fake_llm = object()
    a = agent.build_agent(ctx(), language="en", llm=fake_llm)
    assert record["build_agent_kwargs"]["model"] is fake_llm
    assert len(record["build_agent_kwargs"]["tools"]) == 4
    assert "search_knowledge_base" in record["build_agent_kwargs"]["system_prompt"]
    assert a.llm is fake_llm


def test_run_agent_pairs_tool_calls_with_their_results_in_order():
    trace = [
        FakeMsg("human", "When can I drop a class in spring?"),
        FakeMsg("ai", "", tool_calls=[{"id": "1", "name": "lookup_deadlines",
                                      "args": {"term": "Spring 2027", "topic": "drop"}}]),
        FakeMsg("tool", '{"found": true}', tool_call_id="1", name="lookup_deadlines"),
        FakeMsg("ai", "You can drop until April 8, 2027."),
    ]
    good = AdvisorAnswer(answer="You can drop until April 8, 2027.",
                         citations=[Citation(source_id="deadlines:ccc-spring27-withdrawal-16wk",
                                             label="Spring 2027 withdrawal deadline")],
                         confidence="High", next_steps=[])
    record = install(agent_trace=trace, structured_answer=good)
    a = agent.build_agent(ctx(), llm=record["llm"])
    result = agent.run_agent(a, "When can I drop a class in spring?")

    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["name"] == "lookup_deadlines"
    assert result.tool_calls[0]["args"] == {"term": "Spring 2027", "topic": "drop"}
    assert result.tool_calls[0]["result"] == '{"found": true}'
    assert result.raw_text == "You can drop until April 8, 2027."
    assert result.answer is good
    assert record["invoke_input"] == {"messages": [{"role": "user", "content": "When can I drop a class in spring?"}]}


def test_run_agent_falls_back_safely_when_structured_output_is_invalid():
    trace = [FakeMsg("ai", "I think it's sometime in spring.")]
    record = install(agent_trace=trace, structured_error=ValueError("model returned bad json"))
    a = agent.build_agent(ctx(), llm=record["llm"])
    result = agent.run_agent(a, "When can I drop a class?")

    assert result.answer.confidence == "Low"
    assert result.answer.citations == []
    assert "model returned bad json" in result.answer.answer or "ValueError" in result.answer.answer


def test_run_agent_accepts_a_plain_dict_from_with_structured_output():
    """Some LangChain versions return a dict instead of the Pydantic instance; either must work."""
    trace = [FakeMsg("ai", "The MAP deadline is February 1, 2027.")]
    as_dict = {"answer": "The MAP priority date is February 1, 2027.",
              "citations": [{"source_id": "deadlines:state-map-priority-2027-28", "label": "MAP priority date"}],
              "confidence": "High", "next_steps": []}
    record = install(agent_trace=trace, structured_answer=as_dict)
    a = agent.build_agent(ctx(), llm=record["llm"])
    result = agent.run_agent(a, "When is the MAP priority date?")

    assert isinstance(result.answer, AdvisorAnswer)
    assert result.answer.citations[0].source_id == "deadlines:state-map-priority-2027-28"


def test_run_agent_falls_back_safely_when_the_tool_calling_call_itself_fails():
    """If the tool-calling phase raises (e.g. the free Groq tier's per-minute token limit),
    run_agent must not crash the whole batch - it should return a safe Low-confidence answer,
    exactly like it already does when the later structured-output call fails."""
    record = install()
    a = agent.build_agent(ctx(), llm=record["llm"])

    def boom(_input):
        raise RuntimeError("Error code: 413 - tokens per minute rate_limit_exceeded")

    a.runnable.invoke = boom
    result = agent.run_agent(a, "What time does the bookstore close on Saturdays?")

    assert result.answer.confidence == "Low"
    assert result.answer.citations == []
    assert result.tool_calls == []
    assert result.raw_text == ""
    assert "rate_limit_exceeded" in result.answer.answer or "RuntimeError" in result.answer.answer
