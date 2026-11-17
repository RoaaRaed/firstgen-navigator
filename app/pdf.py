"""My Plan as a PDF (reportlab). No Streamlit in here.

Arabic needs two extra steps that English does not:
  1. shaping  - Arabic letters change shape depending on their neighbours (arabic-reshaper);
  2. ordering - the line is drawn left to right on the page, so an Arabic line has to be
                reordered visually first (python-bidi).
Both must happen on each finished *line*, after we have wrapped the text ourselves, which is
why this file draws lines directly instead of using reportlab's Paragraph.

The fonts (DejaVu Sans, free licence) live in app/assets/fonts so the PDF looks the same on
every computer, including Streamlit Community Cloud.
"""
from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

FONT_DIR = Path(__file__).parent / "assets" / "fonts"
REG, BOLD = "FGN-Sans", "FGN-Sans-Bold"
INK, MUTED, ACCENT, LINK = HexColor("#181c2b"), HexColor("#555c74"), HexColor("#09707f"), HexColor("#1f5fd1")
_ARABIC = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")
FOOTER_H = 20 * mm


def has_arabic(text: str) -> bool:
    return bool(_ARABIC.search(text or ""))


@dataclass
class Shaper:
    """width_text: the text as it will look (for measuring). display: what to draw on a line."""
    width_text: Callable[[str], str]
    display: Callable[[str, bool], str]


def _load_arabic_tools():
    """(reshape, get_display) from the two Arabic packages. Raises RuntimeError if missing."""
    try:
        import arabic_reshaper
        try:
            from bidi import get_display
        except ImportError:  # older python-bidi versions
            from bidi.algorithm import get_display
    except ImportError as e:
        raise RuntimeError("The Arabic PDF needs two small packages. Run: "
                           "pip install arabic-reshaper python-bidi") from e
    return arabic_reshaper.reshape, get_display


_SWAP = str.maketrans("()[]{}<>\u00ab\u00bb", ")(][}{><\u00bb\u00ab")
_BRACKETS = set("()[]{}<>\u00ab\u00bb")


def _char_directions(text: str) -> list:
    """'L', 'R' or None (neutral) for each character, following the Unicode bidi rules closely
    enough for brackets: numbers count as R, except after left-to-right letters."""
    dirs, last = [], None
    for ch in text:
        kind = unicodedata.bidirectional(ch)
        if kind == "L":
            d, last = "L", "L"
        elif kind in ("R", "AL"):
            d, last = "R", "R"
        elif kind == "AN":
            d = "R"
        elif kind == "EN":
            d = "L" if last == "L" else "R"
        else:
            d = None
        dirs.append(d)
    return dirs


_PAIRS = {"(": ")", "[": "]", "{": "}", "<": ">", "\u00ab": "\u00bb"}


def _bracket_pairs(text: str) -> list:
    stack, pairs = [], []
    for i, ch in enumerate(text):
        if ch in _PAIRS:
            stack.append((ch, i))
        elif ch in _PAIRS.values():
            for k in range(len(stack) - 1, -1, -1):
                if _PAIRS[stack[k][0]] == ch:
                    pairs.append((stack[k][1], i))
                    del stack[k:]
                    break
    return pairs


def mirror_brackets_for_rtl(text: str) -> str:
    """Swap ( ) [ ] { } < > in a right-to-left line the way the Unicode bidi algorithm would.

    Some python-bidi versions reorder the line but forget to mirror brackets, so "(بأجر)"
    would be drawn as ")بأجر(". We swap them *before* reordering, and reordering then puts each
    one on the correct side. A bracket pair is mirrored when it holds right-to-left text, or
    when it holds only left-to-right text but follows right-to-left text; it is left alone when
    it holds left-to-right text that follows left-to-right text ("hours (Mon-Fri) are")."""
    dirs = _char_directions(text)
    pair_dir: dict = {}
    for a, b in _bracket_pairs(text):
        inside = {d for d in dirs[a + 1:b] if d}
        if "R" in inside:
            d = "R"
        elif "L" in inside:
            before = next((dirs[j] for j in range(a - 1, -1, -1) if dirs[j]), "R")
            d = "L" if before == "L" else "R"
        else:
            continue
        pair_dir[a] = pair_dir[b] = d
    out = list(text)
    for i, ch in enumerate(text):
        if ch not in _BRACKETS:
            continue
        d = pair_dir.get(i)
        if d is None:  # an unmatched or empty bracket: take the direction of its neighbours
            before = next((dirs[j] for j in range(i - 1, -1, -1) if dirs[j]), None)
            after = next((dirs[j] for j in range(i + 1, len(text)) if dirs[j]), None)
            d = "L" if before == "L" and after == "L" else "R"
        if d == "R":
            out[i] = ch.translate(_SWAP)
    return "".join(out)


def _library_mirrors_brackets(get_display) -> bool:
    """Ask the installed python-bidi whether it mirrors brackets itself (older versions do)."""
    try:
        return get_display("\u0628(\u0628)", base_dir="R").startswith("(")
    except Exception:
        return False


def make_shaper(lang: str) -> Shaper:
    """Only text that contains Arabic letters is shaped, so English lines are never touched.
    An Arabic plan needs the packages (error if missing); an English plan that happens to hold
    one Arabic answer (the language choice) uses them when present and skips shaping if not."""
    tools = None
    try:
        tools = _load_arabic_tools()
    except RuntimeError:
        if lang == "ar":
            raise
    if tools is None:
        return Shaper(lambda s: s, lambda s, rtl: s)
    reshape, get_display = tools
    own_mirroring = not _library_mirrors_brackets(get_display)

    def display(s: str, rtl: bool) -> str:
        if not has_arabic(s):
            return s
        shaped = reshape(s)
        if rtl and own_mirroring:
            shaped = mirror_brackets_for_rtl(shaped)
        return get_display(shaped, base_dir="R" if rtl else "L")

    return Shaper(lambda s: reshape(s) if has_arabic(s) else s, display)


def register_fonts() -> None:
    for name, file in ((REG, "DejaVuSans.ttf"), (BOLD, "DejaVuSans-Bold.ttf")):
        try:
            pdfmetrics.getFont(name)
        except KeyError:
            pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / file)))


def wrap(text: str, font: str, size: float, width: float, measure: Callable[[str], str]) -> list[str]:
    """Split text into lines that fit `width`. A word wider than a whole line (a long URL) is
    cut by characters instead of running off the page."""
    def fits(s: str) -> bool:
        return pdfmetrics.stringWidth(measure(s), font, size) <= width

    lines: list[str] = []
    for paragraph in (text or "").split("\n"):
        current = ""
        for word in paragraph.split():
            candidate = f"{current} {word}".strip()
            if fits(candidate):
                current = candidate
                continue
            if current:
                lines.append(current)
                current = ""
            while not fits(word) and len(word) > 1:  # hard-split an over-long word
                cut = len(word) - 1
                while cut > 1 and not fits(word[:cut]):
                    cut -= 1
                lines.append(word[:cut])
                word = word[cut:]
            current = word
        lines.append(current)
    return lines


class _Writer:
    def __init__(self, lang: str, shaper: Shaper, footer_text: str, page_label: str):
        register_fonts()
        self.lang, self.shaper = lang, shaper
        self.footer_text, self.page_label = footer_text, page_label
        self.buf = io.BytesIO()
        self.c = canvas.Canvas(self.buf, pagesize=A4)
        self.w, self.h = A4
        self.m = 20 * mm
        self.y = self.h - self.m
        self.page = 1

    # -- pages
    def _footer(self) -> None:
        c = self.c
        c.setStrokeColor(HexColor("#d9ddea")); c.setLineWidth(0.6)
        c.line(self.m, FOOTER_H, self.w - self.m, FOOTER_H)
        c.setFillColor(MUTED)
        rtl = self.lang == "ar"
        for i, line in enumerate(wrap(self.footer_text, REG, 7.5, self.w - 2 * self.m, self.shaper.width_text)[:3]):
            y = FOOTER_H - 4 * mm - i * 9
            vis = self.shaper.display(line, rtl and has_arabic(line))
            if rtl and has_arabic(line):
                c.setFont(REG, 7.5); c.drawRightString(self.w - self.m, y, vis)
            else:
                c.setFont(REG, 7.5); c.drawString(self.m, y, vis)
        c.setFont(REG, 7.5)
        c.drawCentredString(self.w / 2, 8 * mm, self.shaper.display(self.page_label.format(n=self.page), False))

    def _new_page(self) -> None:
        self._footer()
        self.c.showPage()
        self.page += 1
        self.y = self.h - self.m

    def _need(self, height: float) -> None:
        if self.y - height < FOOTER_H + 6 * mm:
            self._new_page()

    # -- drawing
    def text(self, s: str, size: float = 10.5, bold: bool = False, color=INK, indent: float = 0,
             link: str = "", marker: str = "", after: float = 2) -> None:
        font = BOLD if bold else REG
        rtl = self.lang == "ar" and has_arabic(s)   # this block runs right to left
        start_shift = indent if (rtl or self.lang != "ar") else 0
        width = self.w - 2 * self.m - start_shift
        leading = size * 1.5
        for n, line in enumerate(wrap(s, font, size, width, self.shaper.width_text)):
            self._need(leading)
            self.y -= leading
            self.c.setFont(font, size); self.c.setFillColor(color)
            vis = self.shaper.display(line, rtl)
            if rtl:
                right = self.w - self.m
                if marker and n == 0:
                    self.c.drawRightString(right, self.y, marker)
                self.c.drawRightString(right - start_shift, self.y, vis)
            else:
                left = self.m
                if marker and n == 0:
                    self.c.drawString(left, self.y, marker)
                self.c.drawString(left + start_shift, self.y, vis)
                if link:
                    wd = pdfmetrics.stringWidth(vis, font, size)
                    self.c.linkURL(link, (left + start_shift, self.y - 2, left + start_shift + wd, self.y + size),
                                   relative=0, thickness=0)
        self.y -= after

    def heading(self, s: str) -> None:
        self._need(40 * mm)  # a heading never sits alone at the bottom of a page
        self.y -= 5 * mm
        self.text(s, size=13, bold=True, color=ACCENT, after=1)
        self.y -= 1.2 * mm  # a little room, so Arabic letters that drop below the line do not touch the rule
        self.c.setStrokeColor(ACCENT); self.c.setLineWidth(0.8)
        self.c.line(self.m, self.y, self.w - self.m, self.y)
        self.y -= 2 * mm

    def space(self, mm_: float = 2) -> None:
        self.y -= mm_ * mm

    def finish(self, title: str) -> bytes:
        self._footer()
        self.c.setTitle(title)
        self.c.setAuthor("FirstGen Navigator")
        self.c.save()
        return self.buf.getvalue()


def plan_to_pdf(plan, strings: dict, lang: str, shaper: Shaper | None = None) -> bytes:
    """Render a Plan (app/plan.py) to PDF bytes, in the plan's language."""
    from app.plan import format_date
    from app.strings import t

    shaper = shaper or make_shaper(lang)
    w = _Writer(lang, shaper, strings["disclosure"], strings["plan"]["page"])

    w.text(t(strings, "plan.title"), size=24, bold=True, color=ACCENT, after=1)
    w.text(plan.institution_name, size=11, color=MUTED, after=0)
    w.text(t(strings, "plan.prepared", date=format_date(plan.prepared_on, lang)), size=9.5, color=MUTED, after=1)
    w.text(t(strings, "plan.subtitle"), size=10, color=MUTED, after=2)

    if plan.about:
        w.heading(t(strings, "plan.about"))
        for question, answer in plan.about:
            w._need(14 * mm)
            w.text(question, size=9, color=MUTED, after=0)
            w.text(answer, size=10.5, after=3)

    w.heading(t(strings, "plan.steps"))
    if plan.steps:
        for i, step in enumerate(plan.steps, 1):
            w.text(step, indent=7 * mm, marker=f"{i}.", after=3)
    else:
        w.text(t(strings, "plan.empty"), color=MUTED)

    if plan.deadlines:
        w.heading(t(strings, "plan.dates"))
        for d in plan.deadlines:
            w._need(20 * mm)
            w.text(d["item"], bold=True, after=0)
            w.text(f"{d['date']} · {d['term']}", size=9.5, color=MUTED, after=0)
            w.text(d["url"], size=8, color=LINK, link=d["url"], after=3)

    for key, entries in (("plan.programs", plan.programs), ("plan.contacts", plan.contacts)):
        if not entries:
            continue
        w.heading(t(strings, key))
        for p in entries:
            w._need(24 * mm)
            w.text(p["name"] if key == "plan.programs" else p["office"], bold=True, after=0)
            if key == "plan.programs":
                w.text(p["office"], size=9.5, color=MUTED, after=0)
            if p["phone"]:
                w.text(t(strings, "plan.phone", phone=p["phone"]), size=9.5, after=0)
            if p["hours"]:
                w.text(t(strings, "plan.hours", hours=p["hours"]), size=9.5, after=0)
            if p["url"]:
                w.text(p["url"], size=8, color=LINK, link=p["url"], after=3)

    return w.finish(t(strings, "plan.title"))
