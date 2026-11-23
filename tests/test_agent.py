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

    text, out = search_t(query="MAP grant")
    assert out["found"] and out["results"][0]["source_id"] == "state-isac-map::03"

    text, out = deadlines_t(term="Spring 2027", topic="drop")
    assert out["results"][0]["source_id"] == "deadlines:ccc-spring27-withdrawal-16wk"

    text, out = programs_t(tags=["caregiver"])
    assert out["found"]

    text, out = escalate_t(topic="DACA")
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

    text, out = search_t(query="MAP grant")
    assert out["found"] and out["results"][0]["source_id"] == "state-isac-map::03"

    text, out = deadlines_t(term="Spring 2027", topic="drop")
    assert out["results"][0]["source_id"] == "deadlines:ccc-spring27-withdrawal-16wk"

    text, out = programs_t(tags=["caregiver"])
    assert out["found"]

    text, out = escalate_t(topic="DACA")
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


def _answer():
    return AdvisorAnswer(answer="ok", citations=[], confidence="Low", next_steps=[])


def test_run_agent_without_profile_sends_the_question_unchanged():
    record = install(agent_trace=[FakeMsg("ai", "ok")], structured_answer=_answer())
    a = agent.build_agent(ctx(), llm=record["llm"])
    agent.run_agent(a, "What is MAP?")
    assert record["invoke_input"]["messages"][0]["content"] == "What is MAP?"


def test_run_agent_puts_the_profile_before_the_question_in_one_user_message():
    record = install(agent_trace=[FakeMsg("ai", "ok")], structured_answer=_answer())
    a = agent.build_agent(ctx(), llm=record["llm"])
    agent.run_agent(a, "What is MAP?", profile="[STUDENT PROFILE]\n- stage: Applying\n[END STUDENT PROFILE]")
    msgs = record["invoke_input"]["messages"]
    assert len(msgs) == 1 and msgs[0]["role"] == "user"
    text = msgs[0]["content"]
    assert text.startswith("[STUDENT PROFILE]")
    assert text.endswith("Student's question:\nWhat is MAP?")


# ---- rate limit (the free Groq tier: tokens per minute) ----

class _RateLimit(Exception):
    pass


def test_rate_limit_wait_reads_the_time_groq_asks_for():
    e = _RateLimit("Error code: 429 - Rate limit reached ... Please try again in 8.5s. Need more")
    assert agent._rate_limit_wait(e) == 9.5
    assert agent._rate_limit_wait(_RateLimit("429 ... try again in 1m3.5s.")) == 64.5
    assert agent._rate_limit_wait(_RateLimit("429 ... try again in 340ms")) == 6.0     # at least 5s
    assert agent._rate_limit_wait(_RateLimit("429 without a time")) == 6.0
    assert agent._rate_limit_wait(ValueError("bad schema")) is None


def test_call_retries_after_a_rate_limit_then_succeeds():
    calls, slept = [], []

    def fn():
        calls.append(1)
        if len(calls) < 3:
            raise _RateLimit("429 Rate limit reached. Please try again in 10s.")
        return "ok"

    assert agent._call_with_rate_limit_retry(fn, sleep=slept.append) == "ok"
    assert len(calls) == 3 and slept == [11.0, 11.0]


def test_call_gives_up_after_the_retries_and_does_not_retry_other_errors():
    import pytest

    n = []

    def always():
        n.append(1)
        raise _RateLimit("429 Rate limit")

    with pytest.raises(_RateLimit):
        agent._call_with_rate_limit_retry(always, sleep=lambda s: None)
    assert len(n) == agent.RATE_LIMIT_RETRIES + 1

    other = []

    def bad():
        other.append(1)
        raise ValueError("boom")

    with pytest.raises(ValueError):
        agent._call_with_rate_limit_retry(bad, sleep=lambda s: None)
    assert len(other) == 1


def test_run_agent_waits_and_retries_the_tool_loop_on_a_rate_limit(monkeypatch):
    record = install(agent_trace=[FakeMsg("ai", "ok")], structured_answer=_answer())
    a = agent.build_agent(ctx(), llm=record["llm"])
    real, tries = a.runnable.invoke, []

    def flaky(payload):
        tries.append(1)
        if len(tries) == 1:
            raise _RateLimit("429 Please try again in 7s")
        return real(payload)

    a.runnable.invoke = flaky
    slept = []
    monkeypatch.setattr(agent.time, "sleep", slept.append)
    result = agent.run_agent(a, "What is MAP?")
    assert len(tries) == 2 and slept == [8.0]
    assert result.answer.answer == "ok"


def test_a_long_wait_such_as_the_daily_limit_is_not_slept_through():
    daily = _RateLimit("Error code: 429 - Rate limit reached ... on tokens per day (TPD): Limit 200000, "
                       "Used 199159. Please try again in 19m38.928s.")
    assert agent._rate_limit_wait(daily) is None
    assert agent.is_daily_limit_error(str(daily)) is True
    assert agent.is_daily_limit_error("429 tokens per minute (TPM)") is False
    slept = []
    import pytest

    with pytest.raises(_RateLimit):
        agent._call_with_rate_limit_retry(lambda: (_ for _ in ()).throw(daily), sleep=slept.append)
    assert slept == []


# ---- the model reads compact text, the page keeps the full result ----

def test_tools_return_compact_text_for_the_model_and_the_full_dict_as_artifact():
    search_t, deadlines_t, programs_t, escalate_t = agent.build_langchain_tools(ctx())
    assert all(t.response_format == "content_and_artifact" for t in (search_t, deadlines_t, programs_t, escalate_t))

    text, full = search_t(query="MAP grant")
    assert text.startswith("[state-isac-map::03]") and "http" not in text
    assert full["results"][0]["source_url"] == "https://www.isac.org/map"   # the cards still get the link

    text, full = deadlines_t(term="Spring 2027", topic="drop")
    assert text.startswith("today: 2026-11-09") and "deadlines:" in text and "http" not in text
    assert full["results"][0]["source_url"].startswith("http")

    text, full = programs_t(tags=["caregiver"])
    assert "[programs:" in text and "http" not in text and full["results"][0]["source_url"]

    text, full = escalate_t(topic="DACA")
    assert text.startswith("topic: ") and "[programs:" in text


def test_extract_tool_calls_prefers_the_artifact_over_the_compact_text():
    from tests.fake_langchain import FakeMsg

    full = {"found": True, "results": [{"source_id": "x::01", "source_url": "https://x.org"}]}
    msgs = [FakeMsg("ai", "", tool_calls=[{"id": "1", "name": "search_knowledge_base", "args": {"query": "q"}},
                                          {"id": "2", "name": "lookup_deadlines", "args": {}}]),
            FakeMsg("tool", "[x::01] compact text", tool_call_id="1", artifact=full),
            FakeMsg("tool", "plain content only", tool_call_id="2")]
    calls = agent._extract_tool_calls(msgs)
    assert calls[0]["result"] == full                       # the full dict, for the source cards
    assert calls[1]["result"] == "plain content only"       # no artifact: the content, as before


def test_the_tool_loop_reserves_less_room_than_the_final_answer(monkeypatch):
    from types import SimpleNamespace

    record = install(agent_trace=[FakeMsg("ai", "ok")], structured_answer=_answer())
    made = []
    monkeypatch.setattr(agent, "get_llm", lambda model=None, temperature=0.0, max_tokens=2000:
                        made.append(max_tokens) or SimpleNamespace(max_tokens=max_tokens))
    a = agent.build_agent(ctx())
    assert record["build_agent_kwargs"]["model"].max_tokens == agent.LOOP_MAX_TOKENS == 1200
    assert a.llm.max_tokens == 2000                       # the structured answer keeps its room


# ---- 413 "request too large": retry smaller instead of failing ----

def test_is_too_large_error_matches_groqs_413_only():
    assert agent.is_too_large_error(RuntimeError("Error code: 413 - Request too large for model x"))
    assert not agent.is_too_large_error(RuntimeError("Error code: 429 - tokens per day (TPD)"))


def test_a_413_in_the_tool_loop_is_retried_once_in_lean_mode(monkeypatch):
    record = install(agent_trace=[FakeMsg("ai", "ok")], structured_answer=_answer())
    a = agent.build_agent(ctx(), llm=record["llm"])
    real, modes = a.runnable.invoke, []

    def too_big_first(payload):
        modes.append(a.lean["on"])
        if len(modes) == 1:
            raise RuntimeError("Error code: 413 - Request too large ... Limit 8000, Requested 8071")
        return real(payload)

    a.runnable.invoke = too_big_first
    monkeypatch.setattr(agent.time, "sleep", lambda s: None)
    result = agent.run_agent(a, "How do I apply?")
    assert modes == [False, True]            # first normal, then lean
    assert a.lean["on"] is False              # switched off again afterwards
    assert result.answer.answer == "ok"


def test_lean_mode_shows_the_model_fewer_search_results_but_the_page_keeps_the_full_ones():
    seen = []

    class Many(FakeRetriever):
        def search(self, query, k=5, layer=None, **kw):
            seen.append(k)
            return super().search(query, k=k, layer=layer) * k

    lean = {"on": False}
    c = load_context("demo-ccc", retriever=Many(), today=dt.date(2026, 11, 9))
    search_t, deadlines_t, programs_t, _ = agent.build_langchain_tools(c, lean)
    search_t(query="MAP")
    lean["on"] = True
    search_t(query="MAP")
    assert seen == [8, agent.LEAN_SEARCH_K]
    cats = ["financial", "academic", "wellness", "transfer", "childcare", "food", "disability"]
    text_lean, full_lean = programs_t(categories=cats)
    lean["on"] = False
    text_normal, full_normal = programs_t(categories=cats)
    assert len(text_lean.splitlines()) <= agent.LEAN_ROWS < len(text_normal.splitlines())
    assert len(full_lean["results"]) == len(full_normal["results"])   # the cards keep every row


def test_a_413_in_the_final_call_is_retried_without_the_draft_text():
    calls = []
    trace = [FakeMsg("ai", "", tool_calls=[{"id": "1", "name": "lookup_deadlines", "args": {}}]),
             FakeMsg("tool", "[d::1] 2026-12-01", tool_call_id="1"),
             FakeMsg("ai", "a long draft answer")]
    record = install(agent_trace=trace, structured_answer=_answer())
    a = agent.build_agent(ctx(), llm=record["llm"])

    class Llm:
        def with_structured_output(self, schema):
            return self

        def invoke(self, msgs):
            calls.append(msgs)
            if len(calls) == 1:
                raise RuntimeError("Error code: 413 - Request too large")
            return _answer()

    a.llm = Llm()
    result = agent.run_agent(a, "When is it?")
    assert len(calls) == 2
    assert any(getattr(m, "content", "") == "a long draft answer" for m in calls[0])
    assert not any(getattr(m, "content", "") == "a long draft answer" for m in calls[1])
    assert result.answer.confidence != "Low" or result.answer.answer == "ok"


def test_token_usage_is_printed_for_each_model_call(capsys):
    msgs = [FakeMsg("ai", ""), FakeMsg("ai", "x")]
    msgs[0].usage_metadata = {"input_tokens": 5000, "output_tokens": 40}
    msgs[1].usage_metadata = {"input_tokens": 6200, "output_tokens": 300}
    agent._print_usage(msgs)
    out = capsys.readouterr().out
    assert "model call 1: input 5000, output 40" in out and "model call 2: input 6200, output 300" in out


# ---- the model calls a tool that does not exist (Groq 400 tool_use_failed) ----

BAD_TOOL = ("Error code: 400 - {'error': {'message': \"Tool call validation failed: attempted to call tool "
            "'open_file' which was not in request.tools\", 'code': 'tool_use_failed'}}")


def test_is_tool_use_error_matches_the_made_up_tool_error_only():
    assert agent.is_tool_use_error(RuntimeError(BAD_TOOL))
    assert not agent.is_tool_use_error(RuntimeError("Error code: 413 - Request too large"))


def test_a_made_up_tool_is_retried_with_a_reminder_of_the_real_tools():
    record = install(agent_trace=[FakeMsg("ai", "ok")], structured_answer=_answer())
    a = agent.build_agent(ctx(), llm=record["llm"])
    real, sent = a.runnable.invoke, []

    def flaky(payload):
        sent.append(payload["messages"][-1]["content"])
        if len(sent) == 1:
            raise RuntimeError(BAD_TOOL)
        return real(payload)

    a.runnable.invoke = flaky
    result = agent.run_agent(a, "How do I apply?")
    assert len(sent) == 2
    assert "search_knowledge_base" not in sent[0] and "search_knowledge_base" in sent[1]
    assert result.answer.answer == "ok"


def test_a_made_up_tool_that_keeps_happening_ends_in_the_safe_fallback():
    record = install(agent_trace=[FakeMsg("ai", "ok")], structured_answer=_answer())
    a = agent.build_agent(ctx(), llm=record["llm"])
    tries = []

    def always(payload):
        tries.append(1)
        raise RuntimeError(BAD_TOOL)

    a.runnable.invoke = always
    result = agent.run_agent(a, "How do I apply?")
    assert len(tries) == 1 + agent.TOOL_USE_RETRIES
    assert result.answer.confidence == "Low"


def test_a_made_up_tool_in_the_final_call_is_retried():
    record = install(agent_trace=[FakeMsg("ai", "draft")], structured_answer=_answer())
    a = agent.build_agent(ctx(), llm=record["llm"])
    calls = []

    class Llm:
        def with_structured_output(self, schema):
            return self

        def invoke(self, msgs):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError(BAD_TOOL)
            return _answer()

    a.llm = Llm()
    result = agent.run_agent(a, "How do I apply?")
    assert len(calls) == 2 and result.answer.answer == "ok"


# ---- a question gets a limited number of tool calls (each extra one re-sends the whole conversation) ----

def test_a_third_search_and_a_fifth_call_get_the_stop_message_not_a_result():
    budget = {"used": 0, "searches": 0}
    search_t, deadlines_t, programs_t, escalate_t = agent.build_langchain_tools(ctx(), {"on": False}, budget)
    assert search_t(query="MAP")[1].get("skipped") is None
    assert search_t(query="MAP again")[1].get("skipped") is None
    text, out = search_t(query="a third time")
    assert text == agent.TOOL_LIMIT_TEXT and out == {"results": [], "skipped": "tool limit reached"}
    deadlines_t(term="Spring 2027")                 # 3rd real call
    programs_t(categories=["food"])                 # 4th real call
    assert budget["used"] == agent.MAX_TOOL_CALLS == 4
    text, out = deadlines_t(term="Spring 2027")
    assert text == agent.TOOL_LIMIT_TEXT and out["skipped"] == "tool limit reached"


def test_escalate_to_human_is_never_blocked_by_the_tool_limit():
    budget = {"used": agent.MAX_TOOL_CALLS, "searches": agent.MAX_SEARCHES}
    *_, escalate_t = agent.build_langchain_tools(ctx(), {"on": False}, budget)
    text, out = escalate_t(topic="immigration")
    assert text != agent.TOOL_LIMIT_TEXT and "skipped" not in out


def test_every_run_of_the_loop_starts_with_a_full_budget():
    from types import SimpleNamespace

    seen = []
    a = SimpleNamespace(budget={"used": 4, "searches": 2},
                        runnable=SimpleNamespace(invoke=lambda p: seen.append(dict(a.budget)) or {"messages": []}))
    agent._once(a, {"messages": []})
    assert seen == [{"used": 0, "searches": 0}]


def test_tool_calls_are_listed_on_one_line_without_the_students_words(capsys, monkeypatch):
    monkeypatch.delenv("ADVISOR_DEBUG_QUERIES", raising=False)
    ai = FakeMsg("ai", "", tool_calls=[{"id": "1", "name": "search_knowledge_base", "args": {"query": "my name is Sara and I live at 5 Main St"}},
                                        {"id": "2", "name": "lookup_deadlines", "args": {"term": "Spring 2027"}}])
    agent._print_tools([ai, FakeMsg("ai", "done")])
    out = capsys.readouterr().out
    assert out.strip() == "[tools] search_knowledge_base, lookup_deadlines"
    assert "Sara" not in out and "Spring" not in out


def test_debug_switch_shows_the_first_words_of_the_arguments(capsys, monkeypatch):
    monkeypatch.setenv("ADVISOR_DEBUG_QUERIES", "1")
    ai = FakeMsg("ai", "", tool_calls=[{"id": "1", "name": "search_knowledge_base", "args": {"query": "how do I apply"}}])
    agent._print_tools([ai])
    assert capsys.readouterr().out.strip() == "[tools] search_knowledge_base('how do I apply')"
