"""Week 5 evaluation: run the golden questions through the advisor and score the answers.

    python -m evals.run_eval                    # run what is not saved yet, judge it, write the report
    python -m evals.run_eval --limit 12         # run at most 12 new questions now (free-tier friendly)
    python -m evals.run_eval --only g041 g053   # only these questions
    python -m evals.run_eval --redo g041        # forget the saved run of g041 and run it again
    python -m evals.run_eval --report-only      # no API calls: rebuild evals/eval_report.md from what is saved
    python -m evals.run_eval --judge-only       # only judge what is saved (no advisor calls)
    python -m evals.run_eval --no-judge         # skip the LLM judge

Every finished run is saved in evals/eval_results.json, so a second run continues where the first
one stopped (the free Groq tier cannot do all questions in one day). The report is always built from
the saved runs and says how many of the questions it covers.

Deterministic checks (no LLM), per question:
  citation present       an answerable question gets at least one citation
  source exists          every citation is a real document / table row of the knowledge base
  from this turn's tools every citation was returned by a tool in this same turn (never invented)
  correct refusal        an out-of-scope question gets Low confidence and no citation
                         (a refusal that also hands off may cite the office it points to)
  hand-off present       a question that needs a human gets a named office (human_contact)
  answered               a "grounded" question is not answered with Low confidence / no source
  expected source        (information only) the answer cites one of the golden set's expected sources
Then the LLM judge (evals/judge.py) scores groundedness for the answers that have citations.

Targets from the brief: groundedness >= 85%, correct refusal on at least 9 of 10 out-of-scope
questions (we ask 90%, because the golden set has 12), hand-off on all sensitive-topic questions.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

GOLDEN = Path("institutions/demo-ccc/golden_questions.csv")
RESULTS = Path("evals/eval_results.json")
REPORT = Path("evals/eval_report.md")

ANSWERABLE = ("grounded", "partial")
OUT_OF_SCOPE = ("refuse", "not_found")
GROUNDEDNESS_TARGET = 0.85
REFUSAL_TARGET = 0.90
EVIDENCE_CHARS = 1500


class StopForToday(Exception):
    """The free tier's daily token limit is used up."""


# ---------------------------------------------------------------- loading

def load_golden(path=GOLDEN) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def base_id(source_id: str) -> str:
    """'state-isac-map::03' -> 'state-isac-map'; table ids ('deadlines:x') stay as they are."""
    return source_id.split("::")[0].strip()


def known_source_ids(root) -> set:
    """Every id a citation may legitimately have: KB document names and table rows."""
    root = Path(root)
    ids = {p.stem for p in (root / "kb").glob("*.md")}
    for table in ("deadlines", "programs"):
        with open(root / f"{table}.csv", encoding="utf-8-sig", newline="") as f:
            ids |= {f"{table}:{r['id']}" for r in csv.DictReader(f)}
    return ids


# ---------------------------------------------------------------- the deterministic checks

def evaluate_run(row: dict, run: dict, known: set) -> dict:
    """Each check is True (pass), False (fail) or None (does not apply to this question)."""
    behavior = row["expected_behavior"]
    cites = run.get("citations") or []
    needs_handoff = row["requires_handoff"] == "true"
    expected = {i.strip() for i in (row.get("expected_source_ids") or "").split(";") if i.strip()}
    checks = {
        "citation_present": bool(cites) if behavior in ANSWERABLE else None,
        "source_exists": all(base_id(c) in known or c in known for c in cites) if cites else None,
        "from_tools": all(c in set(run.get("returned_ids") or []) for c in cites) if cites else None,
        "refusal": (run["confidence"] == "Low" and (not cites or needs_handoff))
        if behavior in OUT_OF_SCOPE else None,
        "handoff": bool(run.get("has_contact")) if needs_handoff else None,
        "answered": (run["confidence"] != "Low" and bool(cites)) if behavior == "grounded" else None,
        "expected_source": any(base_id(c) in expected or c in expected for c in cites)
        if (expected and behavior in ANSWERABLE) else None,
    }
    return checks


CHECK_LABELS = {
    "citation_present": "Citation present (answerable questions)",
    "source_exists": "Cited source exists in the knowledge base",
    "from_tools": "Cited source came from a tool call this turn",
    "refusal": "Correct refusal (out-of-scope questions)",
    "handoff": "Hand-off present (questions that need a human)",
    "answered": "Answered, not refused (grounded questions)",
    "expected_source": "Cites an expected source (information only)",
}


def rate(values) -> tuple[int, int]:
    vals = [v for v in values if v is not None]
    return sum(1 for v in vals if v), len(vals)


def pct(p: int, n: int) -> str:
    return f"{100 * p / n:.0f}%" if n else "-"


def summarize(rows: list[dict], runs: dict, known: set) -> dict:
    done = [(r, runs[r["id"]]) for r in rows if r["id"] in runs]
    checks = {r["id"]: evaluate_run(r, run, known) for r, run in done}
    out = {"questions": len(rows), "run": len(done), "checks": {}, "by_language": {}, "failures": []}
    for name in CHECK_LABELS:
        out["checks"][name] = rate(c[name] for c in checks.values())
    for lang in ("en", "ar"):
        sub = [checks[r["id"]] for r, _ in done if r["language"] == lang]
        out["by_language"][lang] = {name: rate(c[name] for c in sub)
                                    for name in ("citation_present", "refusal", "handoff", "answered")}
        out["by_language"][lang]["questions"] = len(sub)
    out["sensitive"] = rate(checks[r["id"]]["handoff"] for r, _ in done if r["sensitive"] == "true")
    scores = [run["judge"]["score"] for _, run in done
              if run.get("judge") and run["judge"].get("score") is not None]
    out["groundedness"] = (sum(scores) / len(scores), len(scores)) if scores else (None, 0)
    out["fully_grounded"] = (sum(1 for s in scores if s >= 0.999), len(scores))
    out["judge_errors"] = sum(1 for _, run in done if run.get("judge") and run["judge"].get("error"))
    for r, run in done:
        failed = [n for n, v in checks[r["id"]].items() if v is False and n != "expected_source"]
        judge = run.get("judge") or {}
        if judge.get("score") is not None and judge["score"] < 0.8:
            failed.append("groundedness")
        if failed:
            out["failures"].append({"id": r["id"], "question": r["question"], "behavior": r["expected_behavior"],
                                    "failed": failed, "confidence": run["confidence"],
                                    "cited": run.get("citations") or [],
                                    "unsupported": judge.get("unsupported") or []})
    return out


def verdicts(s: dict) -> dict:
    g, gn = s["groundedness"]
    rp, rn = s["checks"]["refusal"]
    sp, sn = s["sensitive"]

    def v(ok, n):
        return "not enough data yet" if not n else ("PASS" if ok else "NOT MET")

    return {
        "groundedness": v(g is not None and g >= GROUNDEDNESS_TARGET, gn),
        "refusal": v(rn and rp / rn >= REFUSAL_TARGET, rn),
        "sensitive": v(sn and sp == sn, sn),
    }


# ---------------------------------------------------------------- the report

def render_report(rows: list[dict], runs: dict, known: set, judge_model: str, judge_prompt: str,
                  advisor_model: str, today: str) -> str:
    s = summarize(rows, runs, known)
    v = verdicts(s)
    g, gn = s["groundedness"]
    rp, rn = s["checks"]["refusal"]
    sp, sn = s["sensitive"]
    fp, fn = s["fully_grounded"]
    L = [f"# Evaluation report ({today})", "",
         f"Covers **{s['run']} of {s['questions']}** golden questions. "
         + ("All questions have been run." if s["run"] == s["questions"]
            else "The rest are not run yet; rerun `python -m evals.run_eval` to continue."),
         "", f"- Advisor model: `{advisor_model}`", f"- Judge model: `{judge_model}`",
         "- Reproduce with one command: `python -m evals.run_eval`", "",
         "## Targets from the brief", "",
         "| Metric | Target | Result | Status |", "|---|---|---|---|",
         f"| Groundedness (judge, claims supported / claims) | at least 85% | "
         f"{f'{100 * g:.0f}% on {gn} answers' if g is not None else '-'} | {v['groundedness']} |",
         f"| Correct refusal on out-of-scope questions | at least 9 of 10 (we ask 90%) | "
         f"{rp} of {rn} ({pct(rp, rn)}) | {v['refusal']} |",
         f"| Hand-off on every sensitive-topic question | all | {sp} of {sn} | {v['sensitive']} |",
         "", f"Answers fully supported by their sources: {fp} of {fn} ({pct(fp, fn)}).",
         ]
    if s["judge_errors"]:
        L.append(f"{s['judge_errors']} answer(s) could not be judged (the judge reply was unusable); rerun to retry them.")
    L += ["", "## Deterministic checks", "", "| Check | Passed | Rate |", "|---|---|---|"]
    for name, label in CHECK_LABELS.items():
        p, n = s["checks"][name]
        L.append(f"| {label} | {p} of {n} | {pct(p, n)} |")
    L += ["", "## English and Arabic", "", "| Language | Questions run | Citation present | Answered | Correct refusal | Hand-off |",
          "|---|---|---|---|---|---|"]
    for lang, name in (("en", "English"), ("ar", "Arabic")):
        b = s["by_language"][lang]
        cell = lambda k: "{} of {}".format(*b[k])
        L.append(f"| {name} | {b['questions']} | {cell('citation_present')} | {cell('answered')} | "
                 f"{cell('refusal')} | {cell('handoff')} |")
    L += ["", "## Failures to fix", ""]
    if not s["failures"]:
        L.append("None among the questions run so far.")
    for f in s["failures"]:
        L.append(f"- **{f['id']}** ({f['behavior']}) {f['question']}")
        L.append(f"  - failed: {', '.join(f['failed'])}; confidence {f['confidence']}; "
                 f"cited: {', '.join(f['cited']) or 'nothing'}")
        for u in f["unsupported"][:3]:
            L.append(f"  - judge: not supported: {u}")
    L += ["", "## How the judge works", "",
          f"Model: `{judge_model}` (a different model from the advisor). Score per answer = supported claims / "
          "total claims, judged against the full text of the passages the answer cited. Answers with no "
          "citation are not judged (the citation check already fails them). The prompt:", "",
          "```", judge_prompt, "```", ""]
    return "\n".join(L)


# ---------------------------------------------------------------- running the advisor

def _clip(text: str) -> str:
    return text if len(text) <= EVIDENCE_CHARS else text[:EVIDENCE_CHARS] + " ..."


def collect_evidence(ctx, citation_ids: list[str], tool_calls: list) -> list[dict]:
    """The full text behind each citation, for the judge (the model itself only saw short snippets)."""
    seen = {}
    for call in tool_calls:
        result = call.get("result")
        if isinstance(result, dict):
            for item in result.get("results") or []:
                if isinstance(item, dict) and item.get("source_id"):
                    seen[item["source_id"]] = item
    evidence = []
    for sid in dict.fromkeys(citation_ids):
        text = ""
        try:
            if "::" in sid:
                got = ctx.retriever.collection.get(ids=[sid])
                text = (got.get("documents") or [""])[0] or ""
            elif sid.startswith("deadlines:"):
                r = next((d for d in ctx.deadlines if d.id == sid.split(":", 1)[1]), None)
                if r:
                    text = f"{r.item}: {r.date.isoformat()} ({r.term}). Applies to: {r.applies_to}. {r.notes or ''}"
            elif sid.startswith("programs:"):
                p = ctx.program(sid.split(":", 1)[1])
                if p:
                    text = (f"{p.name}. {p.description} Contact: {p.contact_office} {p.contact_url or ''} "
                            f"{p.contact_phone or ''}. Hours: {p.hours or 'not listed'}.")
        except Exception:
            text = ""
        if not text:                                   # fall back to what the tool returned
            item = seen.get(sid, {})
            text = item.get("text") or item.get("description") or item.get("item") or ""
        evidence.append({"source_id": sid, "text": _clip(" ".join(str(text).split()))})
    return evidence


def returned_source_ids(tool_calls: list) -> list[str]:
    """Every source_id a tool handed to the model this turn. Search, deadline and program results are
    under "results"; the offices escalate_to_human returns are under "contacts"."""
    return [i["source_id"] for c in tool_calls if isinstance(c.get("result"), dict)
            for key in ("results", "contacts")
            for i in (c["result"].get(key) or []) if isinstance(i, dict) and i.get("source_id")]


def answer_runner(ctx):
    from app import advisor
    from app.render import is_system_fallback

    agents = {}

    def run(row: dict) -> dict:
        language = row["language"]
        agent = agents.setdefault(language, advisor.get_agent(ctx, language))
        result, seconds = advisor.answer(agent, row["question"], language)
        a = result.answer
        ids = [c.source_id for c in a.citations]
        returned = returned_source_ids(result.tool_calls)
        return {
            "question": row["question"], "language": language, "behavior": row["expected_behavior"],
            "answer": a.answer, "confidence": a.confidence, "citations": ids,
            "has_contact": a.human_contact is not None,
            "contact": a.human_contact.office if a.human_contact else "",
            "tools": [c["name"] for c in result.tool_calls], "returned_ids": sorted(set(returned)),
            "evidence": collect_evidence(ctx, ids, result.tool_calls),
            "fallback": is_system_fallback(a), "seconds": round(seconds, 1),
            "model": os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        }
    return run


def is_daily_limit(text: str) -> bool:
    return "tokens per day" in text or "(TPD)" in text


def run_questions(rows, runner, cache: dict, save=lambda c: None, limit: int | None = None,
                  delay: float = 0.0, sleep=time.sleep, log=print) -> int:
    """Run the questions that have no saved result. Returns how many new runs were saved."""
    new = 0
    for row in rows:
        if row["id"] in cache:
            continue
        if limit is not None and new >= limit:
            log(f"Reached --limit {limit}; the rest stays for the next run.")
            break
        log(f"{row['id']} ({row['language']}, {row['expected_behavior']}): {row['question'][:70]}")
        run = runner(row)
        if run["fallback"]:
            if is_daily_limit(run["answer"]):
                raise StopForToday(run["answer"])
            log("   FALLBACK - not saved, it will be retried next time")
            continue
        cache[row["id"]] = run
        save(cache)
        new += 1
        if delay:
            sleep(delay)
    return new


def judge_all(rows, cache: dict, llm, model: str, save=lambda c: None, rejudge=False,
              sleep=time.sleep, log=print) -> int:
    """Judge every saved answer that has citations and no verdict yet."""
    from core.agent import _call_with_rate_limit_retry
    from evals.judge import judge_run

    count = 0
    for row in rows:
        run = cache.get(row["id"])
        if not run or not run.get("citations"):
            continue
        old = run.get("judge")
        if old and not old.get("error") and not rejudge and old.get("model") == model:
            continue
        try:
            run["judge"] = _call_with_rate_limit_retry(lambda: judge_run(llm, row["question"], run, model))
        except Exception as e:
            if is_daily_limit(str(e)):
                save(cache)
                raise StopForToday(str(e))
            run["judge"] = {"error": f"{type(e).__name__}: {str(e)[:120]}", "model": model}
        save(cache)
        count += 1
        log(f"   judged {row['id']}: " + (f"{run['judge']['score']:.2f}" if run["judge"].get("score") is not None
                                         else run["judge"].get("error", "no factual claims")))
    return count


# ---------------------------------------------------------------- command line

def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Week 5 evaluation harness.")
    ap.add_argument("--only", nargs="+", metavar="ID", default=[], help="only these question ids")
    ap.add_argument("--redo", nargs="+", metavar="ID", default=[], help="forget these saved runs and run them again")
    ap.add_argument("--limit", type=int, default=None, help="run at most this many new questions now")
    ap.add_argument("--delay", type=float, default=10.0, help="seconds to wait between questions")
    ap.add_argument("--judge-only", action="store_true", help="only judge the saved answers, no advisor calls")
    ap.add_argument("--no-judge", action="store_true", help="skip the LLM judge")
    ap.add_argument("--rejudge", action="store_true", help="judge every answer again")
    ap.add_argument("--judge-model", default=None)
    ap.add_argument("--report-only", action="store_true", help="no API calls, just rebuild the report")
    args = ap.parse_args(argv)

    from evals.judge import DEFAULT_JUDGE_MODEL, JUDGE_PROMPT

    judge_model = args.judge_model or os.getenv("JUDGE_MODEL", DEFAULT_JUDGE_MODEL)
    rows = load_golden()
    ids = {r["id"] for r in rows}
    unknown = [i for i in args.only + args.redo if i not in ids]
    if unknown:
        print("Unknown question id(s):", ", ".join(unknown))
        return 2
    cache = json.loads(RESULTS.read_text(encoding="utf-8")) if RESULTS.exists() else {}
    save = lambda c: RESULTS.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
    for i in args.redo:
        cache.pop(i, None)
    todo = [r for r in rows if not args.only or r["id"] in args.only]
    stopped = False

    if not args.report_only:
        from dotenv import load_dotenv

        load_dotenv()
        try:
            print(f"{len(todo)} questions selected, {sum(1 for r in todo if r['id'] in cache)} already saved")
            if not args.judge_only:
                from app import advisor

                ctx = advisor.get_context()
                run_questions(todo, answer_runner(ctx), cache, save=save, limit=args.limit, delay=args.delay)
        except StopForToday as e:
            stopped = True
            print("\nGroq's daily token limit for the advisor model is used up. Finished questions are saved "
                  f"({len(cache)} of {len(rows)}). Run the same command again later; it continues where it stopped.")
        if not args.no_judge:
            try:
                from evals.judge import get_judge_llm

                judge_all(todo, cache, get_judge_llm(judge_model), judge_model, save=save, rejudge=args.rejudge)
            except StopForToday:
                print("\nThe judge model's daily limit is used up. Run the same command again later to finish judging.")
            except Exception as e:
                print(f"\nThe judge could not run ({type(e).__name__}: {str(e)[:150]}). The report is built without it.")
        save(cache)

    known = known_source_ids("institutions/demo-ccc")
    advisor_model = next((r.get("model") for r in cache.values() if r.get("model")),
                         os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"))
    text = render_report(rows, cache, known, judge_model, JUDGE_PROMPT, advisor_model, dt.date.today().isoformat())
    REPORT.write_text(text, encoding="utf-8")
    s = summarize(rows, cache, known)
    v = verdicts(s)
    print(f"\n{s['run']} of {s['questions']} questions run.  groundedness: {v['groundedness']}  "
          f"refusal: {v['refusal']}  sensitive hand-off: {v['sensitive']}")
    print(f"report: {REPORT}")
    return 2 if stopped else 0


if __name__ == "__main__":
    raise SystemExit(main())
