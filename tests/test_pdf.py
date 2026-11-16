"""The PDF writer: layout and text, with the real fonts and a stand-in for the Arabic packages."""
import datetime as dt
import io
import sys
from types import SimpleNamespace

import pytest
from pypdf import PdfReader

from app import pdf, strings
from app import plan as plan_mod
from core.rules import load_rules
from core.tools import load_context

FULL = {"stage": "applying", "language": "ar", "work_hours": "over_30", "family": "children",
        "financial_aid": "not_eligible_or_unsure", "needs": ["paying", "deadlines"], "notes": "I work nights."}


@pytest.fixture(scope="module")
def ctx():
    c = load_context("demo-ccc")
    c.today = dt.date(2026, 11, 16)
    return c


def make_plan(ctx, lang="en", answers=FULL):
    rules = load_rules(ctx.root / "rules.yaml")
    return plan_mod.build_plan(ctx, rules, strings.load_strings(lang), answers, lang, "City Colleges of Chicago",
                               today=dt.date(2026, 11, 16))


def text_of(data: bytes) -> str:
    return "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(data)).pages)


# a stand-in for arabic-reshaper + python-bidi: reverses Arabic lines so we can see the call happened
FAKE = pdf.Shaper(lambda s: s, lambda s, rtl: s[::-1] if (rtl and pdf.has_arabic(s)) else s)


def test_english_pdf_has_the_plan_in_it(ctx):
    plan = make_plan(ctx)
    data = pdf.plan_to_pdf(plan, strings.load_strings("en"), "en")
    assert data.startswith(b"%PDF")
    text = text_of(data)
    for expected in ("My Plan", "City Colleges of Chicago", "Prepared on 2026-11-16", "Your next steps",
                     "Dates to know", "Support for you", plan.deadlines[0]["date"], plan.programs[0]["name"],
                     "You are talking to an AI advisor"):
        assert expected in text, expected
    assert "I work nights." in text


def test_the_fonts_are_embedded_so_it_looks_the_same_everywhere(ctx):
    data = pdf.plan_to_pdf(make_plan(ctx), strings.load_strings("en"), "en")
    assert b"DejaVuSans" in data


def test_pages_have_a_footer_with_the_page_number_and_long_plans_break_across_pages(ctx):
    plan = make_plan(ctx)
    plan.steps = plan.steps * 6
    data = pdf.plan_to_pdf(plan, strings.load_strings("en"), "en")
    pages = PdfReader(io.BytesIO(data)).pages
    assert len(pages) >= 3
    for i, page in enumerate(pages, 1):
        assert f"Page {i}" in page.extract_text()


def test_no_heading_is_left_alone_at_the_bottom_of_a_page(ctx):
    plan = make_plan(ctx)
    headings = ("About you", "Your next steps", "Dates to know", "Support for you", "Talk to a person")
    for page in PdfReader(io.BytesIO(pdf.plan_to_pdf(plan, strings.load_strings("en"), "en"))).pages:
        lines = [l.strip() for l in page.extract_text().splitlines() if l.strip()]
        body = lines[:-3]  # the last lines are the footer
        assert not (body and body[-1] in headings), body[-1]


def test_empty_plan_still_makes_a_valid_pdf_with_a_hint(ctx):
    plan = make_plan(ctx, answers={})
    text = text_of(pdf.plan_to_pdf(plan, strings.load_strings("en"), "en"))
    assert "Answer the questions first" in text and "About you" not in text


def test_links_are_clickable(ctx):
    data = pdf.plan_to_pdf(make_plan(ctx), strings.load_strings("en"), "en")
    uris = [a.get_object()["/A"]["/URI"] for p in PdfReader(io.BytesIO(data)).pages for a in (p.get("/Annots") or [])]
    assert uris and all(u.startswith("http") for u in uris)


def test_arabic_pdf_is_made_with_the_shaper_and_the_arabic_font(ctx):
    plan = make_plan(ctx, "ar")
    data = pdf.plan_to_pdf(plan, strings.load_strings("ar"), "ar", shaper=FAKE)
    assert data.startswith(b"%PDF") and b"DejaVuSans" in data
    text = text_of(data)
    assert "خطتي" in text or "خطتي"[::-1] in text   # the Arabic title is there (either direction)
    assert "City Colleges of Chicago" in text and plan.deadlines[0]["date"] in text  # English data is not reversed


# ---- wrap ----------------------------------------------------------------------------

def test_wrap_keeps_every_line_inside_the_width():
    pdf.register_fonts()
    text = "word " * 80
    lines = pdf.wrap(text, pdf.REG, 10, 200, lambda s: s)
    assert len(lines) > 3
    assert all(pdf.pdfmetrics.stringWidth(l, pdf.REG, 10) <= 200 for l in lines)
    assert " ".join(lines).split() == text.split()


def test_wrap_cuts_a_url_that_is_wider_than_the_page():
    pdf.register_fonts()
    url = "https://example.org/" + "a" * 200
    lines = pdf.wrap(url, pdf.REG, 8, 150, lambda s: s)
    assert len(lines) > 1 and "".join(lines) == url
    assert all(pdf.pdfmetrics.stringWidth(l, pdf.REG, 8) <= 150 for l in lines)


def test_wrap_keeps_blank_lines_and_empty_text():
    pdf.register_fonts()
    assert pdf.wrap("", pdf.REG, 10, 100, lambda s: s) == [""]
    assert pdf.wrap("a\n\nb", pdf.REG, 10, 100, lambda s: s) == ["a", "", "b"]


def test_has_arabic():
    assert pdf.has_arabic("مرحبا") and pdf.has_arabic("FAFSA ومنحة") and not pdf.has_arabic("FAFSA 2027")


# ---- the Arabic packages ---------------------------------------------------------------

def test_arabic_without_the_packages_gives_a_clear_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "arabic_reshaper", None)  # makes `import arabic_reshaper` fail
    with pytest.raises(RuntimeError, match="pip install arabic-reshaper python-bidi"):
        pdf.make_shaper("ar")


def test_english_without_the_packages_just_skips_shaping(monkeypatch):
    monkeypatch.setitem(sys.modules, "arabic_reshaper", None)
    s = pdf.make_shaper("en")
    assert s.display("Hello", False) == "Hello" and s.width_text("Hello") == "Hello"


def test_the_shaper_reshapes_then_reorders_and_only_touches_arabic(monkeypatch):
    calls = []
    monkeypatch.setitem(sys.modules, "arabic_reshaper", SimpleNamespace(reshape=lambda s: calls.append(("reshape", s)) or f"~{s}~"))
    monkeypatch.setitem(sys.modules, "bidi", SimpleNamespace(get_display=lambda s, base_dir="L": f"{base_dir}:{s}"))
    s = pdf.make_shaper("ar")
    assert s.display("مرحبا", True) == "R:~مرحبا~"
    assert s.display("مرحبا", False) == "L:~مرحبا~"
    assert s.width_text("مرحبا") == "~مرحبا~"
    assert s.display("Hello 2027", True) == "Hello 2027"
    assert ("reshape", "Hello 2027") not in calls


# ---- brackets in Arabic lines -----------------------------------------------------------

def test_brackets_are_mirrored_in_arabic_text():
    assert pdf.mirror_brackets_for_rtl("(بأجر)") == ")بأجر("
    assert pdf.mirror_brackets_for_rtl("مركز (Transfer Center) بكليتك") == "مركز )Transfer Center( بكليتك"
    assert pdf.mirror_brackets_for_rtl("ماذا (FAFSA)؟") == "ماذا )FAFSA(؟"


def test_brackets_between_english_words_are_left_alone():
    assert pdf.mirror_brackets_for_rtl("ب Illinois (MAP) x ب") == "ب Illinois (MAP) x ب"
    assert pdf.mirror_brackets_for_rtl("ب hours (Mon-Fri) ب") == "ب hours (Mon-Fri) ب"


def test_a_bracket_before_a_number_after_arabic_is_mirrored_but_after_english_is_not():
    assert pdf.mirror_brackets_for_rtl("ب (2027) ب") == "ب )2027( ب"
    assert pdf.mirror_brackets_for_rtl("ب Fall (2027) x") == "ب Fall (2027) x"


def test_square_brackets_and_guillemets_swap_too():
    assert pdf.mirror_brackets_for_rtl("ب[ب]ب") == "ب]ب[ب"
    assert pdf.mirror_brackets_for_rtl("ب«ب»ب") == "ب»ب«ب"


def _fake_bidi(mirrors: bool):
    def get_display(s, base_dir="L"):
        if s == "ب(ب)":  # the probe
            return "(ب)ب" if mirrors else ")ب(ب"
        return f"{base_dir}:{s}"
    return SimpleNamespace(get_display=get_display)


def test_we_mirror_ourselves_when_the_library_does_not(monkeypatch):
    monkeypatch.setitem(sys.modules, "arabic_reshaper", SimpleNamespace(reshape=lambda s: s))
    monkeypatch.setitem(sys.modules, "bidi", _fake_bidi(mirrors=False))
    s = pdf.make_shaper("ar")
    assert s.display("(بأجر)", True) == "R:)بأجر("


def test_we_leave_brackets_to_the_library_when_it_mirrors(monkeypatch):
    monkeypatch.setitem(sys.modules, "arabic_reshaper", SimpleNamespace(reshape=lambda s: s))
    monkeypatch.setitem(sys.modules, "bidi", _fake_bidi(mirrors=True))
    s = pdf.make_shaper("ar")
    assert s.display("(بأجر)", True) == "R:(بأجر)"


def test_an_unmatched_bracket_takes_the_direction_of_its_neighbours():
    assert pdf.mirror_brackets_for_rtl("ب (ب") == "ب )ب"
    assert pdf.mirror_brackets_for_rtl("x ( y") == "x ( y"
    assert pdf.mirror_brackets_for_rtl("ب ()ب") == "ب )(ب"
