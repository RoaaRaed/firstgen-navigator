"""Week 5: the golden set must have the mix the brief asks for."""
import csv
from collections import Counter
from pathlib import Path

GOLDEN = Path("institutions/demo-ccc/golden_questions.csv")


def rows():
    with open(GOLDEN, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def test_golden_set_has_the_week5_mix():
    r = rows()
    kinds = Counter(x["expected_behavior"] for x in r)
    answerable = kinds["grounded"] + kinds["partial"]
    out_of_scope = kinds["refuse"] + kinds["not_found"]
    sensitive = [x for x in r if x["sensitive"] == "true"]
    assert answerable >= 40
    assert out_of_scope >= 10
    assert len(sensitive) >= 8


def test_every_sensitive_question_expects_a_handoff():
    assert all(x["requires_handoff"] == "true" for x in rows() if x["sensitive"] == "true")


def test_ids_are_unique_and_both_languages_are_present():
    r = rows()
    assert len({x["id"] for x in r}) == len(r)
    assert {x["language"] for x in r} == {"en", "ar"}


def test_refusals_and_not_found_cite_nothing_and_answerable_ones_cite_something():
    for x in rows():
        if x["expected_behavior"] in ("refuse", "not_found") and not x["requires_handoff"] == "true":
            assert not x["expected_source_ids"], x["id"]
        if x["expected_behavior"] == "grounded":
            assert x["expected_source_ids"], x["id"]


def test_table_ids_in_the_golden_set_exist_in_the_csv_tables():
    def ids(name):
        with open(f"institutions/demo-ccc/{name}.csv", encoding="utf-8", newline="") as f:
            return {x["id"] for x in csv.DictReader(f)}

    tables = {"deadlines": ids("deadlines"), "programs": ids("programs")}
    for x in rows():
        for sid in filter(None, x["expected_source_ids"].split(";")):
            kind, _, rest = sid.partition(":")
            if kind in tables:
                assert rest in tables[kind], f"{x['id']}: {sid}"
