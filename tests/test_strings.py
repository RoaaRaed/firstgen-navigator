"""Tests for app/strings.py: the English and Arabic files must stay in step."""
import json

from app import strings


def _both():
    return strings.load_strings("en"), strings.load_strings("ar")


def _keys(node, prefix=""):
    """All dotted key paths of a nested dict; lists of question dicts are walked by id."""
    out = set()
    if isinstance(node, dict):
        for k, v in node.items():
            out |= _keys(v, f"{prefix}{k}.")
            out.add(f"{prefix}{k}")
    elif isinstance(node, list):
        for item in node:
            if isinstance(item, dict) and "id" in item:
                out |= _keys(item, f"{prefix}{item['id']}.")
    return out


def test_english_and_arabic_have_exactly_the_same_keys():
    en, ar = _both()
    assert _keys(en) == _keys(ar)


def test_every_question_has_same_type_and_option_ids_in_both_languages():
    en, ar = _both()
    for q_en, q_ar in zip(en["questionnaire"]["questions"], ar["questionnaire"]["questions"]):
        assert q_en["id"] == q_ar["id"]
        assert q_en["type"] == q_ar["type"]
        assert [o["id"] for o in q_en.get("options", [])] == [o["id"] for o in q_ar.get("options", [])]


def test_no_translation_is_empty():
    for lang in strings.LANGUAGES:
        for key in ("app.title", "app.subtitle", "disclosure", "buttons.start", "buttons.clear_answers"):
            assert strings.t(strings.load_strings(lang), key).strip()


def test_disclosure_matches_the_brief_promises():
    en, ar = _both()
    assert "AI" in en["disclosure"] and "does not know" in en["disclosure"]
    assert "الذكاء الاصطناعي" in ar["disclosure"]


def test_the_questionnaire_never_asks_about_immigration_status():
    # Brief 4.4: the aid question offers "not eligible or not sure" instead.
    ids = [q["id"] for q in strings.load_strings("en")["questionnaire"]["questions"]]
    assert not any("immig" in i or "status" in i or "income" in i or "ssn" in i for i in ids)


def test_rtl_only_for_arabic():
    assert strings.is_rtl("ar") and not strings.is_rtl("en")
    assert strings.text_direction("ar") == "rtl" and strings.text_direction("en") == "ltr"


def test_unknown_language_falls_back_to_english():
    assert strings.normalize("fr") == "en" and strings.normalize(None) == "en"
    assert strings.load_strings("fr") == strings.load_strings("en")


def test_page_css_is_rtl_for_arabic_and_empty_for_english():
    assert "direction: rtl" in strings.page_css("ar")
    assert "Arabic" in strings.page_css("ar")
    assert strings.page_css("en") == ""


def test_t_returns_the_key_when_missing_and_fills_placeholders():
    en = strings.load_strings("en")
    assert strings.t(en, "no.such.key") == "no.such.key"
    assert strings.t(en, "questionnaire.choose_up_to", max=3) == "Choose up to 3"
    assert strings.t(strings.load_strings("ar"), "questionnaire.choose_up_to", max=3).count("3") == 1


def test_page_css_does_not_reverse_columns_a_second_time():
    # direction: rtl already puts the first button on the right; row-reverse would undo it.
    assert "row-reverse" not in strings.page_css("ar")
