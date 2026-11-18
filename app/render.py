"""Turn an advisor answer into what the chat page shows: source cards, confidence pill, and a
check for the 'advisor could not answer' fallback. No Streamlit in here, so it is easy to test."""
from __future__ import annotations

import html
import json
import re

CONFIDENCE_COLORS = {  # (text, background)
    "High": ("#3E4B24", "#E1E8CC"),
    "Medium": ("#7A5710", "#F3E6BF"),
    "Low": ("#8A3B2A", "#F2DAD2"),
}
HOURS_UNKNOWN = "not listed; check the page"  # core/tools/programs.py, when a program has no hours
SNIPPET_MAX = 220
FALLBACK_PREFIX = "Something went wrong producing a structured answer"  # core/agent.py _safe_fallback


def is_system_fallback(answer) -> bool:
    """True when core/agent.py returned its safe fallback (a failed or rate-limited call) rather
    than a real answer. The page then shows a friendly message instead of that raw text."""
    return answer.answer.startswith(FALLBACK_PREFIX)


def safe_url(url) -> str:
    """Only plain web links become clickable. Anything else (javascript:, file:, empty) is dropped."""
    url = (url or "").strip()
    return url if url.lower().startswith(("https://", "http://")) else ""


def auto_dir_html(text: str, bold: bool = False, muted: bool = False) -> str:
    """A text block whose direction follows its own first letter, not the page.
    Card text comes from the documents (mostly English) and the page may be right-to-left, so
    without this an English sentence on the Arabic page shows its full stop on the wrong side."""
    inner = html.escape(text or "")
    if bold:
        inner = f"<strong>{inner}</strong>"
    style = "text-align:start;" + ("opacity:0.65;font-size:0.9rem;" if muted else "")
    return f'<div dir="auto" style="{style}">{inner}</div>'


def link_html(url: str) -> str:
    """A clickable link that always reads left to right. A URL shown inside a right-to-left page
    otherwise gets its slashes moved to the wrong end. Returns '' for anything that is not http(s)."""
    url = safe_url(url)
    if not url:
        return ""
    shown, href = html.escape(url), html.escape(url, quote=True)
    return (f'<div dir="ltr" style="text-align:left;word-break:break-all">'
            f'<a href="{href}" target="_blank" rel="noopener noreferrer">{shown}</a></div>')


def isolate_ltr(text: str) -> str:
    """Keep a date or number in its normal left-to-right order inside right-to-left text."""
    return f"\u2066{text}\u2069" if text else ""


def confidence_pill_html(label: str, level: str) -> str:
    fg, bg = CONFIDENCE_COLORS.get(level, CONFIDENCE_COLORS["Low"])
    return (f'<span style="background:{bg};color:{fg};padding:3px 14px;border-radius:999px;'
            f'font-weight:700;font-size:0.9rem">{html.escape(label)}</span>')


def _short(text: str, limit: int = SNIPPET_MAX) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[:limit].rstrip() + " ..."


def _parse(result):
    if isinstance(result, dict):
        return result
    if isinstance(result, str):
        try:
            value = json.loads(result)
        except ValueError:
            return None
        return value if isinstance(value, dict) else None
    return None


def index_sources(tool_calls) -> dict:
    """source_id -> the item a tool returned for it (first one wins)."""
    index: dict = {}
    for call in tool_calls or []:
        data = _parse(call.get("result"))
        for item in (data or {}).get("results") or []:
            if isinstance(item, dict) and item.get("source_id"):
                index.setdefault(item["source_id"], item)
    return index


def kind_of(source_id: str) -> str:
    if source_id.startswith("deadlines:"):
        return "deadline"
    if source_id.startswith("programs:"):
        return "program"
    return "doc" if "::" in source_id else "unknown"


def build_cards(answer, tool_calls) -> list[dict]:
    """One card per cited source, filled from what the tools returned this turn.
    Card keys: source_id, kind, title, detail, snippet, url, retrieved_date, hours."""
    index = index_sources(tool_calls)
    cards, seen = [], set()
    for c in answer.citations:
        if c.source_id in seen:
            continue
        seen.add(c.source_id)
        item = index.get(c.source_id, {})
        kind = kind_of(c.source_id)
        card = {"source_id": c.source_id, "kind": kind, "title": c.label, "detail": "",
                "snippet": "", "url": "", "retrieved_date": "", "hours": ""}
        if kind == "doc":
            card["title"] = item.get("title") or c.label
            card["detail"] = " · ".join(x for x in (item.get("section"), item.get("layer")) if x)
            card["snippet"] = _short(item.get("text", ""))
            card["url"] = safe_url(item.get("source_url"))
            card["retrieved_date"] = item.get("retrieved_date", "")
        elif kind == "deadline":
            card["title"] = item.get("item") or c.label
            card["detail"] = " · ".join(x for x in (item.get("date"), item.get("term")) if x)
            card["snippet"] = _short(item.get("notes", ""))
            card["url"] = safe_url(item.get("source_url"))
            card["retrieved_date"] = item.get("retrieved_date", "")
        elif kind == "program":
            card["title"] = item.get("name") or c.label
            card["detail"] = item.get("contact_office", "")
            card["snippet"] = _short(item.get("description", ""))
            card["url"] = safe_url(item.get("contact_url")) or safe_url(item.get("source_url"))
            card["hours"] = item.get("hours", "")
        cards.append(card)
    return cards


# The model sometimes writes its source ids inside the answer text, e.g. "[source institution-ccc-registration::00]".
# The ids belong on the source cards (answer.citations), so they are removed from the text that is shown.
_ID = r"(?:[A-Za-z0-9_.\-]+::\d+|(?:deadlines|programs|handoffs):[A-Za-z0-9_.\-]+)"
_MARK = (r"\s*[\[\(\u3010\uFF08]\s*(?:(?:sources?|src|\u0627\u0644\u0645\u0635\u062f\u0631|\u0627\u0644\u0645\u0635\u0627\u062f\u0631)\s*:?\s*)?"
         + _ID + r"(?:\s*[,;\u060c\u061b]\s*(?:(?:sources?)\s*:?\s*)?" + _ID + r")*\s*[\]\)\u3011\uFF09]")
CITATION_MARKERS = re.compile(_MARK, re.IGNORECASE)


def strip_citation_markers(text: str) -> str:
    """The text without inline source-id markers. Other bracketed text (a link label such as
    "[ccc.edu/apply]") is left alone, because only ids shaped like a source_id match."""
    return CITATION_MARKERS.sub("", text or "")


def is_daily_limit_fallback(answer) -> bool:
    """The fallback caused by Groq's daily token limit (a retry in a minute will not help)."""
    return is_system_fallback(answer) and "tokens per day" in answer.answer


def assistant_message(result, seconds: float) -> dict:
    """The stored form of one advisor turn (plain data, so it survives Streamlit reruns)."""
    a = result.answer
    return {
        "role": "assistant",
        "fallback": is_system_fallback(a),
        "daily_limit": is_daily_limit_fallback(a),
        "answer": a.answer if is_system_fallback(a) else strip_citation_markers(a.answer),
        "confidence": a.confidence,
        "cards": build_cards(a, result.tool_calls),
        "next_steps": [strip_citation_markers(step) for step in a.next_steps],
        "contact": a.human_contact.model_dump() if a.human_contact else None,
        "seconds": round(seconds, 1),
    }
