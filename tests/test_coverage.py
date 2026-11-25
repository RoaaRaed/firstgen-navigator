import datetime as dt
from types import SimpleNamespace

from core import admin, coverage

TODAY = dt.date(2026, 11, 25)
META = {"title": "T", "source_url": "https://example.edu", "layer": "institution", "audience": ["all"]}
DEADLINES = ("id,layer,institution,term,item,date,applies_to,source_url,retrieved_date,notes,language\n"
             "d1,institution,City College,Spring 2027,Last day to drop,2027-04-08,all,https://example.edu/d,2026-10-29,,en\n")


def make_institution(tmp_path, docs=("alpha", "beta"), old=()):
    for slug in docs:
        date = dt.date(2025, 1, 1) if slug in old else dt.date(2026, 11, 1)
        _s, full = admin.make_kb_document(slug + ".md", f"{slug} text.", META, today=date)
        admin.save_document(tmp_path, slug, full)
    (tmp_path / "deadlines.csv").write_text(DEADLINES, encoding="utf-8")
    return tmp_path


class Retriever:
    """Returns the given doc ids for every question (score 0.9), or nothing."""
    def __init__(self, doc_ids=(), score=0.9):
        self.doc_ids, self.score = doc_ids, score

    def search(self, query, k=5, **kw):
        return [SimpleNamespace(doc_id=d, score=self.score) for d in self.doc_ids]


def q(id, expected="", behavior="grounded", lang="en"):
    return {"id": id, "language": lang, "question": f"question {id}", "expected_behavior": behavior,
            "expected_source_ids": expected}


def test_stale_documents_are_listed_oldest_first(tmp_path):
    make_institution(tmp_path, ("alpha", "beta", "gamma"), old=("alpha", "gamma"))
    stale = coverage.stale_documents(tmp_path, 180, TODAY)
    assert [s["id"] for s in stale] == ["alpha", "gamma"] and stale[0]["age_days"] > 180
    assert coverage.stale_documents(tmp_path, 5000, TODAY) == []


def test_covered_weak_and_gap(tmp_path):
    make_institution(tmp_path)
    questions = [q("a", "alpha"),                 # exists and search returns it
                 q("b", "beta"),                  # exists but search does not return it
                 q("c", "missing-doc"),           # no such document
                 q("d", "deadlines:d1"),          # a table row answers it
                 q("e", "deadlines:nope")]        # no such table row
    report = coverage.build_report(tmp_path, Retriever(["alpha"]), questions, today=TODAY)
    status = {r["id"]: r["status"] for r in report["problems"]}
    assert report["questions"] == 5 and report["covered"] == 2
    assert status == {"b": "weak", "c": "gap", "e": "gap"}


def test_a_chunk_id_matches_its_document(tmp_path):
    make_institution(tmp_path)
    report = coverage.build_report(tmp_path, Retriever(["alpha"]), [q("a", "alpha::03")], today=TODAY)
    assert report["covered"] == 1


def test_questions_without_expected_sources_use_the_score(tmp_path):
    make_institution(tmp_path)
    good = coverage.build_report(tmp_path, Retriever(["alpha"], score=0.9), [q("a")], today=TODAY)
    bad = coverage.build_report(tmp_path, Retriever(["alpha"], score=0.4), [q("a")], today=TODAY)
    assert good["covered"] == 1 and bad["gap"] == 1


def test_refusal_and_not_found_questions_are_left_out(tmp_path):
    make_institution(tmp_path)
    questions = [q("r", behavior="refuse"), q("n", behavior="not_found"), q("p", "alpha", behavior="partial")]
    report = coverage.build_report(tmp_path, Retriever(["alpha"]), questions, today=TODAY)
    assert report["questions"] == 1


def test_removing_a_document_creates_a_gap(tmp_path):
    make_institution(tmp_path)
    before = coverage.build_report(tmp_path, Retriever(["alpha"]), [q("a", "alpha")], today=TODAY)
    admin.delete_document(tmp_path, "alpha")
    after = coverage.build_report(tmp_path, Retriever([]), [q("a", "alpha")], today=TODAY)
    assert before["gap"] == 0 and after["gap"] == 1


def test_languages_are_counted_separately(tmp_path):
    make_institution(tmp_path)
    questions = [q("a", "alpha"), q("b", "beta", lang="ar")]
    report = coverage.build_report(tmp_path, Retriever(["alpha"]), questions, today=TODAY)
    assert report["by_language"] == {"ar": {"questions": 1, "covered": 0}, "en": {"questions": 1, "covered": 1}}


def test_markdown_report_has_the_sections_and_the_privacy_note(tmp_path):
    make_institution(tmp_path, ("alpha", "beta"), old=("alpha",))
    report = coverage.build_report(tmp_path, Retriever([]), [q("c", "missing-doc")], today=TODAY)
    text = coverage.render_markdown(report)
    for part in ("# Knowledge Base Coverage Report", "## Summary", "missing-doc", "## Documents older than 180 days",
                 "alpha", "stores no record of student questions"):
        assert part in text
    empty = coverage.render_markdown(coverage.build_report(tmp_path, Retriever(["alpha"]), [q("a", "alpha")], today=TODAY))
    assert "None. Every test question has a source." in empty


def test_the_real_golden_set_loads_and_every_expected_source_exists():
    """The demo institution should have no 'gap' caused by a typo in golden_questions.csv."""
    report = coverage.build_report("institutions/demo-ccc", Retriever(["x"]), today=TODAY)
    assert report["questions"] >= 40
    assert report["gap"] == 0, [r for r in report["problems"] if r["status"] == "gap"]
