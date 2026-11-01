"""Search the knowledge base: embed the question, find the closest chunks.

    python -m core.retriever "What is the MAP grant?"
    python -m core.retriever "ما هي منحة MAP؟" --layer state -k 5
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

from core.embeddings import Embedder, get_embedder

LAYERS = ("federal", "state", "institution")
DEFAULT_K = 5
# Chunks scoring below this are dropped. 0.0 keeps everything for now:
# we pick the real value from the golden-set numbers (Gate 1 tuning).
DEFAULT_THRESHOLD = 0.0


@dataclass
class Hit:
    chunk_id: str      # citation identifier, e.g. "state-isac-map::03"
    doc_id: str        # the document it came from, e.g. "state-isac-map"
    score: float       # cosine similarity, higher is closer (max 1.0)
    text: str
    metadata: dict

    @property
    def section(self) -> str:
        return self.metadata.get("section", "")


def build_where(layer: str | None = None, language: str | None = None):
    """Chroma metadata filter. 'language' is the DOCUMENT's language, not the question's."""
    if layer is not None and layer not in LAYERS:
        raise ValueError(f"layer must be one of {LAYERS}, got {layer!r}")
    conds = []
    if layer:
        conds.append({"layer": layer})
    if language:
        conds.append({"language": language})
    if not conds:
        return None
    return conds[0] if len(conds) == 1 else {"$and": conds}


class Retriever:
    def __init__(self, collection, embedder: Embedder, threshold: float = DEFAULT_THRESHOLD):
        self.collection = collection
        self.embedder = embedder
        self.threshold = threshold

    def search(self, query: str, k: int = DEFAULT_K, layer: str | None = None,
               language: str | None = None, threshold: float | None = None) -> list[Hit]:
        query = (query or "").strip()
        if not query:
            raise ValueError("query must not be empty")
        where = build_where(layer, language)
        kwargs = {"where": where} if where else {}
        res = self.collection.query(
            query_embeddings=[self.embedder.embed_query(query)],
            n_results=k,
            include=["documents", "metadatas", "distances"],
            **kwargs,
        )
        limit = self.threshold if threshold is None else threshold
        hits = []
        for cid, doc, meta, dist in zip(res["ids"][0], res["documents"][0],
                                        res["metadatas"][0], res["distances"][0]):
            score = 1.0 - dist  # the collection uses cosine distance
            if score >= limit:
                hits.append(Hit(cid, meta["doc_id"], score, doc, meta))
        return hits


def load_retriever(institution: str = "demo-ccc", db: str = "chroma_db",
                   embedder: Embedder | None = None, client=None,
                   threshold: float = DEFAULT_THRESHOLD) -> Retriever:
    embedder = embedder or get_embedder()
    if client is None:
        import chromadb

        client = chromadb.PersistentClient(path=db)
    try:
        collection = client.get_collection(institution)
    except Exception as e:
        raise RuntimeError(
            f"No index named '{institution}' in '{db}'. Run:  python -m core.ingest"
        ) from e
    stored = (collection.metadata or {}).get("embedder")
    if stored != embedder.name:
        raise RuntimeError(
            f"The index was built with '{stored}' but the code uses '{embedder.name}'. "
            "Run:  python -m core.ingest --rebuild"
        )
    return Retriever(collection, embedder, threshold)


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Search the knowledge base.")
    ap.add_argument("query")
    ap.add_argument("-k", type=int, default=DEFAULT_K)
    ap.add_argument("--layer", choices=LAYERS)
    ap.add_argument("--institution", default="demo-ccc")
    ap.add_argument("--db", default="chroma_db")
    args = ap.parse_args(argv)
    retriever = load_retriever(args.institution, args.db)
    hits = retriever.search(args.query, k=args.k, layer=args.layer)
    print(f"Q: {args.query}  (layer filter: {args.layer or 'none'})")
    for i, h in enumerate(hits, 1):
        snippet = " ".join(h.text.split())[:110]
        print(f"{i}. {h.score:.3f}  [{h.chunk_id}]  {h.section}")
        print(f"     {snippet}")
    if not hits:
        print("(no results above the threshold)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
