"""Issue #26 - language parity: does the advisor lean on the SAME top source when the same
question is asked in English and in Arabic?

    python -m evals.parity_eval --mode retrieval   # no LLM, no API key: top search hit only
    python -m evals.parity_eval --mode answer      # the full advisor, 2 x 15 runs (slow)

Each of the 15 pairs in institutions/demo-ccc/parity_pairs.csv is one question in two
languages (10 are the Arabic twins already in golden_questions.csv, 5 were added). A pair
passes when both languages give the same top source. In retrieval mode that is the document of
the best-scoring chunk. In answer mode it is the first citation of the final answer, with the
chunk suffix removed ("state-isac-map::03" -> "state-isac-map"); table rows keep their id
("deadlines:...", "programs:..."). The target is at least 12 of 15 pairs.

Answer mode is slow and calls the Groq API, so every finished run is saved to
evals/parity_results.json and a second run continues where the first one stopped.
Runs that ended in the safe fallback (rate limit, import error) are not saved: they are retried.
The advisor is asked WITHOUT a student profile, so only the language differs between the two.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

PAIRS = Path("institutions/demo-ccc/parity_pairs.csv")
NOTES = Path("evals/parity_notes.txt")
RESULTS = Path("evals/parity_results.json")
REPORT = Path("evals/parity_report.md")
TARGET = 12
SEARCH_K = 8


def is_daily_limit_error(text: str) -> bool:
    return "tokens per day" in text or "(TPD)" in text


def load_pairs(path=PAIRS) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def base_source(source_id: str) -> str:
    """"state-isac-map::03" -> "state-isac-map"; "programs:x" and "deadlines:x" stay as they are."""
    return (source_id or "").split("::", 1)[0].strip()


def answer_sources(citations: list[str]) -> list[str]:
    """The distinct documents/rows cited, in the order the answer cites them."""
    out = []
    for c in citations:
        b = base_source(c)
        if b and b not in out:
            out.append(b)
    return out


class DailyLimitReached(Exception):
    """Groq's per-day token limit is used up: more runs now would only fail."""


def compare(en: dict, ar: dict) -> dict:
    """One pair's verdict. `en` / `ar` are {"sources": [...], "fallback": bool}."""
    if en.get("fallback") or ar.get("fallback"):
        status = "error"
    else:
        status = "same" if en["sources"][:1] and en["sources"][:1] == ar["sources"][:1] else "different"
    shared = sorted(set(en.get("sources", [])) & set(ar.get("sources", [])))
    verdict = {"status": status, "same_top": status == "same", "shared": shared}
    # Retrieval mode also keeps each language's top-5 documents. That allows a softer reading of
    # the same pair: does each language's best document at least appear in the other's top 5?
    if en.get("top5") and ar.get("top5") and status != "error":
        en5, ar5 = [d for d, _ in en["top5"]], [d for d, _ in ar["top5"]]
        verdict["top5_overlap"] = len(set(en5) & set(ar5))
        verdict["soft_same"] = en5[0] in ar5 and ar5[0] in en5
    return verdict


def summarize(rows: list[dict], target: int = TARGET) -> dict:
    same = sum(1 for r in rows if r["verdict"]["status"] == "same")
    errors = sum(1 for r in rows if r["verdict"]["status"] == "error")
    out = {"pairs": len(rows), "same_top": same, "errors": errors,
           "target": target, "passed": same >= target}
    if any("soft_same" in r["verdict"] for r in rows):
        out["soft_same"] = sum(1 for r in rows if r["verdict"].get("soft_same"))
    return out


# ---- the two ways to get the sources for one question ----

def retrieval_runner(ctx):
    def run(question: str, language: str) -> dict:
        hits = ctx.retriever.search(question, k=SEARCH_K)
        top5: list = []                                  # the best 5 distinct documents with their best score
        for h in hits:
            doc = base_source(h.chunk_id)
            if doc and all(doc != d for d, _ in top5):
                top5.append([doc, round(h.score, 3)])
        return {"sources": answer_sources([h.chunk_id for h in hits[:1]]), "top5": top5[:5], "fallback": False,
                "seconds": 0.0, "detail": [(h.chunk_id, round(h.score, 3)) for h in hits[:3]]}
    return run


def answer_runner(ctx, retry_pause: float = 0.0):
    from app import advisor
    from app.render import is_system_fallback

    agents = {}

    def run(question: str, language: str) -> dict:
        agent = agents.setdefault(language, advisor.get_agent(ctx, language))
        result, seconds = advisor.answer(agent, question, language)
        fallback = is_system_fallback(result.answer)
        ids = [c.source_id for c in result.answer.citations]
        return {"sources": answer_sources(ids), "fallback": fallback, "seconds": round(seconds, 1),
                "confidence": result.answer.confidence, "answer": result.answer.answer[:600]}
    return run


def run_pairs(pairs, runner, cache: dict, save=lambda c: None, delay: float = 0.0,
              sleep=time.sleep, log=print) -> list[dict]:
    """Run every pair in both languages (skipping runs already in `cache`) and compare them."""
    rows = []
    for p in pairs:
        side = {}
        for lang, key in (("en", "en_question"), ("ar", "ar_question")):
            ck = f"{p['pair']}:{lang}"
            if ck not in cache:
                out = runner(p[key], lang)
                if out["fallback"] and is_daily_limit_error(out.get("answer", "")):
                    raise DailyLimitReached(out.get("answer", ""))
                if not out["fallback"]:           # a failed run is retried next time, not remembered
                    cache[ck] = out
                    save(cache)
                if delay:
                    sleep(delay)
            else:
                out = cache[ck]
            side[lang] = out
            log(f"  {p['pair']} {lang}: {side[lang]['sources'][:1] or '(none)'}"
                + ("  [FALLBACK]" if out["fallback"] else ""))
        rows.append({"pair": p, "en": side["en"], "ar": side["ar"],
                     "verdict": compare(side["en"], side["ar"])})
    return rows


def drop_cached(cache: dict, pair_ids) -> list[str]:
    """Forget the saved runs (both languages) of the given pairs so they are run again; returns the pairs found."""
    found = []
    for pid in pair_ids:
        hit = [k for k in (f"{pid}:en", f"{pid}:ar") if k in cache]
        for k in hit:
            del cache[k]
        if hit:
            found.append(pid)
    return found


def drop_language(cache: dict, language: str) -> int:
    """Forget every saved run of one language ("en" or "ar"); returns how many were dropped."""
    keys = [k for k in cache if k.endswith(f":{language}")]
    for k in keys:
        del cache[k]
    return len(keys)


def read_notes(path=None) -> list[str]:
    path = Path(path or NOTES)
    return [l.strip() for l in path.read_text(encoding="utf-8").splitlines() if l.strip()] if path.exists() else []


def add_note(text: str, path=None) -> None:
    path = Path(path or NOTES)
    if text not in read_notes(path):
        with open(path, "a", encoding="utf-8") as f:
            f.write(text + "\n")


def render_report(rows: list[dict], summary: dict, mode: str, today: str, notes=()) -> str:
    mark = {"same": "same", "different": "DIFFERENT", "error": "ERROR (retry)"}
    lines = [f"# Language parity ({mode} mode, {today})", "",
             f"**{summary['same_top']} of {summary['pairs']} pairs have the same top source** "
             f"(target: at least {summary['target']}). "
             f"{'PASSED' if summary['passed'] else 'NOT PASSED'}."
             + (f" {summary['errors']} pair(s) had an error and count as not passing." if summary["errors"] else ""),
             ]
    if notes:
        lines += ["", "Notes on how this result was produced (re-running only some runs favours the result, "
                      "so read the number with that in mind):"] + [f"- {n}" for n in notes]
    soft = "soft_same" in summary
    if soft:
        lines += ["", f"Softer reading: in **{summary['soft_same']} of {summary['pairs']}** pairs each language's best "
                      "document also appears in the other language's top 5 (the pass rule above is unchanged)."]
    head = "| Pair | Question (EN) | Top source EN | Top source AR | Result |" + (" Top-5 shared |" if soft else "")
    lines += ["", head, "|---|---|---|---|---|" + ("---|" if soft else "")]
    for r in rows:
        p = r["pair"]
        lines.append("| {} | {} | {} | {} | {} |{}".format(
            p["pair"], p["en_question"].replace("|", "/"),
            (r["en"]["sources"][:1] or ["-"])[0], (r["ar"]["sources"][:1] or ["-"])[0],
            mark[r["verdict"]["status"]],
            (" {}/5 |".format(r["verdict"].get("top5_overlap", "-")) if soft else "")))
    diffs = [r for r in rows if r["verdict"]["status"] == "different"]
    if diffs:
        lines += ["", "## Pairs that differ", ""]
        for r in diffs:
            lines += [f"- **{r['pair']['pair']}** {r['pair']['en_question']}",
                      f"  - EN cited: {', '.join(r['en']['sources']) or '-'}",
                      f"  - AR cited: {', '.join(r['ar']['sources']) or '-'}",
                      f"  - cited in both: {', '.join(r['verdict']['shared']) or 'nothing'}"]
            for lang in ("en", "ar"):
                if r[lang].get("top5"):
                    lines.append(f"  - {lang.upper()} top 5: " + ", ".join(f"{d} ({sc})" for d, sc in r[lang]["top5"]))
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Language parity check (issue #26).")
    ap.add_argument("--mode", choices=["retrieval", "answer"], default="retrieval")
    ap.add_argument("--delay", type=float, default=15.0, help="seconds to wait between answer runs")
    ap.add_argument("--fresh", action="store_true", help="ignore saved answer results")
    ap.add_argument("--redo", nargs="+", metavar="PAIR", default=[],
                    help="run these pairs again (e.g. --redo p03 p08 p11); the other saved results are kept")
    ap.add_argument("--redo-lang", choices=["en", "ar"], default=None,
                    help="run every pair of this language again (use after a change that affects that language)")
    args = ap.parse_args(argv)

    from dotenv import load_dotenv

    load_dotenv()
    from app import advisor

    ctx = advisor.get_context()
    pairs = load_pairs()
    if args.mode == "retrieval":
        runner, cache, save, delay = retrieval_runner(ctx), {}, (lambda c: None), 0.0
    else:
        cache = {} if args.fresh or not RESULTS.exists() else json.loads(RESULTS.read_text(encoding="utf-8"))
        save = lambda c: RESULTS.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
        runner, delay = answer_runner(ctx), args.delay
    if args.mode == "answer" and (args.redo or args.redo_lang):
        unknown = [p for p in args.redo if p not in {x["pair"] for x in pairs}]
        if unknown:
            print("Unknown pair(s):", ", ".join(unknown))
            return 2
        if args.redo:
            drop_cached(cache, args.redo)
            add_note(f"Pair(s) {', '.join(args.redo)} were run again after the first full run.")
            print("Running again:", ", ".join(args.redo))
        if args.redo_lang:
            n = drop_language(cache, args.redo_lang)
            add_note(f"All {args.redo_lang.upper()} runs were repeated after the search prompt changed (the search "
                     "query is now always written in English). The other language's runs are from the earlier run. "
                     "The change was made after seeing the 2026-11-24 results.")
            print(f"Running all {n} saved {args.redo_lang.upper()} runs again")
        save(cache)
    print(f"{len(pairs)} pairs, mode={args.mode}")
    try:
        rows = run_pairs(pairs, runner, cache, save=save, delay=delay)
    except DailyLimitReached as e:
        import re

        wait = re.search(r"try again in ([0-9hms.]+)", str(e))
        print("\nGroq's daily token limit is used up. Finished questions are saved "
              f"({len(cache)} of {2 * len(pairs)} runs). Run the same command again later"
              + (f" (Groq says: in {wait.group(1)}, and more may be needed)." if wait else ".")
              + " It continues where it stopped.")
        return 2
    summary = summarize(rows)
    import datetime as dt

    out = REPORT if args.mode == "answer" else REPORT.with_name("parity_report_retrieval.md")
    out.write_text(render_report(rows, summary, args.mode, dt.date.today().isoformat(),
                                    notes=read_notes() if args.mode == "answer" else ()), encoding="utf-8")
    print(f"\n{summary['same_top']}/{summary['pairs']} same top source "
          f"(target {summary['target']}): {'PASSED' if summary['passed'] else 'NOT PASSED'}"
          + (f"  [{summary['errors']} errors - run again to retry them]" if summary["errors"] else ""))
    print(f"report: {out}")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
