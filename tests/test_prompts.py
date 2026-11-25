"""The system prompts must actually contain the five things the brief asks for, in both
languages: citation rules, confidence labels, refusal policy, disclosure, and tool guidance."""
from core.prompts import LANGUAGES, load_system_prompt


def test_both_languages_load_and_fill_in_institution_name():
    for lang in LANGUAGES:
        text = load_system_prompt(lang, institution_name="Test College")
        assert "Test College" in text
        assert "{" not in text and "}" not in text  # no leftover placeholder


def test_rejects_unknown_language():
    import pytest

    with pytest.raises(ValueError):
        load_system_prompt("fr")


def test_mentions_all_four_tools_by_name():
    for lang in LANGUAGES:
        text = load_system_prompt(lang)
        for tool in ("search_knowledge_base", "lookup_deadlines", "match_programs",
                    "escalate_to_human"):
            assert tool in text, f"{lang}: missing tool '{tool}'"


def test_has_the_three_confidence_labels():
    en = load_system_prompt("en")
    for label in ("High", "Medium", "Low"):
        assert label in en
    ar = load_system_prompt("ar")
    for label in ("High", "Medium", "Low"):  # kept in English so the output schema matches
        assert label in ar


def test_states_the_disclosure_content():
    en = load_system_prompt("en")
    assert "not an attorney" in en and "financial aid officer" in en
    ar = load_system_prompt("ar")
    assert "محامياً" in ar and "موظف مساعدات مالية" in ar


def test_forbids_asking_immigration_status():
    for lang in LANGUAGES:
        text = load_system_prompt(lang)
        assert "immigration status" in text.lower() or "وضعه القانوني" in text


def test_requires_citation_on_every_fact():
    en = load_system_prompt("en")
    assert "source_id" in en and "citation" in en.lower()
    ar = load_system_prompt("ar")
    assert "source_id" in ar


def test_says_prefer_newer_source_on_conflict():
    for lang in LANGUAGES:
        text = load_system_prompt(lang).lower()
        assert "newer" in text or "أحدث" in text


def test_not_found_is_distinct_from_low_confidence():
    en = load_system_prompt("en")
    assert "not found" in en.lower()


def test_eight_results_minimum_matches_week2_decision():
    for lang in LANGUAGES:
        assert "8" in load_system_prompt(lang)


def test_both_prompts_tell_the_model_to_search_in_english():
    # Arabic questions are searched with an English phrase: the documents are English and the
    # same English query makes the two languages find the same sources (issue #26).
    assert "in English" in load_system_prompt("en")
    assert "بالإنجليزي" in load_system_prompt("ar")


def test_the_search_tool_description_asks_for_an_english_query():
    from core.tools import search_knowledge_base

    assert "IN ENGLISH" in search_knowledge_base.__doc__


def test_both_prompts_say_to_stay_inside_the_passages_and_to_hand_off():
    from core.prompts import load_system_prompt

    en = load_system_prompt("en", "X")
    ar = load_system_prompt("ar", "X")
    assert "Say only what the passages say" in en and "human_contact" in en
    assert "قول بس اللي بتقوله المقاطع" in ar and "human_contact" in ar
    assert "use **Low**" in en and "**Low**" in ar
