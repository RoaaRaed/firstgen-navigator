"""Build the student's plan from their questionnaire answers. No Streamlit in here.

The plan is assembled only from things already in the project's files, never written by the
model: next steps from rules.yaml, dates from deadlines.csv, offices and programs from
programs.csv (and handoffs.yaml), so every line can be traced to a file.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from app.student_answers import answered_rows
from core.rules import match_rules
from core.tools.escalate import escalate_to_human
from core.tools.programs import match_programs

MAX_DEADLINES = 6
MAX_PROGRAMS = 6
ALL_AUDIENCES = {"applying", "enrolled", "transfer", "all"}
# The plan is a paper the student may print or share, so it never lists immigration-related
# programs, even when a rule ranks them: the questionnaire does not ask about status and the
# plan must not hint at it. The chat can still talk about them if the student asks.
PRIVATE_CATEGORIES = {"immigrant_services"}
STAGE_AUDIENCE = {"thinking": "applying", "applying": "applying", "first_year": "enrolled",
                  "returning": "enrolled", "transfer": "transfer"}


@dataclass
class Plan:
    lang: str
    institution_name: str
    prepared_on: str                                       # ISO date
    about: list = field(default_factory=list)              # [(question, answer)], answered only
    steps: list = field(default_factory=list)              # [str], in the plan's language
    deadlines: list = field(default_factory=list)          # [{id, item, date, term, url}]
    programs: list = field(default_factory=list)           # [{id, name, office, phone, url, hours}]
    contacts: list = field(default_factory=list)           # same shape as programs
    matched_rules: list = field(default_factory=list)      # rule ids, most important first


def format_date(iso: str, lang: str) -> str:
    """The date as shown inside running text. Arabic uses 2026/11/16: a date with hyphens after
    Arabic words gets its numbers reversed by the bidi rules (16-11-2026), slashes stay in order."""
    return iso.replace("-", "/") if lang == "ar" else iso


def _dedupe(items):
    seen, out = set(), []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _program_entry(p) -> dict:
    return {"id": p.id, "name": p.name, "office": p.contact_office,
            "phone": p.contact_phone or "", "url": p.contact_url or p.source_url or "",
            "hours": p.hours or ""}


def build_plan(ctx, ruleset, strings: dict, answers: dict, lang: str,
               institution_name: str, today: dt.date | None = None) -> Plan:
    today = today or ctx.today
    matched = match_rules(ruleset, answers)

    steps = _dedupe(getattr(step, lang) for r in matched for step in r.next_steps)

    audiences = {a for r in matched for a in r.prefer_deadline_audiences}
    stage = STAGE_AUDIENCE.get(answers.get("stage"))
    if stage:
        audiences.add(stage)
    audiences = (audiences | {"all"}) if audiences else set(ALL_AUDIENCES)
    upcoming = sorted((d for d in ctx.deadlines if d.applies_to in audiences and d.date >= today),
                      key=lambda d: (d.date, d.id))
    deadlines = [{"id": d.id, "item": d.item, "date": d.date.isoformat(), "term": d.term,
                  "url": d.source_url} for d in upcoming[:MAX_DEADLINES]]

    tags = _dedupe(["first_gen"] + [t for r in matched for t in r.add_profile_tags])
    categories = _dedupe(c for r in matched for c in r.prefer_program_categories
                         if c not in PRIVATE_CATEGORIES)
    found = match_programs(ctx, tags=tags, categories=categories, limit=MAX_PROGRAMS + 6)["results"]
    rows = [ctx.program(item["source_id"].split(":", 1)[1]) for item in found]
    programs = [_program_entry(p) for p in rows
                if p is not None and p.category not in PRIVATE_CATEGORIES][:MAX_PROGRAMS]

    contacts, seen = [], set()
    for rule in matched:
        if rule.handoff is None:
            continue
        for c in escalate_to_human(ctx, rule.handoff.topic)["contacts"]:
            pid = c["source_id"].split(":", 1)[1]
            row = ctx.program(pid)
            if row is not None and pid not in seen and row.category not in PRIVATE_CATEGORIES:
                seen.add(pid)
                contacts.append(_program_entry(row))

    return Plan(lang=lang, institution_name=institution_name, prepared_on=today.isoformat(),
                about=answered_rows(strings, answers), steps=steps, deadlines=deadlines,
                programs=programs, contacts=contacts, matched_rules=[r.id for r in matched])
