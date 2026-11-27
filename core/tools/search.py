from __future__ import annotations

from core.retriever import LAYERS

SEARCH_K = 8          # Week 2: three of four misses were in the top 10, so we take 8, not 5
# How much of each passage the model gets to read. The first version cut EVERY passage to 150
# characters to stay under the free Groq tier's 8000-tokens-per-minute cap. The evaluation then
# showed the cost: the model could not see a number that sat after character 150 (the maximum
# Pell Grant), and it filled the gaps from general knowledge (invented steps and documents).
# Now the best-ranked passages are shown in much more detail and the rest stay short, which
# adds only about 300 tokens to a search while giving the model the text it must answer from.
TOP_PASSAGES = 4      # how many of the best-ranked passages get the long limit
MAX_CHARS_TOP = 600   # characters shown for each of those
MAX_CHARS = 150       # characters shown for the lower-ranked passages


def search_knowledge_base(ctx, query: str, language: str = "en", layer: str | None = None,
                          k: int = SEARCH_K) -> dict:
    """Search the official documents (federal, Illinois state, and college pages) for passages
    that answer the student's question. Use it for any question about how something works,
    who is eligible, what steps to take, or what a term means.

    Args:
        query: a short search phrase IN ENGLISH, because the documents are English. If the
            student wrote Arabic, translate the question first (Arabic queries match worse).
        language: the language of the student's question ("en" or "ar"). Documents in any
            language are searched, because the search model understands both.
        layer: optional filter: "federal", "state" or "institution". Leave empty unless the
            question is clearly about one level.
        k: how many passages to return.

    Returns: {"found": bool, "results": [...]}. Each result has a "source_id" (cite it exactly),
    the document title, section, layer, source_url, retrieved_date, effective_term and text.
    Prefer newer documents when two passages disagree, and say that they disagree.
    """
    if layer in ("", "none", "all"):
        layer = None
    if layer is not None and layer not in LAYERS:
        return {"found": False, "error": f"layer must be one of {list(LAYERS)} or empty", "results": []}
    if not (query or "").strip():
        return {"found": False, "error": "query is empty", "results": []}

    hits = ctx.retriever.search(query, k=k, layer=layer)
    results = []
    for rank, h in enumerate(hits):
        m = h.metadata
        text = " ".join(h.text.split())
        limit = MAX_CHARS_TOP if rank < TOP_PASSAGES else MAX_CHARS
        results.append({
            "source_id": h.chunk_id,
            "title": m.get("title", ""),
            "section": m.get("section", ""),
            "layer": m.get("layer", ""),
            "source_url": m.get("source_url", ""),
            "retrieved_date": m.get("retrieved_date", ""),
            "effective_term": m.get("effective_term", "") or "not stated",
            "score": round(float(h.score), 3),
            "text": text if len(text) <= limit else text[:limit] + " ...",
        })
    return {"found": bool(results), "query": query, "language": language,
            "layer": layer or "all", "results": results}
