"""Interface text and right-to-left (RTL) styling. No Streamlit in here, so it is easy to test.

All visible text lives in app/i18n/<lang>.json (brief section 4.3); this file only loads it.
"""
from __future__ import annotations

import json
from pathlib import Path

I18N_DIR = Path(__file__).parent / "i18n"
LANGUAGES = {"en": "English", "ar": "العربية"}
RTL_LANGUAGES = {"ar"}
DEFAULT_LANGUAGE = "en"


def normalize(lang: str | None) -> str:
    """Unknown or missing language falls back to English."""
    return lang if lang in LANGUAGES else DEFAULT_LANGUAGE


def load_strings(lang: str) -> dict:
    path = I18N_DIR / f"{normalize(lang)}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def is_rtl(lang: str) -> bool:
    return normalize(lang) in RTL_LANGUAGES


def text_direction(lang: str) -> str:
    return "rtl" if is_rtl(lang) else "ltr"


def t(strings: dict, key: str, **values) -> str:
    """Look up 'buttons.start' style keys. A missing key returns the key itself, so a gap
    in a translation is visible on screen instead of crashing the app."""
    node = strings
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return key
        node = node[part]
    return node.format(**values) if isinstance(node, str) and values else node


def page_css(lang: str) -> str:
    """CSS for the page. Arabic gets right-to-left direction, right-aligned text and an
    Arabic-friendly font. English gets nothing extra."""
    if not is_rtl(lang):
        return ""
    return """
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Arabic:wght@400;600;700&display=swap');
html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"], .stApp {
    direction: rtl;
    font-family: 'Noto Sans Arabic', 'Segoe UI', Tahoma, sans-serif;
}
.stMarkdown, .stMarkdown p, h1, h2, h3, label, p, li,
[data-testid="stAlert"], [data-testid="stWidgetLabel"] {
    text-align: right;
    direction: rtl;
}
[data-testid="stHorizontalBlock"] { flex-direction: row-reverse; }
"""
