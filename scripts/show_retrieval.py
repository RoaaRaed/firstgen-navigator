"""Show what the search finds for the English and Arabic question of a parity pair - no Groq, no quota.

    python scripts/show_retrieval.py p08
    python scripts/show_retrieval.py p03 p08 -k 6

The questions are read from the pairs file, so no Arabic has to be typed in the terminal.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.parity_eval import load_pairs  # noqa: E402


def show(retriever, pair: dict, k: int, out=print) -> None:
    out(f"=== {pair['pair']} ===")
    for lang in ("en", "ar"):
        question = pair[f"{lang}_question"]
        out(f"\n[{lang}] {question}")
        hits = retriever.search(question, k=k)
        for i, h in enumerate(hits, 1):
            snippet = " ".join(h.text.split())[:90]
            out(f"  {i}. {h.score:.3f}  {h.chunk_id}  ({h.section})")
            out(f"       {snippet}")
        if not hits:
            out("  (no results)")
    out("")


def main(argv=None, retriever=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Search results for parity pairs.")
    ap.add_argument("pairs", nargs="+", metavar="PAIR", help="e.g. p08")
    ap.add_argument("-k", type=int, default=5)
    args = ap.parse_args(argv)
    by_id = {p["pair"]: p for p in load_pairs()}
    unknown = [p for p in args.pairs if p not in by_id]
    if unknown:
        print("Unknown pair(s):", ", ".join(unknown))
        return 2
    if retriever is None:
        from core.retriever import load_retriever

        retriever = load_retriever("demo-ccc", "chroma_db")
    for p in args.pairs:
        show(retriever, by_id[p], args.k)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
