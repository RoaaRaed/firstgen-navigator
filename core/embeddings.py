"""The ONE place that knows which embedding model we use.

Everything else (ingest.py, retriever.py) talks to the small interface below.
To switch to an API model (the fallback in the brief), write another class with
the same three members and change get_embedder(). Nothing else changes.
"""
from __future__ import annotations

from typing import Protocol


class Embedder(Protocol):
    name: str  # saved with the index; if it changes, the index is rebuilt

    def embed_passages(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class E5Embedder:
    """intfloat/multilingual-e5-small: local, free, English + Arabic, runs on CPU."""

    name = "intfloat/multilingual-e5-small"

    def __init__(self) -> None:
        self._model = None

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # slow import, so lazy

            self._model = SentenceTransformer(self.name)
        return self._model

    # E5 needs these prefixes: "passage: " for documents, "query: " for questions.
    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        model = self._get_model()
        return model.encode(
            ["passage: " + t for t in texts],
            normalize_embeddings=True,
            batch_size=32,
            show_progress_bar=False,
        ).tolist()

    def embed_query(self, text: str) -> list[float]:
        model = self._get_model()
        return model.encode("query: " + text, normalize_embeddings=True).tolist()


def get_embedder() -> Embedder:
    return E5Embedder()
