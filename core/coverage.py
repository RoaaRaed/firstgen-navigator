"""Knowledge Base Coverage Report (brief section 4, "Admin page").

It answers two questions an institution cares about:
  1. Which of the questions students are likely to ask can the knowledge base NOT answer?
  2. Which documents are older than a chosen age?

It runs the institution's golden question set against the CURRENT documents using search only
(local embeddings, no LLM calls), so it is free and fast and can be run after every upload.
That makes it a coverage check, not an answer-quality check: the evaluation harness
(evals/run_eval.py) is the one that judges the advisor's answers.

For each answerable question (expected_behavior grounded or partial):
  - gap          none of its expected sources exists any more (a document is missing), or, for a
                 question with no expected sources, the best search result scores below MIN_SCORE
  - weak         an expected document exists but search did not bring it back in the top results
  - covered      an expected source was found (or the best score was high enough)
Questions that are SUPPOSED to be refused or not found are left out.

Not included on purpose: "most asked questions". That needs a log of what students type, and this
project stores none (the app has no logging; see tests/test_privacy.py).
"""
from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

ANSWERABLE = ("grounded", "partial")
DEFAULT_MAX_AGE_DAYS = 180
DEFAULT_TOP_K = 5
MIN_SCORE = 0.75      # only used for a question with no expected sources


def load_questions(path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _base(source_id: str) -> str:
    return source_id.split("::")[0]


def table_ids(root) -> set[str]:
    """'deadlines:<id>' and 'programs:<id>' for every row of the two tables."""
    from core.tables import load_deadlines, load_programs

    root = Path(root)
    ids = set()
    for name, loader in (("deadlines", load_deadlines), ("programs", load_programs)):
        path = root / f"{name}.csv"
        if path.exists():
            ids |= {f"{name}:{r.id}" for r in loader(path)}
    return ids


def stale_documents(root, max_age_days: int = DEFAULT_MAX_AGE_DAYS, today: dt.date | None = None) -> list[dict]:
    """Documents whose retrieved_date is older than max_age_days, oldest first."""
    from core.admin import list_documents

    today = today or dt.date.today()
    out = []
    for d in list_documents(root):
        if d["retrieved_date"] is None:
            continue
        age = (today - d["retrieved_date"]).days
        if age > max_age_days:
            out.append({"id": d["id"], "title": d["title"], "retrieved_date": d["retrieved_date"].isoformat(),
                        "age_days": age})
    return sorted(out, key=lambda r: -r["age_days"])


def check_question(row: dict, retriever, doc_ids: set[str], tables: set[str],
                   k: int = DEFAULT_TOP_K, min_score: float = MIN_SCORE) -> dict:
    expected = [e.strip() for e in (row.get("expected_source_ids") or "").split(";") if e.strip()]
    hits = retriever.search(row["question"], k=k)
    found_docs = {h.doc_id for h in hits}
    best = max((h.score for h in hits), default=0.0)
    result = {"id": row["id"], "language": row["language"], "question": row["question"],
              "best_score": round(best, 2), "expected": expected}
    if expected:
        present = [e for e in expected if (e in tables) or (_base(e) in doc_ids)]
        if not present:
            result.update(status="gap", reason="none of the expected sources exists in the knowledge base")
        else:
            doc_present = [e for e in present if e not in tables]
            if any(_base(e) in found_docs for e in doc_present) or any(e in tables for e in present):
                result.update(status="covered", reason="")
            else:
                result.update(status="weak", reason="the expected document exists but search did not return it")
    elif best >= min_score:
        result.update(status="covered", reason="")
    else:
        result.update(status="gap", reason=f"best search score {best:.2f} is below {min_score}")
    return result


def build_report(root, retriever, questions: list[dict] | None = None,
                 max_age_days: int = DEFAULT_MAX_AGE_DAYS, today: dt.date | None = None,
                 k: int = DEFAULT_TOP_K) -> dict:
    from core.admin import list_documents

    root = Path(root)
    today = today or dt.date.today()
    if questions is None:
        questions = load_questions(root / "golden_questions.csv")
    doc_ids = {d["id"] for d in list_documents(root)}
    tables = table_ids(root)
    rows = [check_question(q, retriever, doc_ids, tables, k=k)
            for q in questions if q["expected_behavior"] in ANSWERABLE]
    counts = {s: sum(1 for r in rows if r["status"] == s) for s in ("covered", "weak", "gap")}
    by_language = {}
    for lang in sorted({r["language"] for r in rows}):
        sub = [r for r in rows if r["language"] == lang]
        by_language[lang] = {"questions": len(sub), "covered": sum(1 for r in sub if r["status"] == "covered")}
    return {
        "institution": root.name, "date": today.isoformat(), "max_age_days": max_age_days,
        "documents": len(doc_ids), "questions": len(rows), **counts,
        "by_language": by_language,
        "problems": [r for r in rows if r["status"] != "covered"],
        "stale": stale_documents(root, max_age_days, today),
    }


def render_markdown(report: dict) -> str:
    n = report["questions"]
    pct = f"{100 * report['covered'] / n:.0f}%" if n else "-"
    lines = [
        f"# Knowledge Base Coverage Report: {report['institution']}",
        "",
        f"Date: {report['date']}. Documents: {report['documents']}. "
        f"Answerable test questions: {n}.",
        "",
        "## Summary",
        "",
        "| | Count |",
        "|---|---|",
        f"| Covered (the knowledge base can answer it) | {report['covered']} ({pct}) |",
        f"| Weak (the document exists but search missed it) | {report['weak']} |",
        f"| Gap (no source for it) | {report['gap']} |",
        f"| Documents older than {report['max_age_days']} days | {len(report['stale'])} |",
        "",
    ]
    if report["by_language"]:
        lines += ["| Language | Questions | Covered |", "|---|---|---|"]
        lines += [f"| {lang} | {v['questions']} | {v['covered']} |" for lang, v in report["by_language"].items()]
        lines.append("")
    lines += ["## Questions the knowledge base cannot answer well", ""]
    if report["problems"]:
        lines += ["| Status | Question | Why | Expected source |", "|---|---|---|---|"]
        lines += [f"| {r['status']} | {r['question'][:110]} ({r['id']}) | {r['reason']} | "
                  f"{', '.join(r['expected']) or '-'} |" for r in report["problems"]]
    else:
        lines.append("None. Every test question has a source.")
    lines += ["", f"## Documents older than {report['max_age_days']} days", ""]
    if report["stale"]:
        lines += ["| Document | Retrieved | Age (days) |", "|---|---|---|"]
        lines += [f"| {r['title']} ({r['id']}) | {r['retrieved_date']} | {r['age_days']} |" for r in report["stale"]]
    else:
        lines.append("None.")
    lines += ["", "## How to read this", "",
              "This is a coverage check: it uses search only and does not judge the wording of answers. "
              "A question marked weak or gap is a place where a student would likely get no answer or a poor one. "
              "The fix is usually a missing or outdated document. "
              "Most-asked questions are not reported because this app stores no record of student questions."]
    return "\n".join(lines) + "\n"
