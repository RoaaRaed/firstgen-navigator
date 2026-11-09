"""Command-line harness: ask the advisor one question and see everything the Week 3
benchmark cares about - the answer, its confidence label, every citation, next steps, the
hand-off contact if there is one, and exactly which tools were called with which arguments.

    python -m core.harness "What is the MAP grant?"
    python -m core.harness "ما هو الموعد النهائي لمنحة MAP؟" --language ar
    python -m core.harness "..." --save docs/transcripts/01.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from core.agent import AgentResult, build_agent, run_agent
from core.tools import load_context


def format_answer(question: str, language: str, result: AgentResult, seconds: float | None = None) -> str:
    a = result.answer
    lines = [
        f"Q ({language}): {question}",
        "",
        f"Confidence: {a.confidence}",
        "",
        "Answer:",
        a.answer,
        "",
        "Citations:" if a.citations else "Citations: (none)",
    ]
    for c in a.citations:
        lines.append(f"  - [{c.source_id}] {c.label}")
    if a.next_steps:
        lines += ["", "Next steps:"]
        lines += [f"  - {s}" for s in a.next_steps]
    if a.human_contact:
        hc = a.human_contact
        contact = hc.office + (f" - {hc.url}" if hc.url else "") + (f" - {hc.phone}" if hc.phone else "")
        lines += ["", f"Hand-off: {contact}"]
    lines += ["", "Tool calls:" if result.tool_calls else "Tool calls: (none)"]
    lines += [f"  {i}. {c['name']}({c['args']})" for i, c in enumerate(result.tool_calls, 1)]
    if seconds is not None:
        lines += ["", f"({seconds:.1f}s)"]
    return "\n".join(lines)


def transcript_entry(question: str, language: str, result: AgentResult, seconds: float) -> dict:
    """What gets saved to docs/transcripts/: enough to check tool selection and confidence
    later without rerunning the model."""
    a = result.answer
    return {
        "question": question,
        "language": language,
        "confidence": a.confidence,
        "answer": a.answer,
        "citations": [{"source_id": c.source_id, "label": c.label} for c in a.citations],
        "next_steps": a.next_steps,
        "human_contact": a.human_contact.model_dump() if a.human_contact else None,
        "tool_calls": [{"name": c["name"], "args": c["args"]} for c in result.tool_calls],
        "seconds": round(seconds, 1),
    }


def ask(question: str, language: str = "en", institution: str = "demo-ccc") -> tuple[AgentResult, float]:
    ctx = load_context(institution)
    agent = build_agent(ctx, language=language)
    t0 = time.time()
    result = run_agent(agent, question, language=language)
    return result, time.time() - t0


def save_transcript(path: str, question: str, language: str, result: AgentResult, seconds: float) -> Path:
    entry = transcript_entry(question, language, result, seconds)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    from dotenv import load_dotenv

    load_dotenv()
    ap = argparse.ArgumentParser(description="Ask the advisor one question from the command line.")
    ap.add_argument("question")
    ap.add_argument("--language", choices=("en", "ar"), default="en")
    ap.add_argument("--institution", default="demo-ccc")
    ap.add_argument("--save", help="also save this turn as JSON, e.g. docs/transcripts/01.json")
    args = ap.parse_args(argv)

    result, seconds = ask(args.question, language=args.language, institution=args.institution)
    print(format_answer(args.question, args.language, result, seconds))

    if args.save:
        out = save_transcript(args.save, args.question, args.language, result, seconds)
        print(f"\nSaved -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
