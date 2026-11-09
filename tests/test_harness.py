"""Tests for core/harness.py's own logic: formatting an AgentResult for the screen, turning it
into the dict that gets saved to docs/transcripts/, and the --save CLI flag. Built directly
from AdvisorAnswer/AgentResult objects, no model or tool call needed for most of these; a
fake LangChain (see tests/fake_langchain.py) is installed only so core.harness can import
core.agent at all.
"""
import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from tests.fake_langchain import install

install()
import core.harness as harness  # noqa: E402

from core.agent import AgentResult  # noqa: E402
from core.schema import AdvisorAnswer, Citation, Contact  # noqa: E402


def result_with(**kw):
    kw.setdefault("answer", "The MAP priority date is February 1, 2027.")
    kw.setdefault("confidence", "High")
    kw.setdefault("citations", [Citation(source_id="deadlines:state-map-priority-2027-28",
                                         label="MAP priority date")])
    kw.setdefault("next_steps", [])
    answer = AdvisorAnswer(**kw)
    return AgentResult(answer=answer, tool_calls=[{"name": "lookup_deadlines", "args": {"topic": "MAP"}}],
                       raw_text="")


def test_format_answer_includes_question_confidence_citation_and_tool_call():
    text = harness.format_answer("When is MAP priority?", "en", result_with(), seconds=1.2)
    assert "When is MAP priority?" in text
    assert "Confidence: High" in text
    assert "deadlines:state-map-priority-2027-28" in text
    assert "lookup_deadlines({'topic': 'MAP'})" in text
    assert "(1.2s)" in text


def test_format_answer_handles_no_citations_next_steps_or_handoff():
    r = result_with(confidence="Low", citations=[], answer="I could not find this.")
    r.tool_calls = []
    text = harness.format_answer("Q", "en", r)
    assert "Citations: (none)" in text and "Tool calls: (none)" in text


def test_format_answer_shows_next_steps_and_handoff_contact():
    r = result_with(next_steps=["Ask the financial aid office.", "Bring your ID."],
                    human_contact=Contact(office="Financial Aid Office",
                                         url="https://ccc.edu/financialaid", phone="800-555-0000"))
    text = harness.format_answer("Q", "en", r)
    assert "Ask the financial aid office." in text
    assert "Hand-off: Financial Aid Office - https://ccc.edu/financialaid - 800-555-0000" in text


def test_transcript_entry_is_plain_json_serializable():
    entry = harness.transcript_entry("Q?", "ar", result_with(), 2.345)
    json.dumps(entry)  # must not raise
    assert entry["confidence"] == "High"
    assert entry["citations"] == [{"source_id": "deadlines:state-map-priority-2027-28",
                                   "label": "MAP priority date"}]
    assert entry["tool_calls"] == [{"name": "lookup_deadlines", "args": {"topic": "MAP"}}]
    assert entry["seconds"] == round(2.345, 1)  # transcript_entry rounds to 1 decimal
    assert entry["human_contact"] is None


def test_transcript_entry_serializes_human_contact():
    r = result_with(human_contact=Contact(office="Wellness Center", url="https://ccc.edu/wellnesscenter"))
    entry = harness.transcript_entry("Q", "en", r, 1.0)
    assert entry["human_contact"] == {"office": "Wellness Center",
                                      "url": "https://ccc.edu/wellnesscenter", "phone": ""}


def test_save_transcript_writes_readable_json(tmp_path):
    out_path = tmp_path / "docs" / "transcripts" / "01.json"
    out = harness.save_transcript(str(out_path), "Q?", "en", result_with(), 1.0)
    assert out == out_path and out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["question"] == "Q?"


def test_main_with_save_writes_file_and_prints_without_crashing(tmp_path, monkeypatch):
    monkeypatch.setattr(harness, "ask", lambda q, language="en", institution="demo-ccc": (result_with(), 0.5))
    out_path = tmp_path / "t.json"
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = harness.main(["When is MAP priority?", "--language", "en", "--save", str(out_path)])
    assert code == 0
    assert "Confidence: High" in buf.getvalue()
    assert "Saved ->" in buf.getvalue()
    assert out_path.exists()
