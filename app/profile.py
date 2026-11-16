"""Questionnaire answers: cleaning and display. No Streamlit in here, so it is easy to test.

An answers dict maps a question id to its answer:
    single    -> one option id        {"stage": "applying"}
    multi     -> a list of option ids {"needs": ["paying", "deadlines"]}
    free_text -> a short string       {"notes": "..."}
A question that was skipped has no key at all (never an empty value).
"""
from __future__ import annotations

NOTES_MAX_CHARS = 500


def clean_value(question: dict, value):
    """Return a safe value for this question, or None if there is nothing valid to keep."""
    qtype = question["type"]
    valid = [o["id"] for o in question.get("options", [])]

    if qtype == "single":
        return value if value in valid else None

    if qtype == "multi":
        if not isinstance(value, (list, tuple)):
            return None
        kept: list[str] = []
        for v in value:
            if v in valid and v not in kept:
                kept.append(v)
        kept = kept[: question.get("max_choices", len(valid))]
        return kept or None

    if qtype == "free_text":
        if not isinstance(value, str):
            return None
        text = value.strip()[:NOTES_MAX_CHARS]
        return text or None

    return None


def set_answer(answers: dict, question: dict, value) -> dict:
    """Return a new answers dict with this question's answer set (or removed if invalid/empty)."""
    new = dict(answers)
    cleaned = clean_value(question, value)
    if cleaned is None:
        new.pop(question["id"], None)
    else:
        new[question["id"]] = cleaned
    return new


def answered_count(answers: dict) -> int:
    return len(answers)


def describe_answers(strings: dict, answers: dict) -> list[tuple[str, str]]:
    """(question text, readable answer) for every question, in order. Skipped ones say so."""
    q = strings["questionnaire"]
    out = []
    for question in q["questions"]:
        value = answers.get(question["id"])
        if value is None:
            shown = q["skipped"]
        elif question["type"] == "free_text":
            shown = value
        else:
            labels = {o["id"]: o["label"] for o in question["options"]}
            ids = value if isinstance(value, list) else [value]
            shown = ", ".join(labels.get(i, i) for i in ids)
        out.append((question["text"], shown))
    return out
