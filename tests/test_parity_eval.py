"""The parity script's own logic (pairing, top source, verdicts, resume, report). The real
numbers come from running it against the real index and the Groq API on a normal machine."""
import json

from evals import parity_eval as pe


def test_pairs_file_has_15_complete_pairs_and_the_ten_golden_twins():
    pairs = pe.load_pairs()
    assert len(pairs) == 15
    assert [p["pair"] for p in pairs] == [f"p{i:02d}" for i in range(1, 16)]
    assert all(p["en_question"].strip() and p["ar_question"].strip() for p in pairs)
    assert any("؀" <= ch <= "ۿ" for p in pairs for ch in p["ar_question"])
    assert all(not any("؀" <= ch <= "ۿ" for ch in p["en_question"]) for p in pairs)
    assert len({p["en_id"] for p in pairs}) == 15
    assert sum(1 for p in pairs if p["ar_id"]) == 10  # the other five Arabic questions are new


def test_the_golden_twins_use_the_golden_texts():
    from evals.retrieval_eval import load_golden

    golden = {r["id"]: r["question"] for r in load_golden("institutions/demo-ccc/golden_questions.csv")}
    for p in pe.load_pairs():
        assert p["en_question"] == golden[p["en_id"]]
        if p["ar_id"]:
            assert p["ar_question"] == golden[p["ar_id"]]


def test_base_source_drops_only_the_chunk_suffix():
    assert pe.base_source("state-isac-map::03") == "state-isac-map"
    assert pe.base_source("programs:ccc-food-pantries") == "programs:ccc-food-pantries"
    assert pe.base_source("deadlines:x") == "deadlines:x"
    assert pe.base_source("") == ""


def test_answer_sources_are_distinct_documents_in_citation_order():
    assert pe.answer_sources(["a::01", "b::02", "a::05", "programs:p"]) == ["a", "b", "programs:p"]


def test_compare_same_different_and_error():
    ok = lambda *s: {"sources": list(s), "fallback": False}
    assert pe.compare(ok("a", "b"), ok("a", "c"))["status"] == "same"
    d = pe.compare(ok("a", "b"), ok("b", "a"))
    assert d["status"] == "different" and d["shared"] == ["a", "b"]
    assert pe.compare(ok(), ok())["status"] == "different"            # nothing cited is not parity
    assert pe.compare(ok("a"), {"sources": ["a"], "fallback": True})["status"] == "error"


def test_summarize_counts_and_the_target():
    row = lambda s: {"verdict": {"status": s}}
    s = pe.summarize([row("same")] * 12 + [row("different")] * 2 + [row("error")])
    assert (s["same_top"], s["errors"], s["passed"]) == (12, 1, True)
    assert pe.summarize([row("same")] * 11 + [row("different")] * 4)["passed"] is False


def fake_pairs(n=2):
    return [{"pair": f"p{i:02d}", "en_question": f"q{i}", "ar_question": f"س{i}"} for i in range(1, n + 1)]


def test_run_pairs_resumes_from_the_cache_and_retries_fallbacks():
    calls, cache, saved, failed_once = [], {}, [], []

    def runner(q, lang):
        calls.append(q)
        if q == "س2" and not failed_once:
            failed_once.append(1)
            return {"sources": [], "fallback": True, "seconds": 1}
        return {"sources": ["doc-" + q[0]], "fallback": False, "seconds": 1}

    rows = pe.run_pairs(fake_pairs(), runner, cache, save=lambda c: saved.append(dict(c)),
                        log=lambda *_: None)
    assert rows[1]["verdict"]["status"] == "error"
    assert "p02:ar" not in cache and "p01:en" in cache          # the fallback was not remembered
    calls.clear()
    rows = pe.run_pairs(fake_pairs(), runner, cache, log=lambda *_: None)
    assert calls == ["س2"]                                       # only the failed run is repeated
    assert rows[1]["verdict"]["status"] == "different"            # doc-q vs doc-س


def test_run_pairs_waits_between_real_runs_only():
    slept = []
    cache = {"p01:en": {"sources": ["a"], "fallback": False, "seconds": 0}}
    pe.run_pairs(fake_pairs(1), lambda q, l: {"sources": ["a"], "fallback": False, "seconds": 0},
                 cache, delay=5, sleep=slept.append, log=lambda *_: None)
    assert slept == [5]                                           # en was cached, only ar ran


def test_report_lists_totals_and_the_differences():
    pairs = fake_pairs(2)
    en = {"sources": ["a"], "fallback": False}
    rows = [{"pair": pairs[0], "en": en, "ar": en, "verdict": pe.compare(en, en)},
            {"pair": pairs[1], "en": en, "ar": {"sources": ["b"], "fallback": False},
             "verdict": pe.compare(en, {"sources": ["b"], "fallback": False})}]
    text = pe.render_report(rows, pe.summarize(rows, target=1), "answer", "2026-11-17")
    assert "1 of 2 pairs have the same top source" in text and "PASSED" in text
    assert "## Pairs that differ" in text and "AR cited: b" in text


def test_retrieval_runner_takes_the_best_hit_only():
    from types import SimpleNamespace

    hit = lambda cid, s: SimpleNamespace(chunk_id=cid, score=s)
    ctx = SimpleNamespace(retriever=SimpleNamespace(search=lambda q, k=8, **kw: [hit("x::01", 0.9), hit("y::02", 0.8)]))
    out = pe.retrieval_runner(ctx)("q", "en")
    assert out["sources"] == ["x"] and out["fallback"] is False


def test_run_stops_at_once_when_the_daily_token_limit_is_hit():
    import pytest

    calls = []

    def runner(q, lang):
        calls.append(q)
        return {"sources": [], "fallback": True, "answer": "Something went wrong (RateLimitError: ... "
                "tokens per day (TPD): Limit 200000 ... try again in 19m38s)"}

    with pytest.raises(pe.DailyLimitReached):
        pe.run_pairs(fake_pairs(3), runner, {}, log=lambda *_: None)
    assert len(calls) == 1                                        # no more wasted runs


# ---- retrieval mode keeps the top 5 documents so the pairs can be read more softly ----

def test_retrieval_runner_keeps_the_top_five_distinct_documents_with_scores():
    from types import SimpleNamespace

    hit = lambda cid, s: SimpleNamespace(chunk_id=cid, score=s)
    hits = [hit("a::01", .9), hit("a::02", .88), hit("b::01", .8), hit("c::03", .7),
            hit("d::01", .6), hit("e::01", .5), hit("f::01", .4)]
    ctx = SimpleNamespace(retriever=SimpleNamespace(search=lambda q, k=8, **kw: hits))
    out = pe.retrieval_runner(ctx)("q", "en")
    assert out["top5"] == [["a", .9], ["b", .8], ["c", .7], ["d", .6], ["e", .5]]


def test_compare_reads_the_top_five_overlap_and_the_soft_verdict():
    en = {"sources": ["a"], "fallback": False, "top5": [["a", .9], ["b", .8], ["c", .7]]}
    ar = {"sources": ["b"], "fallback": False, "top5": [["b", .9], ["x", .8], ["a", .7]]}
    v = pe.compare(en, ar)
    assert v["status"] == "different" and v["top5_overlap"] == 2 and v["soft_same"] is True
    far = {"sources": ["z"], "fallback": False, "top5": [["z", .9], ["y", .8]]}
    v2 = pe.compare(en, far)
    assert v2["top5_overlap"] == 0 and v2["soft_same"] is False
    assert "top5_overlap" not in pe.compare({"sources": ["a"], "fallback": False}, {"sources": ["a"], "fallback": False})


def test_report_shows_the_soft_reading_and_the_top_five_of_pairs_that_differ():
    pair = {"pair": "p9", "en_question": "Q?", "ar_question": "س؟"}
    en = {"sources": ["a"], "fallback": False, "top5": [["a", .9], ["b", .8]]}
    ar = {"sources": ["b"], "fallback": False, "top5": [["b", .85], ["a", .8]]}
    rows = [{"pair": pair, "en": en, "ar": ar, "verdict": pe.compare(en, ar)}]
    summary = pe.summarize(rows)
    assert summary["soft_same"] == 1 and summary["same_top"] == 0
    text = pe.render_report(rows, summary, "retrieval", "2026-11-23")
    assert "Softer reading" in text and "Top-5 shared" in text and "2/5" in text
    assert "EN top 5: a (0.9), b (0.8)" in text and "AR top 5: b (0.85), a (0.8)" in text
    # without top-5 data (answer mode) the report is as before
    plain = [{"pair": pair, "en": {"sources": ["a"], "fallback": False}, "ar": {"sources": ["b"], "fallback": False},
              "verdict": pe.compare({"sources": ["a"], "fallback": False}, {"sources": ["b"], "fallback": False})}]
    assert "Softer reading" not in pe.render_report(plain, pe.summarize(plain), "answer", "2026-11-23")


def test_show_run_prints_a_saved_run_and_says_when_one_is_missing(tmp_path, monkeypatch, capsys):
    import importlib.util
    import sys as _sys

    spec = importlib.util.spec_from_file_location("show_run", "scripts/show_run.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    (tmp_path / "r.json").write_text(json.dumps(
        {"p08:ar": {"sources": [], "confidence": "Low", "seconds": 12.5, "answer": "لم أجد"}}), encoding="utf-8")
    monkeypatch.setattr(mod, "RESULTS", tmp_path / "r.json")
    assert mod.main(["p08:ar", "p99:en"]) == 0
    out = capsys.readouterr().out
    assert "p08:ar" in out and "(none)" in out and "Low" in out and "لم أجد" in out
    assert "p99:en: not saved" in out


def test_redo_forgets_only_the_named_pairs_and_languages_and_the_report_says_so(tmp_path):
    cache = {"p03:en": {"x": 1}, "p03:ar": {"x": 2}, "p08:ar": {"x": 3}, "p01:en": {"x": 4}}
    assert pe.drop_cached(cache, ["p03", "p08", "p99"]) == ["p03", "p08"]
    assert list(cache) == ["p01:en"]
    cache = {"p01:en": 1, "p01:ar": 2, "p02:ar": 3}
    assert pe.drop_language(cache, "ar") == 2 and list(cache) == ["p01:en"]
    notes = tmp_path / "notes.txt"
    assert pe.read_notes(notes) == []
    pe.add_note("first note", notes)
    pe.add_note("first note", notes)          # no duplicates
    pe.add_note("second note", notes)
    assert pe.read_notes(notes) == ["first note", "second note"]
    pair = {"pair": "p1", "en_question": "Q?", "ar_question": "س؟"}
    run = {"sources": ["a"], "fallback": False}
    rows = [{"pair": pair, "en": run, "ar": run, "verdict": pe.compare(run, run)}]
    text = pe.render_report(rows, pe.summarize(rows), "answer", "2026-11-24", notes=pe.read_notes(notes))
    assert "- first note" in text and "- second note" in text and "favours the result" in text
    assert "favours the result" not in pe.render_report(rows, pe.summarize(rows), "answer", "2026-11-24")


def test_show_retrieval_prints_both_languages_of_a_pair_from_the_pairs_file(capsys):
    import importlib.util
    from types import SimpleNamespace

    spec = importlib.util.spec_from_file_location("show_retrieval", "scripts/show_retrieval.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    class Fake:
        def __init__(self):
            self.asked = []

        def search(self, q, k=5):
            self.asked.append((q, k))
            return [SimpleNamespace(score=0.8765, chunk_id="institution-ccc-tuition::02", section="Rates", text="word " * 50)]

    fake = Fake()
    assert mod.main(["p08", "-k", "3"], retriever=fake) == 0
    out = capsys.readouterr().out
    assert "=== p08 ===" in out and "[en]" in out and "[ar]" in out and "institution-ccc-tuition::02" in out
    assert [k for _, k in fake.asked] == [3, 3] and "كلفة الساعة" in fake.asked[1][0]
    assert mod.main(["p99"], retriever=fake) == 2
