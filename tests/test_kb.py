import datetime as dt

import pytest

from core.kb import load_doc, load_kb

GOOD = """---
title: FAFSA basics
source_url: https://studentaid.gov/example
layer: federal
audience: [applying, enrolled]
retrieved_date: 2026-10-28
language: en
effective_term: 2026-27
---
# Heading

Some text.
"""


def write(tmp_path, text, name="doc.md"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_valid_doc_loads(tmp_path):
    doc = load_doc(write(tmp_path, GOOD))
    assert doc.meta.title == "FAFSA basics"
    assert doc.meta.layer == "federal"
    assert doc.meta.audience == ["applying", "enrolled"]
    assert doc.meta.retrieved_date == dt.date(2026, 10, 28)
    assert doc.meta.effective_term == "2026-27"
    assert doc.body.startswith("# Heading")


def test_missing_front_matter_rejected(tmp_path):
    with pytest.raises(ValueError, match="front matter"):
        load_doc(write(tmp_path, "# Just a heading\n\nNo front matter here.\n"))


def test_bad_layer_rejected(tmp_path):
    with pytest.raises(ValueError, match="layer"):
        load_doc(write(tmp_path, GOOD.replace("layer: federal", "layer: nation")))


def test_missing_field_rejected(tmp_path):
    with pytest.raises(ValueError, match="source_url"):
        load_doc(write(tmp_path, GOOD.replace("source_url: https://studentaid.gov/example\n", "")))


def test_typo_in_field_name_rejected(tmp_path):
    with pytest.raises(ValueError, match="retrieved_date"):
        load_doc(write(tmp_path, GOOD.replace("retrieved_date", "retreived_date")))


def test_audience_as_single_word_accepted(tmp_path):
    doc = load_doc(write(tmp_path, GOOD.replace("audience: [applying, enrolled]", "audience: all")))
    assert doc.meta.audience == ["all"]


def test_effective_term_number_becomes_text(tmp_path):
    doc = load_doc(write(tmp_path, GOOD.replace("effective_term: 2026-27", "effective_term: 2026")))
    assert doc.meta.effective_term == "2026"


def test_load_kb_reports_the_broken_file(tmp_path):
    write(tmp_path, GOOD, "good.md")
    assert len(load_kb(tmp_path)) == 1
    write(tmp_path, GOOD.replace("layer: federal", "layer: nation"), "bad.md")
    with pytest.raises(ValueError, match="bad.md"):
        load_kb(tmp_path)