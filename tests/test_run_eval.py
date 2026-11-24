import json
from types import SimpleNamespace

import pytest

from evals import judge, run_eval as ev

KNOWN = {"state-isac-map", "deadlines:state-map-priority-2027-28", "programs:ccc-wellness-centers"}


def row(id="g1", behavior="grounded", handoff="false", sensitive="false", expected="state-isac-map", lang="en"):
    return {"id": id, "language": lang, "question": f"question {id}", "expected_behavior": behavior,
            "expected_source_ids": expected, "requires_handoff": handoff, "sensitive": sensitive}


def run(cites=("state-isac-map::03",), conf="High", contact=False, returned=None, **kw):
    return {"answer": "an answer", "confidence": conf, "citations": list(cites), "has_contact": contact,
            "returned_ids": list(cites if returned is None else returned), "evidence": [], "fallback": False, **kw}


# ---- the checks

def test_a_good_grounded_answer_passes_every_check():
    c = ev.evaluate_run(row(), run(), KNOWN)
    assert c["citation_present"] and c["source_exists"] and c["from_tools"] and c["answered"] and c["expected_source"]
    assert c["refusal"] is None and c["handoff"] is None


def test_missing_and_invented_citations_are_caught():
    assert ev.evaluate_run(row(), run(cites=()), KNOWN)["citation_present"] is False
    assert ev.evaluate_run(row(), run(cites=("made-up-doc::01",)), KNOWN)["source_exists"] is False
    # real document, but no tool returned it this turn
    assert ev.evaluate_run(row(), run(returned=[]), KNOWN)["from_tools"] is False
    # table ids count as existing
    assert ev.evaluate_run(row(), run(cites=("deadlines:state-map-priority-2027-28",)), KNOWN)["source_exists"]


def test_refusal_needs_low_confidence_and_no_citation():
    oos = row("g2", "refuse", expected="")
    assert ev.evaluate_run(oos, run(cites=(), conf="Low"), KNOWN)["refusal"] is True
    assert ev.evaluate_run(oos, run(cites=("state-isac-map::03",), conf="Low"), KNOWN)["refusal"] is False
    assert ev.evaluate_run(oos, run(cites=(), conf="High"), KNOWN)["refusal"] is False
    # a refusal that also hands off may cite the office it points to
    visa = row("g3", "refuse", handoff="true", expected="")
    assert ev.evaluate_run(visa, run(cites=("programs:ccc-wellness-centers",), conf="Low", contact=True), KNOWN)["refusal"]


def test_handoff_and_answered_checks():
    h = row("g4", handoff="true", sensitive="true")
    assert ev.evaluate_run(h, run(contact=True), KNOWN)["handoff"] is True
    assert ev.evaluate_run(h, run(contact=False), KNOWN)["handoff"] is False
    assert ev.evaluate_run(row(), run(conf="Low"), KNOWN)["answered"] is False
    assert ev.evaluate_run(row(behavior="partial"), run(conf="Low"), KNOWN)["answered"] is None


def test_expected_source_is_information_only_and_matches_documents_and_table_rows():
    assert ev.evaluate_run(row(expected="other-doc"), run(), KNOWN)["expected_source"] is False
    r = row(expected="deadlines:state-map-priority-2027-28")
    assert ev.evaluate_run(r, run(cites=("deadlines:state-map-priority-2027-28",)), KNOWN)["expected_source"]


# ---- the numbers

def test_summary_verdicts_and_failures():
    rows = [row("a"), row("b", "refuse", expected=""), row("c", handoff="true", sensitive="true"),
            row("d", "refuse", expected=""), row("e")]
    runs = {"a": run(judge={"score": 1.0}), "b": run(cites=(), conf="Low"),
            "c": run(contact=True, judge={"score": 0.5, "unsupported": ["a claim"]}),
            "d": run(cites=(), conf="High")}
    s = ev.summarize(rows, runs, KNOWN)
    assert s["run"] == 4 and s["questions"] == 5
    assert s["checks"]["refusal"] == (1, 2)
    assert s["sensitive"] == (1, 1)
    assert s["groundedness"][1] == 2 and s["groundedness"][0] == pytest.approx(0.75)
    failed = {f["id"]: f["failed"] for f in s["failures"]}
    assert "refusal" in failed["d"] and "groundedness" in failed["c"]
    v = ev.verdicts(s)
    assert v == {"groundedness": "NOT MET", "refusal": "NOT MET", "sensitive": "PASS"}


def test_verdicts_say_not_enough_data_when_nothing_ran():
    s = ev.summarize([row()], {}, KNOWN)
    assert set(ev.verdicts(s).values()) == {"not enough data yet"}


# ---- running with a cache

def test_run_questions_saves_skips_and_obeys_the_limit():
    rows = [row("a"), row("b"), row("c")]
    cache, calls = {"a": run()}, []

    def runner(r):
        calls.append(r["id"])
        return run()

    saved = []
    n = ev.run_questions(rows, runner, cache, save=lambda c: saved.append(len(c)), limit=1, log=lambda *_: None)
    assert n == 1 and calls == ["b"] and set(cache) == {"a", "b"} and saved == [2]


def test_a_fallback_is_not_saved_and_the_daily_limit_stops_the_run():
    rows = [row("a"), row("b")]
    cache = {}
    outs = iter([run(fallback=True, answer="Something went wrong (busy)"), run()])
    ev.run_questions(rows, lambda r: next(outs), cache, log=lambda *_: None)
    assert set(cache) == {"b"}
    limit = run(fallback=True, answer="Rate limit reached ... on tokens per day (TPD): Limit 200000")
    with pytest.raises(ev.StopForToday):
        ev.run_questions([row("z")], lambda r: limit, {}, log=lambda *_: None)


# ---- the judge

def test_parse_judge_reads_json_and_rejects_nonsense():
    ok = judge.parse_judge('Sure! {"total_claims": 4, "supported_claims": 3, "unsupported": ["x"]}')
    assert ok["score"] == 0.75 and ok["unsupported"] == ["x"]
    assert judge.parse_judge('{"total_claims": 0, "supported_claims": 0}')["score"] is None
    assert "error" in judge.parse_judge("no json here")
    assert "error" in judge.parse_judge('{"total_claims": 2, "supported_claims": 5}')
    assert "error" in judge.parse_judge('{"total_claims": "many"}')


def test_judge_input_contains_question_answer_and_sources():
    text = judge.build_judge_input("Q?", "A.", [{"source_id": "s::01", "text": "the passage"}])
    assert "Q?" in text and "A." in text and "[s::01]" in text and "the passage" in text


class FakeJudge:
    def __init__(self, reply):
        self.reply, self.seen = reply, []

    def invoke(self, messages):
        self.seen.append(messages)
        return SimpleNamespace(content=self.reply)


def test_judge_all_judges_only_cited_answers_once():
    from tests.fake_langchain import install

    install()
    rows = [row("a"), row("b")]
    cache = {"a": run(evidence=[{"source_id": "state-isac-map::03", "text": "t"}]), "b": run(cites=(), conf="Low")}
    llm = FakeJudge('{"total_claims": 2, "supported_claims": 2, "unsupported": []}')
    assert ev.judge_all(rows, cache, llm, "m1", log=lambda *_: None) == 1
    assert cache["a"]["judge"]["score"] == 1.0 and cache["a"]["judge"]["model"] == "m1" and "judge" not in cache["b"]
    assert ev.judge_all(rows, cache, llm, "m1", log=lambda *_: None) == 0     # already judged
    assert ev.judge_all(rows, cache, llm, "m2", log=lambda *_: None) == 1     # another model: judge again
    assert len(llm.seen) == 2


def test_judge_all_stops_on_the_daily_limit():
    from tests.fake_langchain import install

    install()
    class Limited:
        def invoke(self, m):
            raise RuntimeError("Rate limit on tokens per day (TPD)")

    cache = {"a": run()}
    with pytest.raises(ev.StopForToday):
        ev.judge_all([row("a")], cache, Limited(), "m", log=lambda *_: None)


# ---- evidence, report, command line

def test_collect_evidence_uses_the_full_chunk_then_tables_then_tool_text():
    class Coll:
        def get(self, ids):
            return {"documents": ["FULL CHUNK TEXT"] if ids == ["state-isac-map::03"] else [""]}

    d = SimpleNamespace(id="x", item="Priority date", date=SimpleNamespace(isoformat=lambda: "2027-02-01"),
                        term="2027-28", applies_to="returning", notes="")
    p = SimpleNamespace(name="Wellness", description="Counseling.", contact_office="Wellness Center",
                        contact_url="", contact_phone="", hours="")
    ctx = SimpleNamespace(retriever=SimpleNamespace(collection=Coll()), deadlines=[d],
                          program=lambda i: p if i == "ccc-wellness-centers" else None)
    calls = [{"name": "search_knowledge_base", "result": {"results": [{"source_id": "a::01", "text": "tool text"}]}}]
    ev_ = ev.collect_evidence(ctx, ["state-isac-map::03", "deadlines:x", "programs:ccc-wellness-centers", "a::01"], calls)
    assert ev_[0]["text"] == "FULL CHUNK TEXT"
    assert "2027-02-01" in ev_[1]["text"] and "Counseling" in ev_[2]["text"] and ev_[3]["text"] == "tool text"


def test_known_ids_cover_the_real_knowledge_base_and_the_golden_set_cites_only_known_ids():
    known = ev.known_source_ids("institutions/demo-ccc")
    assert "institution-ccc-tuition" in known and "programs:ccc-wellness-centers" in known
    for r in ev.load_golden():
        for sid in filter(None, r["expected_source_ids"].split(";")):
            assert sid in known, f"{r['id']}: {sid}"


def test_report_shows_targets_checks_failures_and_the_judge_prompt():
    rows = [row("a"), row("b", "refuse", expected="")]
    runs = {"a": run(judge={"score": 0.5, "unsupported": ["a bad claim"]}), "b": run(cites=(), conf="Low")}
    text = ev.render_report(rows, runs, KNOWN, "judge-model", judge.JUDGE_PROMPT, "advisor-model", "2026-11-23")
    assert "Covers **2 of 2**" in text and "`advisor-model`" in text and "`judge-model`" in text
    assert "at least 85%" in text and "Correct refusal" in text and "a bad claim" in text
    assert judge.JUDGE_PROMPT.splitlines()[0] in text


def test_report_only_makes_no_api_calls_and_writes_the_report(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ev, "RESULTS", tmp_path / "r.json")
    monkeypatch.setattr(ev, "REPORT", tmp_path / "report.md")
    (tmp_path / "r.json").write_text(json.dumps({"g041": run(cites=("institution-ccc-student-resources::01",))}),
                                     encoding="utf-8")
    assert ev.main(["--report-only"]) == 0
    assert "1 of 62 questions run" in capsys.readouterr().out
    assert "Evaluation report" in (tmp_path / "report.md").read_text(encoding="utf-8")
    assert ev.main(["--report-only", "--only", "g999"]) == 2


# ---- step 24: the judge model and --judge-only

def test_default_judge_model_is_not_the_retired_one():
    assert judge.DEFAULT_JUDGE_MODEL != "llama-3.3-70b-versatile"
    assert judge.DEFAULT_JUDGE_MODEL != "openai/gpt-oss-120b"      # the advisor must not grade itself


def test_judge_only_makes_no_advisor_calls(tmp_path, monkeypatch, capsys):
    import sys
    import types

    saved = {"g001": run(judge={"error": "NotFoundError", "model": "old"})}
    monkeypatch.setattr(ev, "RESULTS", tmp_path / "r.json")
    monkeypatch.setattr(ev, "REPORT", tmp_path / "rep.md")
    ev.RESULTS.write_text(json.dumps(saved), encoding="utf-8")
    monkeypatch.setattr(ev, "load_golden", lambda path=ev.GOLDEN: [row("g001")])
    monkeypatch.setattr(ev, "known_source_ids", lambda root: KNOWN)
    seen = {}
    monkeypatch.setattr(ev, "judge_all", lambda todo, cache, llm, model, **kw: seen.setdefault("model", model))
    monkeypatch.setattr(judge, "get_judge_llm", lambda model=None: object())
    monkeypatch.setitem(sys.modules, "dotenv", types.SimpleNamespace(load_dotenv=lambda *a, **k: None))

    def boom(*a, **k):
        raise AssertionError("the advisor must not be called")

    monkeypatch.setattr(ev, "run_questions", boom)
    monkeypatch.setattr(ev, "answer_runner", boom)
    assert ev.main(["--judge-only", "--judge-model", "m-x"]) == 0
    assert seen["model"] == "m-x" and ev.REPORT.exists()


def test_judge_run_asks_again_once_when_the_reply_is_not_json():
    replies = iter(["", '{"total_claims": 2, "supported_claims": 1, "unsupported": ["x"]}'])

    class Llm:
        calls = 0

        def invoke(self, messages):
            Llm.calls += 1
            return SimpleNamespace(content=next(replies))

    out = judge.judge_run(Llm(), "Q", {"answer": "A", "evidence": []}, "m")
    assert out["score"] == 0.5 and Llm.calls == 2 and out["model"] == "m"


def test_judge_run_error_shows_what_the_model_said():
    class Llm:
        def invoke(self, messages):
            return SimpleNamespace(content="I think the answer is fine.")

    out = judge.judge_run(Llm(), "Q", {"answer": "A", "evidence": []}, "m")
    assert "error" in out and "I think the answer is fine" in out["error"]
