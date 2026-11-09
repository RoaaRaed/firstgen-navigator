from __future__ import annotations

import re

from core.tools.programs import _program_dict


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")


def resolve_topic(handoffs: dict, topic: str) -> tuple[str, bool]:
    """Return (topic key, matched?). Unknown topics fall back to the default topic."""
    t = _norm(topic)
    for key, cfg in handoffs["topics"].items():
        names = [key] + [_norm(a) for a in cfg.get("aliases", [])]
        if t in names:
            return key, True
    for key, cfg in handoffs["topics"].items():  # partial match, e.g. "financial aid office"
        names = [key] + [_norm(a) for a in cfg.get("aliases", [])]
        if any(n and (n in t or t in n) for n in names):
            return key, True
    return handoffs.get("default", "academic"), False


def escalate_to_human(ctx, topic: str) -> dict:
    """Get the named office a student should talk to. Use it when the question needs a person:
    the student's own eligibility or aid decision, immigration or legal questions, verification,
    a crisis, or anything the documents do not answer. Never give legal advice and never ask
    about immigration status.

    Args:
        topic: one of financial_aid, state_aid, immigration, academic, transfer, wellness,
            food, snap, childcare, disability (other words are matched to the closest topic).

    Returns: {"topic", "matched", "sensitive", "contacts": [...]}. Each contact has a
    "source_id" such as "programs:ccc-financial-aid-offices" (cite it exactly), the office,
    link, phone and hours. If "sensitive" is true, use a gentle tone.
    """
    key, matched = resolve_topic(ctx.handoffs, topic)
    cfg = ctx.handoffs["topics"][key]
    contacts = []
    for pid in [cfg["program"]] + ([cfg["also"]] if cfg.get("also") else []):
        p = ctx.program(pid)
        if p is not None:
            contacts.append(_program_dict(p))
    return {"topic": key, "matched": matched, "asked_for": topic,
            "sensitive": bool(cfg.get("sensitive")), "contacts": contacts}
