from __future__ import annotations

import re
from typing import get_args

from core.tables import Category, Tag

TAGS = set(get_args(Tag))
CATEGORIES = set(get_args(Category))


def _program_dict(p) -> dict:
    return {
        "source_id": f"programs:{p.id}",
        "name": p.name,
        "category": p.category,
        "for": p.eligibility_tags or ["all students"],
        "description": p.description,
        "contact_office": p.contact_office,
        "contact_url": p.contact_url or "",
        "contact_phone": p.contact_phone or "",
        "hours": p.hours or "not listed; check the page",
        "languages": p.language_support,
        "source_url": p.source_url,
        "retrieved_date": p.retrieved_date.isoformat(),
    }


def match_programs(ctx, tags: list[str] | None = None, categories: list[str] | None = None,
                   keywords: str = "", limit: int = 6) -> dict:
    """Find support programs and offices that fit the student's situation (aid, food, child
    care, immigrant services, ESL, transfer, wellness, disability, academic help).

    Args:
        tags: the student's profile tags, any of: first_gen, working_20plus, working_30plus,
            caregiver, fafsa_ineligible_or_unsure, esl, transfer.
        categories: kinds of help, any of: financial, academic, wellness, transfer,
            immigrant_services, childcare, food, disability.
        keywords: optional English words, for example "food pantry" or "laptop".

    Returns: {"found": bool, "results": [...]}. Each result has a "source_id" such as
    "programs:ccc-food-pantries" (cite it exactly), name, description, who it is for, contact
    office, link, phone and hours. Only recommend programs that this tool returned.
    """
    tags = [t.strip() for t in (tags or []) if t and t.strip()]
    categories = [c.strip() for c in (categories or []) if c and c.strip()]
    ignored = [t for t in tags if t not in TAGS] + [c for c in categories if c not in CATEGORIES]
    tags = [t for t in tags if t in TAGS]
    categories = [c for c in categories if c in CATEGORIES]
    words = [w for w in re.findall(r"[a-z0-9]+", keywords.lower()) if len(w) > 2]
    if not (tags or categories or words):
        return {"found": False, "ignored": ignored, "results": [],
                "message": "Give at least one valid tag, category or keyword.",
                "valid_tags": sorted(TAGS), "valid_categories": sorted(CATEGORIES)}

    scored = []
    for p in ctx.programs:
        score = 3 * len(set(tags) & set(p.eligibility_tags))
        score += 2 if p.category in categories else 0
        hay = f"{p.name} {p.description}".lower()
        score += sum(1 for w in words if w in hay)
        if score:
            scored.append((score, p))
    scored.sort(key=lambda x: (-x[0], x[1].id))
    results = [_program_dict(p) for _, p in scored[:limit]]
    out = {"found": bool(results), "results": results}
    if ignored:
        out["ignored"] = ignored
    return out
