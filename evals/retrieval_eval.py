"""Gate 1 measurement: for every golden question, is the expected source in the top 5?

    python -m evals.retrieval_eval                  # prints the summary, writes evals/retrieval_report.md
    python -m evals.retrieval_eval --k 5 --out evals/retrieval_report.md

Only knowledge-base documents are scored. Rows that expect only a table row
(deadlines:... / programs:...) are not retrieval questions, and refuse / not_found
rows have no source to find. Those rows are used only to study the threshold.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
from dataclasses import dataclass, field
from pathlib import Path

GATE_EN = 0.80
GATE_AR = 0.70
THRESHOLDS = (0.0, 0.80, 0.82, 0.84, 0.85, 0.86, 0.87, 0.88, 0.90)
ANSWERABLE = ("grounded", "partial")
UNANSWERABLE = ("not_found", "refuse")


@dataclass
class Result:
    qid: str
    language: str
    behavior: str
    question: str
    expected: set            # KB document ids that would answer it
    ranked: list             # [(doc_id, score)] for the top chunks, best first
    rank: int | None = None  # 1-based position of the first expected chunk (None = missing)
    top_score: float = 0.0

    @property
    def scored(self) -> bool:
        return self.behavior in ANSWERABLE and bool(self.expected)


def load_golden(path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def kb_ids(row: dict) -> set:
    """Expected KB document ids. 'deadlines:..' and 'programs:..' come from tables, not retrieval."""
    ids = (row.get("expected_source_ids") or "").split(";")
    return {i.strip() for i in ids if i.strip() and ":" not in i}


class LayeredRetriever:
    """Strategy 'layered': guarantee the best chunk of each layer a place at the top.

    A question like "I cannot file the FAFSA, is there state aid?" shares many words with
    federal documents, so they can crowd out the state documents. Here the best federal,
    state and institution chunk come first (ordered by score), then everything else by score.
    """

    LAYERS = ("federal", "state", "institution")

    def __init__(self, inner):
        self.inner = inner

    def search(self, query, k=5, threshold=None, **kw):
        per_layer = {L: self.inner.search(query, k=k, layer=L, threshold=0.0) for L in self.LAYERS}
        firsts = [hits[0] for hits in per_layer.values() if hits]
        firsts.sort(key=lambda h: -h.score)
        seen = {h.chunk_id for h in firsts}
        rest = sorted((h for hits in per_layer.values() for h in hits if h.chunk_id not in seen),
                      key=lambda h: -h.score)
        merged = firsts + rest
        if threshold:
            merged = [h for h in merged if h.score >= threshold]
        return merged[:k]


def evaluate(rows: list[dict], retriever, k: int = 5, depth: int = 10) -> list[Result]:
    """Search `depth` chunks per question so near misses (rank 6-10) are visible too."""
    results = []
    for row in rows:
        hits = retriever.search(row["question"], k=max(k, depth), threshold=0.0)
        ranked = [(h.doc_id, h.score) for h in hits]
        expected = kb_ids(row)
        rank = next((i for i, (d, _) in enumerate(ranked, 1) if d in expected), None)
        results.append(Result(
            qid=row["id"], language=row["language"], behavior=row["expected_behavior"],
            question=row["question"], expected=expected, ranked=ranked, rank=rank,
            top_score=ranked[0][1] if ranked else 0.0,
        ))
    return results


def hit_rate(results: list[Result], language: str, k: int = 5) -> tuple[int, int]:
    pool = [r for r in results if r.scored and r.language == language]
    return sum(1 for r in pool if r.rank is not None and r.rank <= k), len(pool)


def gate_verdict(results: list[Result], k: int = 5) -> dict:
    out = {}
    for lang, need in (("en", GATE_EN), ("ar", GATE_AR)):
        hits, n = hit_rate(results, lang, k)
        rate = hits / n if n else 0.0
        out[lang] = {"hits": hits, "n": n, "rate": rate, "need": need, "pass": n > 0 and rate >= need}
    out["pass"] = out["en"]["pass"] and out["ar"]["pass"]
    return out


def threshold_table(results: list[Result], k: int = 5, thresholds=THRESHOLDS) -> list[dict]:
    """For each threshold: answerable hits kept, and unanswerable questions correctly left empty."""
    rows = []
    for t in thresholds:
        entry = {"threshold": t}
        for lang in ("en", "ar"):
            pool = [r for r in results if r.scored and r.language == lang]
            kept = sum(1 for r in pool if any(
                d in r.expected and s >= t for d, s in r.ranked[:k]))
            entry[lang] = (kept, len(pool))
        un = [r for r in results if r.behavior in UNANSWERABLE]
        entry["empty"] = (sum(1 for r in un if not any(s >= t for _, s in r.ranked[:k])), len(un))
        rows.append(entry)
    return rows


def _pct(a: int, b: int) -> str:
    return f"{a}/{b} = {100 * a / b:.0f}%" if b else "n/a"


def render_report(results: list[Result], embedder_name: str, k: int = 5,
                  chunk_info: str = "", strategy: str = "plain") -> str:
    v = gate_verdict(results, k)
    skipped = [r for r in results if r.behavior in ANSWERABLE and not r.expected]
    lines = [
        "# Retrieval report (Gate 1)",
        "",
        f"Generated: {dt.date.today().isoformat()} | Embedding model: `{embedder_name}` | "
        f"Top-{k} chunks, no threshold, strategy: {strategy}" + (f" | {chunk_info}" if chunk_info else ""),
        "",
        f"**Gate 1 {'PASS' if v['pass'] else 'NOT YET'}**: "
        f"English {_pct(v['en']['hits'], v['en']['n'])} (need {GATE_EN:.0%}), "
        f"Arabic {_pct(v['ar']['hits'], v['ar']['n'])} (need {GATE_AR:.0%}).",
        "",
        "A question counts as a hit when at least one of the top-5 chunks comes from a document "
        "listed in `expected_source_ids` of `golden_questions.csv`. Only knowledge-base documents "
        "are scored. Table rows (`deadlines:`, `programs:`) are answered by tools, not retrieval.",
        "",
        "## Per question",
        "",
        "| id | lang | behavior | rank | top score | expected | top 3 documents |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        if r.scored:
            rank = str(r.rank) if r.rank and r.rank <= k else (f"miss (rank {r.rank})" if r.rank else "miss")
        else:
            rank = "-"
        top3 = ", ".join(list(dict.fromkeys(d for d, _ in r.ranked[:5]))[:3])
        exp = ", ".join(sorted(r.expected)) or "(none)"
        lines.append(f"| {r.qid} | {r.language} | {r.behavior} | {rank} | {r.top_score:.3f} | {exp} | {top3} |")

    misses = [r for r in results if r.scored and (r.rank is None or r.rank > k)]
    lines += ["", "## Misses", ""]
    if not misses:
        lines.append("None.")
    for r in misses:
        lines += [f"- **{r.qid}** ({r.language}): {r.question}",
                  f"  - expected: {', '.join(sorted(r.expected))}",
                  f"  - got: {', '.join(dict.fromkeys(d for d, _ in r.ranked[:k]))}"]

    lines += ["", "## Threshold study", "",
              "Each cell: questions that still have the right document in the top 5 after dropping "
              "chunks below the threshold. 'Left empty' = refuse / not_found questions that return "
              "nothing (that is what we want for them).", "",
              "| threshold | English kept | Arabic kept | refuse / not_found left empty |",
              "|---|---|---|---|"]
    for e in threshold_table(results, k):
        lines.append(f"| {e['threshold']:.2f} | {_pct(*e['en'])} | {_pct(*e['ar'])} | {_pct(*e['empty'])} |")

    lines += ["", "## Notes", ""]
    if skipped:
        lines.append("- Not scored (answered from tables only): " + ", ".join(r.qid for r in skipped) + ".")
    lines.append("- Arabic has few questions (10), so one question moves the rate by 10 points.")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Measure top-k retrieval hit rate on the golden set.")
    ap.add_argument("--golden", default="institutions/demo-ccc/golden_questions.csv")
    ap.add_argument("--institution", default="demo-ccc")
    ap.add_argument("--db", default="chroma_db")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--out", default="evals/retrieval_report.md")
    ap.add_argument("--strategy", choices=("plain", "layered"), default="plain",
                    help="plain = one search; layered = best chunk of each layer first")
    args = ap.parse_args(argv)

    from core.ingest import MAX_CHARS, MIN_CHARS
    from core.retriever import load_retriever

    retriever = load_retriever(args.institution, args.db)
    searcher = LayeredRetriever(retriever) if args.strategy == "layered" else retriever
    results = evaluate(load_golden(args.golden), searcher, k=args.k)
    report = render_report(results, retriever.embedder.name, args.k,
                           chunk_info=f"chunks {MIN_CHARS}-{MAX_CHARS} chars", strategy=args.strategy)
    Path(args.out).write_text(report, encoding="utf-8")

    v = gate_verdict(results, args.k)
    for lang, name in (("en", "English"), ("ar", "Arabic")):
        g = v[lang]
        print(f"{name}: {g['hits']}/{g['n']} = {g['rate']:.0%}  (need {g['need']:.0%})  "
              f"{'PASS' if g['pass'] else 'below target'}")
    misses = [r.qid for r in results if r.scored and (r.rank is None or r.rank > args.k)]
    print("Misses:", ", ".join(misses) or "none")
    print(f"Strategy: {args.strategy}")
    print(f"Gate 1: {'PASS' if v['pass'] else 'NOT YET'}   report -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
