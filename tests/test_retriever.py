"""Retriever tests with a fake collection and embedder (no model, no database)."""
import math

import pytest

from core.retriever import Retriever, build_where, load_retriever


class FakeEmbedder:
    name = "fake"

    def embed_query(self, text):
        return [1.0, 0.0]


def _match(meta, where):
    if where is None:
        return True
    if "$and" in where:
        return all(_match(meta, w) for w in where["$and"])
    (k, v), = where.items()
    return meta[k] == v


class FakeCollection:
    metadata = {"embedder": "fake"}

    # (id, text, meta, vector)
    ROWS = [
        ("fed::00", "federal text", {"doc_id": "fed", "layer": "federal", "language": "en", "section": "S1"}, [1.0, 0.0]),
        ("state::00", "state text", {"doc_id": "state", "layer": "state", "language": "en", "section": "S2"}, [0.8, 0.6]),
        ("inst::00", "inst text", {"doc_id": "inst", "layer": "institution", "language": "en", "section": "S3"}, [0.0, 1.0]),
    ]

    def query(self, query_embeddings, n_results, include, where=None):
        q = query_embeddings[0]
        scored = []
        for cid, text, meta, vec in self.ROWS:
            if _match(meta, where):
                cos = sum(a * b for a, b in zip(q, vec)) / (math.hypot(*q) * math.hypot(*vec))
                scored.append((1 - cos, cid, text, meta))
        scored.sort(key=lambda r: r[0])
        scored = scored[:n_results]
        return {
            "ids": [[r[1] for r in scored]],
            "documents": [[r[2] for r in scored]],
            "metadatas": [[r[3] for r in scored]],
            "distances": [[r[0] for r in scored]],
        }


class FakeClient:
    def __init__(self, col=None):
        self.col = col

    def get_collection(self, name):
        if self.col is None:
            raise ValueError("does not exist")
        return self.col


def make():
    return Retriever(FakeCollection(), FakeEmbedder())


def test_build_where():
    assert build_where() is None
    assert build_where("state") == {"layer": "state"}
    assert build_where(language="ar") == {"language": "ar"}
    assert build_where("state", "en") == {"$and": [{"layer": "state"}, {"language": "en"}]}


def test_invalid_layer_is_rejected():
    with pytest.raises(ValueError):
        build_where("planet")


def test_results_are_ordered_by_score():
    hits = make().search("q", k=3)
    assert [h.chunk_id for h in hits] == ["fed::00", "state::00", "inst::00"]
    assert hits[0].score == pytest.approx(1.0)
    assert hits[1].score == pytest.approx(0.8)
    assert hits[0].doc_id == "fed" and hits[0].section == "S1"


def test_k_limits_results():
    assert len(make().search("q", k=2)) == 2


def test_threshold_drops_weak_hits():
    hits = make().search("q", k=3, threshold=0.5)
    assert [h.chunk_id for h in hits] == ["fed::00", "state::00"]
    assert make().search("q", k=3, threshold=1.1) == []


def test_layer_filter():
    hits = make().search("q", k=3, layer="state")
    assert [h.chunk_id for h in hits] == ["state::00"]


def test_layer_and_language_filter_together():
    assert make().search("q", layer="federal", language="en")[0].chunk_id == "fed::00"
    assert make().search("q", layer="federal", language="ar") == []


def test_empty_query_is_rejected():
    with pytest.raises(ValueError):
        make().search("   ")


def test_missing_index_gives_clear_error():
    with pytest.raises(RuntimeError, match="python -m core.ingest"):
        load_retriever(client=FakeClient(None), embedder=FakeEmbedder())


def test_wrong_embedder_gives_clear_error():
    col = FakeCollection()
    emb = FakeEmbedder()
    emb.name = "other"
    with pytest.raises(RuntimeError, match="--rebuild"):
        load_retriever(client=FakeClient(col), embedder=emb)


def test_load_retriever_ok():
    r = load_retriever(client=FakeClient(FakeCollection()), embedder=FakeEmbedder())
    assert r.search("q")[0].chunk_id == "fed::00"
