"""Wire the four tools and the bilingual system prompt into a LangChain tool-calling agent.

    from core.agent import build_agent, run_agent
    from core.tools import load_context
    ctx = load_context("demo-ccc")
    agent = build_agent(ctx, language="en")
    result = run_agent(agent, "What is the MAP grant deadline?")
    print(result.answer.confidence, [c.source_id for c in result.answer.citations])

Needs GROQ_API_KEY in the environment (.env). get_llm() is the one place that knows the LLM
provider, same pattern as core/embeddings.py - swap it later for another backend without
touching anything else (the brief: swappable by environment variable).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from langchain_core.tools import tool
from langchain_groq import ChatGroq

from core.prompts import load_system_prompt
from core.schema import AdvisorAnswer
from core.tools import escalate_to_human as _escalate_to_human
from core.tools import lookup_deadlines as _lookup_deadlines
from core.tools import match_programs as _match_programs
from core.tools import search_knowledge_base as _search_knowledge_base

DEFAULT_INSTITUTION_NAME = "City Colleges of Chicago"

FINALIZE_INSTRUCTIONS = (
    "Turn the conversation above into the required structured answer. Use only source_id "
    "values that appeared in a tool result above - never invent one. If no tool found "
    "anything useful, set confidence to \"Low\", citations to an empty list, and say plainly "
    "in `answer` that you could not find this in the documents, with a next step to ask a "
    "human (use escalate_to_human's result if you already called it)."
)


def get_llm(model: str | None = None, temperature: float = 0.0):
    """The one place that knows which LLM we use (Groq free tier for development)."""
    from dotenv import load_dotenv

    load_dotenv()
    model = model or os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set. Add it to .env (see .env.example).")
    return ChatGroq(model=model, api_key=api_key, temperature=temperature, max_tokens=2000)


def build_langchain_tools(ctx) -> list:
    """Wrap the four tools so the model only sees the arguments it should fill in.
    `ctx` (the loaded institution data) is bound in this closure - the model never sees it
    and cannot change it."""

    # Tool names must exactly match what the system prompt calls them (Groq rejects a tool
    # call whose name is not in the request's tool list, so the wrapper and the prompt text
    # must agree character for character - hence the plain names here, not "..._tool").
    @tool
    def search_knowledge_base(query: str, language: str = "en", layer: str = "") -> dict:
        """Search the official documents (federal, Illinois state, and college pages) for
        passages that answer the student's question. Use for how something works, who is
        eligible, what steps to take, or what a term means.

        Args:
            query: the question in the student's own words.
            language: "en" or "ar" - the language of the student's question.
            layer: optional: "federal", "state" or "institution". Leave empty otherwise.
        """
        return _search_knowledge_base(ctx, query, language=language, layer=layer or None)

    @tool
    def lookup_deadlines(term: str = "", topic: str = "") -> dict:
        """Look up exact dates from the official deadlines table (FAFSA, MAP, Alternative
        Application, registration, withdrawal, term dates). Use for any "when" question.

        Args:
            term: optional term or aid year, e.g. "Spring 2027", "2026-27".
            topic: optional English words, e.g. "withdrawal", "first day", "FAFSA".
        """
        return _lookup_deadlines(ctx, term=term, topic=topic)

    @tool
    def match_programs(tags: list[str] | None = None, categories: list[str] | None = None,
                       keywords: str = "") -> dict:
        """Find support programs and offices for the student's situation (aid, food, child
        care, immigrant services, ESL, transfer, wellness, disability, academic help).

        Args:
            tags: profile tags, any of: first_gen, working_20plus, working_30plus, caregiver,
                fafsa_ineligible_or_unsure, esl, transfer.
            categories: any of: financial, academic, wellness, transfer, immigrant_services,
                childcare, food, disability.
            keywords: optional English words.
        """
        return _match_programs(ctx, tags=tags or [], categories=categories or [], keywords=keywords)

    @tool
    def escalate_to_human(topic: str) -> dict:
        """Get the named office a student should talk to for something the documents cannot
        decide alone: eligibility decisions, immigration, verification, a crisis. Never give
        legal advice and never ask about immigration status.

        Args:
            topic: financial_aid, state_aid, immigration, academic, transfer, wellness, food,
                snap, childcare, disability (other words are matched to the closest topic).
        """
        return _escalate_to_human(ctx, topic)

    return [search_knowledge_base, lookup_deadlines, match_programs, escalate_to_human]


@dataclass
class Agent:
    """Bundles the tool-calling runnable and the chat model (reused for the structured pass)."""
    runnable: object
    llm: object
    tools: list = field(default_factory=list)


def build_agent(ctx, language: str = "en", institution_name: str = DEFAULT_INSTITUTION_NAME,
                llm=None) -> Agent:
    from langchain.agents import create_agent

    llm = llm or get_llm()
    tools = build_langchain_tools(ctx)
    system_prompt = load_system_prompt(language, institution_name=institution_name)
    runnable = create_agent(model=llm, tools=tools, system_prompt=system_prompt)
    return Agent(runnable=runnable, llm=llm, tools=tools)


@dataclass
class AgentResult:
    answer: AdvisorAnswer
    tool_calls: list   # [{"name": ..., "args": {...}, "result": ...}], in call order
    raw_text: str        # the agent's last free-text message, kept for the harness/debugging


def _extract_tool_calls(messages) -> list:
    """Pair each AI tool_call with its ToolMessage result, in the order the calls finished."""
    pending, calls = {}, []
    for msg in messages:
        if getattr(msg, "type", None) == "ai" and getattr(msg, "tool_calls", None):
            for c in msg.tool_calls:
                pending[c["id"]] = {"name": c["name"], "args": c["args"]}
        elif getattr(msg, "type", None) == "tool":
            entry = pending.pop(getattr(msg, "tool_call_id", None),
                                {"name": getattr(msg, "name", "?"), "args": {}})
            entry["result"] = msg.content
            calls.append(entry)
    return calls


def _safe_fallback(reason: str) -> AdvisorAnswer:
    return AdvisorAnswer(
        answer=f"Something went wrong producing a structured answer ({reason}). "
               "Please ask a human advisor.",
        citations=[], confidence="Low", next_steps=[], human_contact=None,
    )


def run_agent(agent: Agent, question: str, language: str = "en") -> AgentResult:
    """Run one turn: the tool-calling loop first (it may call several tools), then a second,
    structured-output call turns that conversation into an AdvisorAnswer. Two calls, not one,
    so the free-form tool loop (well supported) and the strict output schema (brief
    requirement) do not have to be the same LLM call."""
    try:
        result = agent.runnable.invoke({"messages": [{"role": "user", "content": question}]})
        messages = result["messages"]
    except Exception as e:
        # The tool-calling phase itself failed (e.g. the free tier's per-minute token limit
        # was hit on a hard question) - return a safe low-confidence answer instead of
        # crashing the whole run; a human should answer this one.
        return AgentResult(answer=_safe_fallback(f"{type(e).__name__}: {e}"),
                           tool_calls=[], raw_text="")

    tool_calls = _extract_tool_calls(messages)
    raw_text = next((m.content for m in reversed(messages)
                     if getattr(m, "type", None) == "ai" and m.content), "")

    finalize = list(messages) + [{"role": "user", "content": FINALIZE_INSTRUCTIONS}]
    try:
        structured = agent.llm.with_structured_output(AdvisorAnswer).invoke(finalize)
        answer = structured if isinstance(structured, AdvisorAnswer) \
            else AdvisorAnswer.model_validate(structured)
    except Exception as e:
        answer = _safe_fallback(f"{type(e).__name__}: {e}")
    return AgentResult(answer=answer, tool_calls=tool_calls, raw_text=raw_text)
