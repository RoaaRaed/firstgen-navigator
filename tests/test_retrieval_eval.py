"""Tests for the retrieval evaluation logic with a fake retriever (no model, no database)."""
from pathlib import Path

from core.retriever import Hit
from evals.retrieval_eval import (
    LayeredRetriever,
    evaluate,
    gate_verdict,
    hit_rate,
    kb_ids,
    load_golden,
    render_report,
    threshold_table,
)

GOLDEN = Path("institutions/demo-ccc/golden_questions.csv")
KB = Path("institutions/demo-ccc/kb")


def row(qid, lang, behavior, ids, q=None):
    return {"id": qid, "language": lang, "expected_behavior": behavior,
            "question": q or f"question {qid}", "expected_source_ids": ";".join(ids)}


class FakeRetriever:
    """Returns a fixed ranked list of (doc_id, score) for each question text."""

    def __init__(self, table):
        self.table = table

    def search(self, query, k=5, threshold=None, **kw):
        return [Hit(f"{d}::00", d, s, "text", {"doc_id": d}) for d, s in self.table[query][:k]]


def test_kb_ids_ignores_table_ids():
    r = row("g1", "en", "grounded", ["state-isac-map", "deadlines:x", "programs:y"])
    assert kb_ids(r) == {"state-isac-map"}


def test_rank_and_hit_at_5():
    rows = [row("g1", "en", "grounded", ["a"], "q1"), row("g2", "en", "grounded", ["b"], "q2")]
    fr = FakeRetriever({
        "q1": [("x", .9), ("a", .8), ("y", .7)],
        "q2": [("x", .9), ("y", .8), ("z", .7), ("w", .6), ("v", .5), ("b", .4)],  # rank 6
    })
    res = evaluate(rows, fr)
    assert res[0].rank == 2 and res[1].rank == 6
    assert hit_rate(res, "en", 5) == (1, 2)  # rank 6 is a near miss, not a hit


def test_unanswerable_and_table_only_rows_are_not_scored():
    rows = [row("g1", "en", "refuse", ["a"], "q1"),
            row("g2", "en", "grounded", ["deadlines:x"], "q2"),
            row("g3", "en", "grounded", ["a"], "q3")]
    fr = FakeRetriever({"q1": [("a", .9)], "q2": [("a", .9)], "q3": [("a", .9)]})
    assert hit_rate(evaluate(rows, fr), "en") == (1, 1)


def test_gate_verdict_uses_different_targets_per_language():
    rows = [row(f"e{i}", "en", "grounded", ["a"], f"qe{i}") for i in range(5)]
    rows += [row(f"a{i}", "ar", "grounded", ["a"], f"qa{i}") for i in range(10)]
    table = {f"qe{i}": [("a", .9)] for i in range(5)}
    table["qe4"] = [("zzz", .9)]                      # English 4/5 = 80% passes
    table.update({f"qa{i}": [("a", .9)] for i in range(10)})
    for i in range(4):                                 # Arabic 6/10 = 60% fails
        table[f"qa{i}"] = [("zzz", .9)]
    v = gate_verdict(evaluate(rows, FakeRetriever(table)))
    assert v["en"]["pass"] and not v["ar"]["pass"] and not v["pass"]


def test_threshold_table_counts_empty_results_for_unanswerable():
    rows = [row("g1", "en", "grounded", ["a"], "q1"), row("g2", "en", "not_found", [], "q2")]
    fr = FakeRetriever({"q1": [("a", .86)], "q2": [("b", .83)]})
    t = {e["threshold"]: e for e in threshold_table(evaluate(rows, fr), thresholds=(0.0, 0.85, 0.9))}
    assert t[0.0]["en"] == (1, 1) and t[0.0]["empty"] == (0, 1)
    assert t[0.85]["en"] == (1, 1) and t[0.85]["empty"] == (1, 1)  # the good threshold
    assert t[0.9]["en"] == (0, 1)


def test_report_mentions_gate_and_misses():
    rows = [row("g1", "en", "grounded", ["a"], "q1"), row("g2", "ar", "grounded", ["a"], "q2")]
    fr = FakeRetriever({"q1": [("a", .9)], "q2": [("zzz", .9)]})
    text = render_report(evaluate(rows, fr), "fake-model")
    assert "Gate 1" in text and "g2" in text and "Threshold study" in text


def test_golden_file_matches_real_kb():
    rows = load_golden(GOLDEN)
    assert len(rows) >= 40
    stems = {p.stem for p in KB.glob("*.md")}
    for r in rows:
        assert kb_ids(r) <= stems, f"{r['id']} expects a document that does not exist"


class LayerFake:
    """Fake retriever that honours the layer filter. Rows: (doc_id, layer, score)."""

    ROWS = [("fed1", "federal", .90), ("fed2", "federal", .89), ("fed3", "federal", .88),
            ("st1", "state", .80), ("st2", "state", .79), ("in1", "institution", .70)]

    def search(self, query, k=5, layer=None, threshold=None, **kw):
        rows = [r for r in self.ROWS if layer is None or r[1] == layer]
        rows.sort(key=lambda r: -r[2])
        return [Hit(f"{d}::00", d, s, "t", {"doc_id": d, "layer": L}) for d, L, s in rows[:k]]


def test_plain_search_lets_one_layer_crowd_out_the_others():
    docs = [h.doc_id for h in LayerFake().search("q", k=3)]
    assert docs == ["fed1", "fed2", "fed3"]


def test_layered_search_gives_every_layer_a_slot():
    docs = [h.doc_id for h in LayeredRetriever(LayerFake()).search("q", k=5)]
    assert docs[:3] == ["fed1", "st1", "in1"]      # best of each layer, ordered by score
    assert docs[3:] == ["fed2", "fed3"] or docs[3:] == ["fed2", "st2"]
    assert len(docs) == 5 and len(set(docs)) == 5


def test_layered_search_respects_threshold():
    docs = [h.doc_id for h in LayeredRetriever(LayerFake()).search("q", k=5, threshold=0.85)]
    assert docs == ["fed1", "fed2", "fed3"]
