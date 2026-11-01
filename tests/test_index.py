"""Tests for the indexing logic using a fake Chroma and a fake embedder (no model needed)."""
from pathlib import Path

from core.ingest import chunk_document, open_collection, sync_index

FRONT = """---
title: "Doc {n}"
source_url: https://example.org/{n}
layer: state
audience: [all]
retrieved_date: 2026-10-28
---

"""


class FakeCollection:
    def __init__(self, metadata=None):
        self.metadata = metadata or {}
        self.rows = {}  # id -> (document, metadata)

    def get(self, include=None):
        return {"ids": list(self.rows), "metadatas": [m for _, m in self.rows.values()]}

    def add(self, ids, documents, embeddings, metadatas):
        assert len(ids) == len(documents) == len(embeddings) == len(metadatas)
        for i, d, m in zip(ids, documents, metadatas):
            assert i not in self.rows, f"duplicate id {i}"
            self.rows[i] = (d, m)

    def delete(self, where):
        (k, v), = where.items()
        self.rows = {i: r for i, r in self.rows.items() if r[1][k] != v}

    def count(self):
        return len(self.rows)


class FakeClient:
    def __init__(self):
        self.cols = {}

    def get_or_create_collection(self, name, metadata=None):
        return self.cols.setdefault(name, FakeCollection(metadata))

    def delete_collection(self, name):
        self.cols.pop(name, None)


class FakeEmbedder:
    name = "fake-embedder"

    def __init__(self):
        self.embedded = 0

    def embed_passages(self, texts):
        self.embedded += len(texts)
        return [[float(len(t)), 0.0] for t in texts]

    def embed_query(self, text):
        return [float(len(text)), 0.0]


def make_doc(tmp_path, n, body):
    p = tmp_path / f"doc{n}.md"
    p.write_bytes((FRONT.format(n=n) + body).encode("utf-8"))
    return p


def chunks_for(tmp_path):
    out = []
    for p in sorted(tmp_path.glob("*.md")):
        out.extend(chunk_document(p))
    return out


def test_first_run_adds_everything(tmp_path):
    make_doc(tmp_path, 1, "## A\n\n" + "alpha " * 80)
    make_doc(tmp_path, 2, "## B\n\n" + "beta " * 80)
    col, emb = FakeCollection(), FakeEmbedder()
    stats = sync_index(chunks_for(tmp_path), col, emb)
    assert stats["added"] == 2 and stats["unchanged"] == 0
    assert col.count() == emb.embedded == 2


def test_second_run_embeds_nothing(tmp_path):
    make_doc(tmp_path, 1, "## A\n\n" + "alpha " * 80)
    col, emb = FakeCollection(), FakeEmbedder()
    sync_index(chunks_for(tmp_path), col, emb)
    before = emb.embedded
    stats = sync_index(chunks_for(tmp_path), col, emb)
    assert stats["unchanged"] == 1 and stats["added"] == 0 and stats["updated"] == 0
    assert emb.embedded == before


def test_changed_file_is_reindexed_and_others_are_not(tmp_path):
    make_doc(tmp_path, 1, "## A\n\n" + "alpha " * 80)
    make_doc(tmp_path, 2, "## B\n\n" + "beta " * 80)
    col, emb = FakeCollection(), FakeEmbedder()
    sync_index(chunks_for(tmp_path), col, emb)
    before = emb.embedded
    make_doc(tmp_path, 2, "## B\n\n" + "beta changed " * 80)
    stats = sync_index(chunks_for(tmp_path), col, emb)
    assert stats["updated"] == 1 and stats["unchanged"] == 1
    assert emb.embedded == before + 1
    assert "changed" in " ".join(d for d, _ in col.rows.values())


def test_deleted_file_is_removed_from_index(tmp_path):
    make_doc(tmp_path, 1, "## A\n\n" + "alpha " * 80)
    p2 = make_doc(tmp_path, 2, "## B\n\n" + "beta " * 80)
    col, emb = FakeCollection(), FakeEmbedder()
    sync_index(chunks_for(tmp_path), col, emb)
    p2.unlink()
    stats = sync_index(chunks_for(tmp_path), col, emb)
    assert stats["removed"] == 1 and col.count() == 1


def test_half_indexed_document_is_repaired(tmp_path):
    make_doc(tmp_path, 1, "## A\n\n" + "alpha " * 400)  # several chunks
    chunks = chunks_for(tmp_path)
    assert len(chunks) > 1
    col, emb = FakeCollection(), FakeEmbedder()
    sync_index(chunks, col, emb)
    first = next(iter(col.rows))
    col.rows.pop(first)  # simulate a crash that lost a chunk
    stats = sync_index(chunks, col, emb)
    assert stats["updated"] == 1 and col.count() == len(chunks)


def test_different_embedder_rebuilds_collection():
    client, emb = FakeClient(), FakeEmbedder()
    col = open_collection(client, "demo", emb)
    col.add(["x"], ["t"], [[0.0]], [{"doc_id": "d", "file_hash": "h"}])
    emb.name = "another-model"
    col2 = open_collection(client, "demo", emb)
    assert col2.count() == 0
    assert col2.metadata["embedder"] == "another-model"


def test_rebuild_flag_empties_collection():
    client, emb = FakeClient(), FakeEmbedder()
    col = open_collection(client, "demo", emb)
    col.add(["x"], ["t"], [[0.0]], [{"doc_id": "d", "file_hash": "h"}])
    assert open_collection(client, "demo", emb).count() == 1
    assert open_collection(client, "demo", emb, rebuild=True).count() == 0
