"""The short text the MODEL reads for each tool result.

Each tool returns a full dict (links, scores, retrieval dates...). The page needs all of it to
draw the source cards, but the model needs far less, and every token counts: the free Groq tier
allows 8000 tokens per request-minute, and an Arabic question that needs two searches went over
it ("Request too large", 413). The agent therefore hands the model this compact text and keeps
the full dict as the tool message's artifact (see core/agent.py).

What the model keeps: the source_id (it must cite it exactly), the section it came from, the
layer, the retrieval date and effective term (it must prefer newer documents), the text, and the
dates/phones/hours it may quote. What it does not get: URLs, scores, echoes of its own query.
"""
from __future__ import annotations

import json


def _clip(text, limit: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[:limit].rstrip() + " ..."


def _head(title: str, section: str) -> str:
    """The sections already start with the document title ("Title > Heading"); do not repeat it."""
    if section and (not title or title in section):
        return section
    return f"{title} > {section}" if section else title


def _nothing(result: dict) -> str:
    bits = ["found: none"]
    for key in ("error", "message"):
        if result.get(key):
            bits.append(str(result[key]))
    for key in ("available_terms", "valid_tags", "valid_categories", "ignored"):
        if result.get(key):
            bits.append(f"{key}: {', '.join(map(str, result[key]))}")
    return ". ".join(bits)


def compact_search(result: dict) -> str:
    rows = result.get("results") or []
    if not rows:
        return _nothing(result)
    lines = []
    for r in rows:
        meta = f"{r.get('layer', '')}; retrieved {r.get('retrieved_date', '')}; term: {r.get('effective_term', '')}"
        lines.append(f"[{r['source_id']}] {_head(r.get('title', ''), r.get('section', ''))} ({meta}): {r.get('text', '')}")
    return "\n".join(lines)


def compact_deadlines(result: dict) -> str:
    rows = result.get("results") or []
    if not rows:
        return _nothing(result)
    lines = [f"today: {result.get('today', '')}"]
    for r in rows:
        when = "PAST" if r.get("is_past") else "upcoming"
        note = f" | {_clip(r['notes'], 140)}" if r.get("notes") else ""
        lines.append(f"[{r['source_id']}] {r.get('date', '')} ({when}) | {r.get('term', '')} | "
                     f"{r.get('item', '')} | {r.get('layer', '')}; for {r.get('applies_to', '')}{note}")
    return "\n".join(lines)


def _program_line(r: dict) -> str:
    tags = r.get("for") or []
    who = ", ".join(tags) if isinstance(tags, list) else str(tags)
    hours = r.get("hours") or ""
    extra = [f"phone: {r['contact_phone']}"] if r.get("contact_phone") else []
    extra += [f"hours: {hours}"] if hours and not hours.startswith("not listed") else []
    extra += [f"office: {r['contact_office']}"] if r.get("contact_office") else []
    meta = "; ".join([str(r.get("category", "")), f"for: {who}"] + extra)
    return f"[{r['source_id']}] {r.get('name', '')} ({meta}): {_clip(r.get('description', ''), 240)}"


def compact_programs(result: dict) -> str:
    rows = result.get("results") or []
    return "\n".join(_program_line(r) for r in rows) if rows else _nothing(result)


def compact_escalate(result: dict) -> str:
    head = (f"topic: {result.get('topic', '')}; matched: {str(result.get('matched')).lower()}; "
            f"sensitive: {str(result.get('sensitive')).lower()}")
    contacts = result.get("contacts") or []
    return "\n".join([head] + [_program_line(c) for c in contacts])


COMPACTORS = {
    "search_knowledge_base": compact_search,
    "lookup_deadlines": compact_deadlines,
    "match_programs": compact_programs,
    "escalate_to_human": compact_escalate,
}


def for_model(tool_name: str, result: dict) -> str:
    """The text the model reads for this tool's result. Never raises: an odd result falls back
    to compact JSON, so a formatting problem cannot break an answer."""
    try:
        return COMPACTORS[tool_name](result)
    except Exception:
        return json.dumps(result, ensure_ascii=False, separators=(",", ":"))
