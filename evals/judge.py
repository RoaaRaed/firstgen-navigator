"""LLM-as-judge groundedness (Week 5).

A second model reads the advisor's answer next to the passages it cited and says how many of the
answer's factual claims those passages support. The judge is a DIFFERENT model from the advisor
(so the advisor does not grade its own work) and has its own free-tier quota.

    score = supported claims / total claims        (per answer, 0.0 to 1.0)

The prompt and the model name are printed in evals/eval_report.md, because the brief asks us to
record them. Change JUDGE_PROMPT and the old scores are no longer comparable: delete the "judge"
entries from evals/eval_results.json (or rerun with --rejudge) after editing it.
"""
from __future__ import annotations

import json
import os
import re

DEFAULT_JUDGE_MODEL = "llama-3.3-70b-versatile"

JUDGE_PROMPT = """You are a strict fact-checker for a college-advising chatbot.

You get a student's QUESTION, the chatbot's ANSWER, and the SOURCES the chatbot cited.
1. Split the ANSWER into its factual claims: dates, amounts, eligibility rules, steps, names of
   offices or programs. Ignore greetings, polite phrasing, "contact your advisor" style
   suggestions, and statements that something was not found.
2. For each claim decide whether the SOURCES state it or it follows directly from them. A claim
   that is true in the real world but not in the SOURCES is NOT supported.
3. The ANSWER may be in Arabic. Judge by meaning, not by wording.

Reply with ONLY one JSON object, no other text:
{"total_claims": <integer>, "supported_claims": <integer>, "unsupported": ["<short quote of each unsupported claim>"]}"""


def build_judge_input(question: str, answer: str, evidence: list[dict]) -> str:
    sources = "\n\n".join(f"[{e['source_id']}]\n{e['text']}" for e in evidence) or "(no sources)"
    return f"QUESTION:\n{question}\n\nANSWER:\n{answer}\n\nSOURCES:\n{sources}"


def parse_judge(text: str) -> dict:
    """Read the judge's reply. Returns {"total","supported","score","unsupported"} or {"error": ...}."""
    text = text if isinstance(text, str) else str(text)
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return {"error": "no JSON in the judge reply"}
    try:
        data = json.loads(match.group(0))
        total = int(data["total_claims"])
        supported = int(data["supported_claims"])
    except (ValueError, KeyError, TypeError):
        return {"error": "the judge reply was not the expected JSON"}
    if total < 0 or supported < 0 or supported > total:
        return {"error": f"impossible counts ({supported} of {total})"}
    unsupported = [str(u) for u in (data.get("unsupported") or [])][:5]
    return {"total": total, "supported": supported,
            "score": (supported / total) if total else None, "unsupported": unsupported}


def get_judge_llm(model: str | None = None):
    from core.agent import get_llm

    return get_llm(model=model or os.getenv("JUDGE_MODEL", DEFAULT_JUDGE_MODEL), temperature=0.0, max_tokens=500)


def judge_run(llm, question: str, run: dict, model: str) -> dict:
    """Judge one saved advisor run. The caller handles rate limits."""
    reply = llm.invoke([("system", JUDGE_PROMPT),
                        ("user", build_judge_input(question, run["answer"], run["evidence"]))])
    out = parse_judge(getattr(reply, "content", reply))
    out["model"] = model
    return out
