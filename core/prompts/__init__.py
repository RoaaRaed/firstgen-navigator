"""Load the bilingual system prompt.

    from core.prompts import load_system_prompt
    prompt = load_system_prompt("en", institution_name="City Colleges of Chicago")
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).parent
LANGUAGES = ("en", "ar")


def load_system_prompt(language: str = "en", institution_name: str = "the college") -> str:
    if language not in LANGUAGES:
        raise ValueError(f"language must be one of {LANGUAGES}, got {language!r}")
    text = (HERE / f"system_{language}.md").read_text(encoding="utf-8")
    return text.format(institution_name=institution_name)
