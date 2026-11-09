"""A tiny stand-in for langchain/langchain_core/langchain_groq, just enough surface for
core.agent to import and run. Real LangChain cannot be installed in this sandbox (no network),
so this is what tests/test_agent.py uses to check OUR wiring logic (which tool is called with
which arguments, how tool results and the final structured answer are assembled) without a
real model or API key. It proves core/agent.py's own code is correct; it does not prove
LangChain's or Groq's behavior - that is confirmed on a machine with real network access,
exactly like core/ingest.py and core/retriever.py were.
"""
import sys
import types


class FakeMsg:
    def __init__(self, type, content="", tool_calls=None, tool_call_id=None, name=None):
        self.type = type
        self.content = content
        self.tool_calls = tool_calls
        self.tool_call_id = tool_call_id
        self.name = name


class FakeLLM:
    """A standalone fake chat model, independent of the sys.modules patching below, so each
    install() call can hand tests a model whose with_structured_output(...) returns exactly
    what that call asked for (the real ChatGroq class is only bound once, at core.agent's
    first import, so re-patching sys.modules later would not change what it returns)."""

    def __init__(self, structured_answer=None, structured_error=None, record=None):
        self._answer = structured_answer
        self._error = structured_error
        self._record = record

    def with_structured_output(self, schema):
        return self._Caller(self)

    class _Caller:
        def __init__(self, outer):
            self.outer = outer

        def invoke(self, messages):
            if self.outer._record is not None:
                self.outer._record["finalize_messages"] = messages
            if self.outer._error is not None:
                raise self.outer._error
            return self.outer._answer


def install(agent_trace=None, structured_answer=None, structured_error=None, record=None):
    """Install fake langchain.agents / langchain_core.tools / langchain_groq into sys.modules,
    and build a FakeLLM with the given structured-output behavior.

    agent_trace: the list[FakeMsg] that the fake agent's .invoke() returns as {"messages": ...}.
    structured_answer / structured_error: what the returned FakeLLM's
        with_structured_output(...).invoke() returns, or raises.
    record: an optional dict that build_langchain_tools()'s calls write debug info into.

    Returns the record dict, with record["llm"] set to a ready-to-use FakeLLM - pass that as
    build_agent(..., llm=record["llm"]) so the structured-output call in run_agent is this
    install() call's FakeLLM, not a stale one bound at import time.
    """
    record = record if record is not None else {}
    record["llm"] = FakeLLM(structured_answer, structured_error, record)

    lc_core_tools = types.ModuleType("langchain_core.tools")

    class FakeTool:
        def __init__(self, func):
            self.func = func
            self.name = func.__name__
            self.description = func.__doc__

        def __call__(self, *a, **kw):
            return self.func(*a, **kw)

    lc_core_tools.tool = FakeTool
    lc_core = types.ModuleType("langchain_core")
    lc_core.tools = lc_core_tools

    lc_groq = types.ModuleType("langchain_groq")

    class FakeChatGroq:
        def __init__(self, **kw):
            self.kw = kw

        def with_structured_output(self, schema):
            return _StructuredCaller(schema)

    class _StructuredCaller:
        def __init__(self, schema):
            self.schema = schema

        def invoke(self, messages):
            record["finalize_messages"] = messages
            if structured_error is not None:
                raise structured_error
            return structured_answer

    lc_groq.ChatGroq = FakeChatGroq

    lc_agents = types.ModuleType("langchain.agents")

    class FakeRunnable:
        def __init__(self, model, tools, system_prompt):
            record["build_agent_kwargs"] = {"model": model, "tools": tools,
                                            "system_prompt": system_prompt}

        def invoke(self, input):
            record["invoke_input"] = input
            return {"messages": agent_trace or []}

    def fake_create_agent(model, tools, system_prompt):
        return FakeRunnable(model, tools, system_prompt)

    lc_agents.create_agent = fake_create_agent
    lc = types.ModuleType("langchain")
    lc.agents = lc_agents

    sys.modules.update({
        "langchain_core": lc_core, "langchain_core.tools": lc_core_tools,
        "langchain_groq": lc_groq,
        "langchain": lc, "langchain.agents": lc_agents,
    })
    return record
