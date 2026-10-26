import pytest

from core.tables import load_deadlines, load_programs

D_HEAD = "id,layer,institution,term,item,date,applies_to,source_url,retrieved_date,notes,language\n"
P_HEAD = (
    "id,institution,name,category,eligibility_tags,description,contact_office,"
    "contact_url,contact_phone,hours,language_support,source_url,retrieved_date\n"
)


def write(tmp_path, text):
    path = tmp_path / "table.csv"
    path.write_text(text, encoding="utf-8")
    return path


def test_valid_deadline_row_loads(tmp_path):
    row = "d1,state,,Spring 2027,Example item,2099-03-01,all,https://example.com,2026-10-27,,en\n"
    rows = load_deadlines(write(tmp_path, D_HEAD + row))
    assert len(rows) == 1
    assert rows[0].institution is None
    assert str(rows[0].date) == "2099-03-01"


def test_bad_date_is_rejected(tmp_path):
    row = "d1,state,,Spring 2027,Example item,not-a-date,all,https://example.com,2026-10-27,,en\n"
    with pytest.raises(ValueError, match="line 2"):
        load_deadlines(write(tmp_path, D_HEAD + row))


def test_bad_layer_is_rejected(tmp_path):
    row = "d1,federel,,Spring 2027,Example item,2099-03-01,all,https://example.com,2026-10-27,,en\n"
    with pytest.raises(ValueError, match="layer"):
        load_deadlines(write(tmp_path, D_HEAD + row))


def test_duplicate_ids_are_rejected(tmp_path):
    row = "d1,state,,Spring 2027,Example item,2099-03-01,all,https://example.com,2026-10-27,,en\n"
    with pytest.raises(ValueError, match="duplicate id"):
        load_deadlines(write(tmp_path, D_HEAD + row + row))


def test_program_tags_are_split(tmp_path):
    row = "p1,Demo College,Food Pantry,food,first_gen;caregiver,Free groceries,Student Affairs,,,,en;ar,https://example.com,2026-10-27\n"
    rows = load_programs(write(tmp_path, P_HEAD + row))
    assert rows[0].eligibility_tags == ["first_gen", "caregiver"]
    assert rows[0].language_support == ["en", "ar"]


def test_unknown_tag_is_rejected(tmp_path):
    row = "p1,Demo College,Food Pantry,food,not_a_tag,Free groceries,Student Affairs,,,,en,https://example.com,2026-10-27\n"
    with pytest.raises(ValueError, match="eligibility_tags"):
        load_programs(write(tmp_path, P_HEAD + row))