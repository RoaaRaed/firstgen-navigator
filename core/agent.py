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
import re
import time
import traceback
from dataclasses import dataclass, field

from langchain_core.tools import tool
from langchain_groq import ChatGroq

from core.compact import for_model
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


LOOP_MAX_TOKENS = 1200  # the tool-calling phase writes tool calls and a short draft, not the final answer
LEAN_SEARCH_K = 4       # "lean" retry after a 413 "request too large": half the passages per search
LEAN_ROWS = 3           # ... and at most this many rows of deadlines / programs shown to the model
# Every extra tool call is another model call that re-sends the whole conversation (the log showed
# 8 calls and ~35k tokens for ONE question), so the code enforces what the prompt only asks for.
MAX_TOOL_CALLS = 4      # search + deadlines + programs, per question (escalate_to_human is never blocked)
MAX_SEARCHES = 2        # the prompt says "at most twice"
TOOL_LIMIT_TEXT = ("Tool limit reached for this question. Do not call more tools; write the answer "
                   "from the results you already have, and say what you could not find.")


def get_llm(model: str | None = None, temperature: float = 0.0, max_tokens: int = 2000):
    """The one place that knows which LLM we use (Groq free tier for development)."""
    from dotenv import load_dotenv

    load_dotenv()
    model = model or os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set. Add it to .env (see .env.example).")
    return ChatGroq(model=model, api_key=api_key, temperature=temperature, max_tokens=max_tokens)


def _trim_rows(out: dict, n: int) -> dict:
    """The same result with at most n rows (only what the MODEL reads is trimmed in lean mode)."""
    rows = out.get("results") if isinstance(out, dict) else None
    return {**out, "results": rows[:n]} if isinstance(rows, list) else out


def build_langchain_tools(ctx, lean: dict | None = None, budget: dict | None = None) -> list:
    """Wrap the four tools so the model only sees the arguments it should fill in.
    `ctx` (the loaded institution data) is bound in this closure - the model never sees it
    and cannot change it.

    `lean` is a shared switch ({"on": bool}). run_agent turns it on for one retry when Groq says
    the request was too large (413): the model then reads fewer passages and rows."""
    lean = lean if lean is not None else {"on": False}
    budget = budget if budget is not None else {"used": 0, "searches": 0}

    def over_budget(kind: str) -> bool:
        """Count this call; True when the question has already used its share of tool calls."""
        if budget["used"] >= MAX_TOOL_CALLS or (kind == "search" and budget["searches"] >= MAX_SEARCHES):
            return True
        budget["used"] += 1
        if kind == "search":
            budget["searches"] += 1
        return False

    skipped = lambda: (TOOL_LIMIT_TEXT, {"results": [], "skipped": "tool limit reached"})

    # Tool names must exactly match what the system prompt calls them (Groq rejects a tool
    # call whose name is not in the request's tool list, so the wrapper and the prompt text
    # must agree character for character - hence the plain names here, not "..._tool").
    # response_format="content_and_artifact": the model reads a short text (core/compact.py), the
    # page still gets the full dict (links, dates, hours) from the tool message's artifact.
    @tool(response_format="content_and_artifact")
    def search_knowledge_base(query: str, language: str = "en", layer: str = ""):
        """Search the official documents (federal, Illinois state, and college pages) for
        passages that answer the student's question. Use for how something works, who is
        eligible, what steps to take, or what a term means.

        Args:
            query: a short search phrase IN ENGLISH (the documents are English); translate it
                if the student wrote Arabic.
            language: "en" or "ar" - the language of the student's question.
            layer: optional: "federal", "state" or "institution". Leave empty otherwise.
        """
        if over_budget("search"):
            return skipped()
        extra = {"k": LEAN_SEARCH_K} if lean["on"] else {}
        out = _search_knowledge_base(ctx, query, language=language, layer=layer or None, **extra)
        return for_model("search_knowledge_base", out), out

    @tool(response_format="content_and_artifact")
    def lookup_deadlines(term: str = "", topic: str = ""):
        """Look up exact dates from the official deadlines table (FAFSA, MAP, Alternative
        Application, registration, withdrawal, term dates). Use for any "when" question.

        Args:
            term: optional term or aid year, e.g. "Spring 2027", "2026-27".
            topic: optional English words, e.g. "withdrawal", "first day", "FAFSA".
        """
        if over_budget("deadlines"):
            return skipped()
        out = _lookup_deadlines(ctx, term=term, topic=topic)
        shown = _trim_rows(out, LEAN_ROWS + 1) if lean["on"] else out
        return for_model("lookup_deadlines", shown), out

    @tool(response_format="content_and_artifact")
    def match_programs(tags: list[str] | None = None, categories: list[str] | None = None,
                       keywords: str = ""):
        """Find support programs and offices for the student's situation (aid, food, child
        care, immigrant services, ESL, transfer, wellness, disability, academic help).

        Args:
            tags: profile tags, any of: first_gen, working_20plus, working_30plus, caregiver,
                fafsa_ineligible_or_unsure, esl, transfer.
            categories: any of: financial, academic, wellness, transfer, immigrant_services,
                childcare, food, disability.
            keywords: optional English words.
        """
        if over_budget("programs"):
            return skipped()
        out = _match_programs(ctx, tags=tags or [], categories=categories or [], keywords=keywords)
        shown = _trim_rows(out, LEAN_ROWS) if lean["on"] else out
        return for_model("match_programs", shown), out

    @tool(response_format="content_and_artifact")
    def escalate_to_human(topic: str):
        """Get the named office a student should talk to for something the documents cannot
        decide alone: eligibility decisions, immigration, verification, a crisis. Never give
        legal advice and never ask about immigration status.

        Args:
            topic: financial_aid, state_aid, immigration, academic, transfer, wellness, food,
                snap, childcare, disability (other words are matched to the closest topic).
        """
        out = _escalate_to_human(ctx, topic)
        return for_model("escalate_to_human", out), out

    return [search_knowledge_base, lookup_deadlines, match_programs, escalate_to_human]


@dataclass
class Agent:
    """Bundles the tool-calling runnable and the chat model (reused for the structured pass)."""
    runnable: object
    llm: object
    tools: list = field(default_factory=list)
    lean: dict = field(default_factory=lambda: {"on": False})   # shared with the tools, see run_agent
    budget: dict = field(default_factory=lambda: {"used": 0, "searches": 0})   # tool calls this question


def build_agent(ctx, language: str = "en", institution_name: str = DEFAULT_INSTITUTION_NAME,
                llm=None) -> Agent:
    from langchain.agents import create_agent

    # Groq counts the room reserved for the reply (max_tokens) as part of each request. The tool
    # loop needs little, so it gets a smaller reserve; the final structured answer keeps 2000.
    loop_llm = llm or get_llm(max_tokens=LOOP_MAX_TOKENS)
    llm = llm or get_llm()
    lean = {"on": False}
    budget = {"used": 0, "searches": 0}
    tools = build_langchain_tools(ctx, lean, budget)
    system_prompt = load_system_prompt(language, institution_name=institution_name)
    runnable = create_agent(model=loop_llm, tools=tools, system_prompt=system_prompt)
    return Agent(runnable=runnable, llm=llm, tools=tools, lean=lean, budget=budget)


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
            artifact = getattr(msg, "artifact", None)  # the full dict, when the tool kept one
            entry["result"] = artifact if artifact is not None else msg.content
            calls.append(entry)
    return calls


def _safe_fallback(reason: str) -> AdvisorAnswer:
    return AdvisorAnswer(
        answer=f"Something went wrong producing a structured answer ({reason}). "
               "Please ask a human advisor.",
        citations=[], confidence="Low", next_steps=[], human_contact=None,
    )


MAX_RATE_LIMIT_WAIT = 65.0   # seconds; the free tier's limit is per minute, so one minute is enough
RATE_LIMIT_RETRIES = 2


def _rate_limit_wait(exc) -> float | None:
    """If `exc` is a "too many requests / tokens per minute" error that a short wait will clear,
    the seconds Groq asks us to wait (parsed from "Please try again in 8.5s" / "1m3.5s" /
    "340ms"), else None. A wait longer than MAX_RATE_LIMIT_WAIT (for example the daily token
    limit: "try again in 19m38s") returns None: sleeping that long inside a chat answer is no use."""
    text = str(exc)
    if "429" not in text and "rate limit" not in text.lower() and type(exc).__name__ != "RateLimitError":
        return None
    m = re.search(r"try again in ((?:\d+(?:\.\d+)?(?:ms|m|s))+)", text)
    seconds = 0.0
    if m:
        for num, unit in re.findall(r"(\d+(?:\.\d+)?)(ms|m|s)", m.group(1)):
            seconds += float(num) * {"ms": 0.001, "s": 1, "m": 60}[unit]
    wait = max(seconds, 5.0) + 1.0
    return wait if wait <= MAX_RATE_LIMIT_WAIT else None


def is_daily_limit_error(text: str) -> bool:
    """True for Groq's "tokens per day (TPD)" error, which only time (not a retry) can clear."""
    return "tokens per day" in text or "(TPD)" in text


def _call_with_rate_limit_retry(fn, sleep=None):
    """Run fn(); if the free tier's per-minute limit is hit, wait as long as Groq asks and try
    again (up to RATE_LIMIT_RETRIES times). Any other error is raised unchanged."""
    for attempt in range(RATE_LIMIT_RETRIES + 1):
        try:
            return fn()
        except Exception as e:
            wait = _rate_limit_wait(e)
            if wait is None or attempt == RATE_LIMIT_RETRIES:
                raise
            (sleep or time.sleep)(wait)


def _with_profile(question: str, profile: str) -> str:
    return f"{profile}\n\nStudent's question:\n{question}" if profile else question


def is_too_large_error(exc) -> bool:
    """Groq's 413 "Request too large for model ... tokens per minute": the single request is over
    the cap, so waiting does not help, but a smaller request does."""
    text = str(exc)
    return "413" in text or "Request too large" in text


TOOL_USE_RETRIES = 2
TOOL_REMINDER = ("\n\n(Call only these tools: search_knowledge_base, lookup_deadlines, match_programs, "
                 "escalate_to_human. There is no tool that opens files; a source_id is only for citations.)")


VALIDATION_REMINDER = ("Your last answer was rejected: {reason}. Write it again and fix exactly that. "
                       "Copy every citation source_id exactly as a tool returned it, including its prefix "
                       "('programs:...', 'deadlines:...' or 'doc::NN'), and keep at most 3 next steps.")


def is_validation_error(exc) -> bool:
    """The structured answer came back but broke one of AdvisorAnswer's rules (for example a
    source_id without its 'programs:' prefix). Asking the model once more usually fixes it."""
    text = str(exc)
    return "validation error" in text.lower() and "AdvisorAnswer" in text


def _validation_reason(exc) -> str:
    m = re.search(r"Value error, (.*?) \[type=", str(exc), re.S)
    return " ".join(m.group(1).split())[:300] if m else "it did not fit the required format"


def is_tool_use_error(exc) -> bool:
    """Groq's 400 "tool_use_failed": the model called a tool that does not exist (it once tried
    "open_file") or wrote a malformed call. It is random, so trying again almost always works."""
    text = str(exc)
    return "tool_use_failed" in text or "Tool call validation failed" in text


def _remind_tools(payload: dict) -> dict:
    """The same payload with the list of real tool names added to the last user message."""
    msgs = [dict(m) for m in payload["messages"]]
    msgs[-1]["content"] = f"{msgs[-1]['content']}{TOOL_REMINDER}"
    return {**payload, "messages": msgs}


def _once(agent: Agent, payload: dict):
    """One run of the tool loop, starting with a full tool-call budget."""
    budget = getattr(agent, "budget", None)
    if budget is not None:
        budget["used"] = budget["searches"] = 0
    return agent.runnable.invoke(payload)


def _invoke_loop(agent: Agent, payload: dict):
    """The tool loop, with the rate-limit wait. A made-up tool name is retried with a reminder of the
    real tool names; a request that is too large is retried once in lean mode."""
    try:
        return _call_with_rate_limit_retry(lambda: _once(agent, payload))
    except Exception as e:
        if is_tool_use_error(e):
            print("[advisor] the model called a tool that does not exist; retrying")
            for attempt in range(TOOL_USE_RETRIES):
                try:
                    return _call_with_rate_limit_retry(lambda: _once(agent, _remind_tools(payload)))
                except Exception as again:
                    if not is_tool_use_error(again) or attempt == TOOL_USE_RETRIES - 1:
                        raise
        lean = getattr(agent, "lean", None)
        if not is_too_large_error(e) or lean is None:
            raise
        print("[advisor] request too large for the free tier; retrying with fewer search results")
        lean["on"] = True
        try:
            return _call_with_rate_limit_retry(lambda: _once(agent, payload))
        finally:
            lean["on"] = False


def _without_draft(messages: list) -> list:
    """The conversation minus the loop's last free-text draft (the structured pass can write the
    answer from the tool results alone). Used to shrink a finalize request that was too large."""
    msgs = list(messages)
    for i in range(len(msgs) - 1, -1, -1):
        m = msgs[i]
        if getattr(m, "type", None) == "ai" and not getattr(m, "tool_calls", None):
            return msgs[:i] + msgs[i + 1:]
    return msgs


def _print_tools(messages) -> None:
    """One terminal line listing the tool calls in order, e.g. search_knowledge_base, lookup_deadlines.

    Privacy: the arguments are the student's own words (the search query), and the terminal of a
    deployed app is a server log. So by default only the tool NAMES are printed. For debugging on
    your own computer set  ADVISOR_DEBUG_QUERIES=1  to see the first 40 characters of the arguments too."""
    show_args = os.getenv("ADVISOR_DEBUG_QUERIES") == "1"
    names = []
    for m in messages:
        if getattr(m, "type", None) == "ai":
            for c in getattr(m, "tool_calls", None) or []:
                if show_args:
                    args = c.get("args") or {}
                    first = args.get("query") or next(iter(args.values()), "")
                    names.append(f"{c.get('name')}({str(first)[:40]!r})")
                else:
                    names.append(str(c.get("name")))
    if names:
        print("[tools] " + ", ".join(names))


def _print_usage(messages) -> None:
    """One terminal line per model call with the tokens Groq counted - shows where a 413 comes from."""
    n = 0
    for m in messages:
        usage = getattr(m, "usage_metadata", None)
        if getattr(m, "type", None) == "ai" and isinstance(usage, dict):
            n += 1
            print(f"[tokens] model call {n}: input {usage.get('input_tokens')}, output {usage.get('output_tokens')}")


def run_agent(agent: Agent, question: str, language: str = "en", profile: str = "") -> AgentResult:
    """Run one turn: the tool-calling loop first (it may call several tools), then a second,
    structured-output call turns that conversation into an AdvisorAnswer. Two calls, not one,
    so the free-form tool loop (well supported) and the strict output schema (brief
    requirement) do not have to be the same LLM call.

    `profile` is an optional block of background about the student (see app/profile_block.py).
    It goes in front of the question inside the same user message, so the second call sees it too."""
    try:
        payload = {"messages": [{"role": "user", "content": _with_profile(question, profile)}]}
        result = _invoke_loop(agent, payload)
        messages = result["messages"]
        _print_usage(messages)
        _print_tools(messages)
    except Exception as e:
        traceback.print_exc()  # the page only shows a friendly message; the terminal gets the real error
        # The tool-calling phase itself failed (e.g. the free tier's per-minute token limit
        # was hit on a hard question) - return a safe low-confidence answer instead of
        # crashing the whole run; a human should answer this one.
        return AgentResult(answer=_safe_fallback(f"{type(e).__name__}: {e}"),
                           tool_calls=[], raw_text="")

    tool_calls = _extract_tool_calls(messages)
    raw_text = next((m.content for m in reversed(messages)
                     if getattr(m, "type", None) == "ai" and m.content), "")

    finalize = list(messages) + [{"role": "user", "content": FINALIZE_INSTRUCTIONS}]
    def finalize_call(msgs):
        for attempt in range(TOOL_USE_RETRIES):
            try:
                return _call_with_rate_limit_retry(
                    lambda: agent.llm.with_structured_output(AdvisorAnswer).invoke(msgs))
            except Exception as e:
                if attempt == TOOL_USE_RETRIES - 1:
                    raise
                if is_tool_use_error(e):
                    continue
                if is_validation_error(e):
                    print("[advisor] the answer did not fit the required format; asking once more")
                    msgs = list(msgs) + [{"role": "user", "content": VALIDATION_REMINDER.format(reason=_validation_reason(e))}]
                    continue
                raise

    try:
        try:
            structured = finalize_call(finalize)
        except Exception as e:
            if not is_too_large_error(e):
                raise
            print("[advisor] final request too large; retrying without the draft text")
            structured = finalize_call(_without_draft(messages) +
                                       [{"role": "user", "content": FINALIZE_INSTRUCTIONS}])
        answer = structured if isinstance(structured, AdvisorAnswer) \
            else AdvisorAnswer.model_validate(structured)
    except Exception as e:
        traceback.print_exc()
        answer = _safe_fallback(f"{type(e).__name__}: {e}")
    return AgentResult(answer=answer, tool_calls=tool_calls, raw_text=raw_text)
