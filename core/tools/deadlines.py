from __future__ import annotations

import re

# A student says "drop", the table says "withdrawal". Keep this list small and obvious.
SYNONYMS = {
    "drop": ["withdrawal", "withdraw"],
    "withdraw": ["withdrawal"],
    "start": ["first day", "begin"],
    "starts": ["first day", "begin"],
    "begin": ["first day", "begin"],
    "register": ["registration"],
    "enroll": ["registration"],
    "end": ["ends", "last day of classes"],
    "ends": ["ends", "last day of classes"],
    "tuition": ["rates"],
    "cost": ["rates"],
    "alternative": ["alternative application"],
    "court": ["court ruling"],
    "ruling": ["court ruling"],
}
STOP = {"the", "a", "an", "of", "for", "to", "is", "when", "what", "date", "deadline",
        "deadlines", "day", "last", "my", "i", "do", "does", "and", "in", "on"}


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if t not in STOP]


def _term_matches(wanted: str, row_term: str) -> bool:
    w, r = " ".join(_tokens(wanted)), " ".join(_tokens(row_term))
    return bool(w) and (w in r or r in w)


def lookup_deadlines(ctx, term: str = "", topic: str = "") -> dict:
    """Look up exact dates from the official deadlines table (federal FAFSA, Illinois MAP and
    Alternative Application, and college registration, withdrawal and term dates). Use it
    whenever the student asks "when" or about a deadline. Never state a date that this tool
    did not return.

    Args:
        term: optional term or aid year, for example "Spring 2027", "Fall 2026", "2026-27".
        topic: optional words in English, for example "withdrawal", "first day", "FAFSA",
            "MAP", "alternative application", "registration", "tuition rates".

    Returns: {"found": bool, "today": ..., "results": [...]}. Each result has a "source_id"
    such as "deadlines:ccc-spring27-first-day-16wk" (cite it exactly), the date, term, item,
    who it applies to, "is_past" (the date is before today), notes and source_url.
    """
    rows = list(ctx.deadlines)
    if term.strip():
        rows = [r for r in rows if _term_matches(term, r.term)]
        if not rows:
            return {"found": False, "today": ctx.today.isoformat(),
                    "message": f"No deadlines for term '{term}'.",
                    "available_terms": sorted({r.term for r in ctx.deadlines}), "results": []}

    words = _tokens(topic)
    scored = []
    for r in rows:
        hay = f"{r.id} {r.item} {r.notes or ''}".lower().replace("-", " ")
        score = 0
        for w in words:
            options = [w] + SYNONYMS.get(w, [])
            if any(o in hay for o in options):
                score += 1
        if not words or score:
            scored.append((score, r))
    # best match first; among equals, upcoming dates before past ones, then soonest first
    scored.sort(key=lambda x: (-x[0], x[1].date < ctx.today, x[1].date))

    results = [{
        "source_id": f"deadlines:{r.id}",
        "item": r.item,
        "date": r.date.isoformat(),
        "term": r.term,
        "layer": r.layer,
        "applies_to": r.applies_to,
        "is_past": r.date < ctx.today,
        "notes": r.notes or "",
        "source_url": r.source_url,
        "retrieved_date": r.retrieved_date.isoformat(),
    } for _, r in scored[:10]]
    out = {"found": bool(results), "today": ctx.today.isoformat(), "results": results}
    if not results:
        out["message"] = f"No deadline matches topic '{topic}'. Say the date was not found."
    return out
