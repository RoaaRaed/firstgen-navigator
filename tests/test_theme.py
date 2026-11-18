"""The look: one palette in two places (config.toml and the CSS), and readable colour pairs."""
import re
import tomllib

import pytest

from app import render
from app.theme import PALETTE, theme_css


def _lum(hex_color: str) -> float:
    rgb = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((_lum(a), _lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


@pytest.fixture(scope="module")
def theme():
    return tomllib.load(open(".streamlit/config.toml", "rb"))["theme"]


def test_config_theme_matches_the_palette(theme):
    p = PALETTE
    assert theme["base"] == "light"
    assert theme["backgroundColor"] == p["background"]
    assert theme["secondaryBackgroundColor"] == p["surface_alt"]
    assert theme["textColor"] == p["text"]
    assert theme["primaryColor"] == p["accent"] == theme["linkColor"]
    assert theme["borderColor"] == p["border"]


def test_every_palette_value_is_a_hex_colour():
    assert all(re.fullmatch(r"#[0-9A-Fa-f]{6}", v) for v in PALETTE.values())


@pytest.mark.parametrize("fg,bg,minimum", [
    ("text", "background", 7.0),
    ("text", "surface", 7.0),
    ("muted", "background", 4.5),
    ("accent", "background", 4.5),     # links and code chips
    ("accent", "surface_alt", 4.0),
    ("surface", "accent", 4.5),        # button text on the olive button
    ("surface", "accent_dark", 4.5),   # the same button on hover
])
def test_palette_pairs_are_readable(fg, bg, minimum):
    assert contrast(PALETTE[fg], PALETTE[bg]) >= minimum


@pytest.mark.parametrize("level", ["High", "Medium", "Low"])
def test_confidence_pills_are_readable(level):
    fg, bg = render.CONFIDENCE_COLORS[level]
    assert contrast(fg, bg) >= 4.5


def test_css_uses_the_palette_and_keeps_the_import_first():
    css = theme_css().strip()
    assert css.startswith("@import url(")  # a browser ignores an @import that comes later
    for value in ("background", "accent", "border", "text"):
        assert PALETTE[value] in css
    assert "{{" not in css and "}}" not in css  # no unrendered f-string braces
    assert css.count("{") == css.count("}")
