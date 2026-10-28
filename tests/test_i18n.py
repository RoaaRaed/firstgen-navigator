import json
from pathlib import Path

I18N_DIR = Path(__file__).resolve().parents[1] / "app" / "i18n"
NON_TEXT = {"id", "type", "max_choices"}  # codes: must be identical in every language


def load(lang):
    return json.loads((I18N_DIR / f"{lang}.json").read_text(encoding="utf-8"))


def flatten(obj, prefix=""):
    """Turn nested JSON into {'questionnaire.questions.0.id': 'stage', ...}."""
    items = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            items.update(flatten(value, f"{prefix}{key}."))
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            items.update(flatten(value, f"{prefix}{i}."))
    else:
        items[prefix.rstrip(".")] = obj
    return items


def test_both_languages_have_the_same_keys():
    en, ar = flatten(load("en")), flatten(load("ar"))
    assert set(en) == set(ar), sorted(set(en) ^ set(ar))


def test_codes_are_identical_in_both_languages():
    en, ar = flatten(load("en")), flatten(load("ar"))
    for key in en:
        if key.split(".")[-1] in NON_TEXT:
            assert en[key] == ar[key], key


def test_no_empty_text():
    for lang in ("en", "ar"):
        for key, value in flatten(load(lang)).items():
            if key.split(".")[-1] not in NON_TEXT:
                assert isinstance(value, str) and value.strip(), f"{lang}: {key} is empty"


def test_questionnaire_has_eight_questions():
    for lang in ("en", "ar"):
        assert len(load(lang)["questionnaire"]["questions"]) == 8