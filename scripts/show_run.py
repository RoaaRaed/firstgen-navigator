"""Print saved parity runs (evals/parity_results.json) so a pair can be read in full.

    python scripts/show_run.py p08:ar p11:en
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RESULTS = Path("evals/parity_results.json")


def describe(key: str, run: dict | None) -> str:
    if run is None:
        return f"{key}: not saved (it has not run yet, or it ended in an error)"
    return (f"{key}\n  sources: {', '.join(run.get('sources', [])) or '(none)'}"
            f"\n  confidence: {run.get('confidence', '-')}   seconds: {run.get('seconds', '-')}"
            f"\n  answer: {run.get('answer', '')}\n")


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    keys = (argv if argv is not None else sys.argv[1:])
    if not keys:
        print("usage: python scripts/show_run.py p08:ar p11:en")
        return 2
    data = json.loads(RESULTS.read_text(encoding="utf-8")) if RESULTS.exists() else {}
    for k in keys:
        print(describe(k, data.get(k)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
