"""Tests for scripts/run_transcripts.py: the question list itself, and that main() saves a
transcript per question but keeps going even when one question raises (for example the free
Groq tier's rate limit) instead of losing the transcripts that already succeeded.
"""
import json

from tests.fake_langchain import install

install()  # langchain_core/langchain_groq/langchain.agents must exist before core.agent imports them
import scripts.run_transcripts as run_transcripts  # noqa: E402

from core.agent import AgentResult  # noqa: E402
from core.schema import AdvisorAnswer  # noqa: E402


def fake_result(confidence="Low"):
    answer = AdvisorAnswer(answer="ok", citations=[], confidence=confidence, next_steps=[])
    return AgentResult(answer=answer, tool_calls=[{"name": "lookup_deadlines", "args": {}}], raw_text="ok")


def always_fails(question, language="en"):
    raise RuntimeError("Error code: 413 - tokens per minute rate_limit_exceeded")


def test_conversations_list_has_ten_entries_with_both_languages():
    langs = [c[2] for c in run_transcripts.CONVERSATIONS]
    assert len(run_transcripts.CONVERSATIONS) == 10
    assert langs.count("en") == 7
    assert langs.count("ar") == 3


def test_all_golden_ids_and_slugs_are_unique():
    ids = [c[0] for c in run_transcripts.CONVERSATIONS]
    slugs = [c[1] for c in run_transcripts.CONVERSATIONS]
    assert len(ids) == len(set(ids))
    assert len(slugs) == len(set(slugs))


def test_main_saves_a_transcript_per_question(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(run_transcripts, "ask", lambda q, language="en": (fake_result(), 0.5))
    monkeypatch.setattr(run_transcripts.time, "sleep", lambda s: None)

    code = run_transcripts.main()

    assert code == 0
    saved = sorted((tmp_path / "docs" / "transcripts").glob("*.json"))
    assert len(saved) == 10
    data = json.loads(saved[0].read_text(encoding="utf-8"))
    assert data["confidence"] == "Low"


def test_main_keeps_going_when_one_question_raises(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(run_transcripts.time, "sleep", lambda s: None)
    calls = {"n": 0}

    def flaky_ask(question, language="en"):
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("Error code: 413 - tokens per minute rate_limit_exceeded")
        return fake_result(), 0.1

    monkeypatch.setattr(run_transcripts, "ask", flaky_ask)

    code = run_transcripts.main()

    assert code == 0
    out = capsys.readouterr().out
    assert out.count("FAILED:") == 1  # only the 3rd question raised
    assert "1 question(s) failed" in out
    saved = list((tmp_path / "docs" / "transcripts").glob("*.json"))
    assert len(saved) == 9  # every question but the one that raised


def test_main_reports_zero_saved_when_every_question_fails(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(run_transcripts.time, "sleep", lambda s: None)
    monkeypatch.setattr(run_transcripts, "ask", always_fails)

    code = run_transcripts.main()

    assert code == 0
    out = capsys.readouterr().out
    assert out.count("FAILED:") == 10  # the per-question line, once each
    assert "10 question(s) failed" in out
    saved = list((tmp_path / "docs" / "transcripts").glob("*.json"))
    assert len(saved) == 0
