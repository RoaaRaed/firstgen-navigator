"""Try each tool from the command line and see exactly what the agent will receive.

    python -m core.tools search "Can I get state aid without the FAFSA?"
    python -m core.tools deadlines --term "Spring 2027" --topic drop
    python -m core.tools programs --tags caregiver --categories food childcare
    python -m core.tools escalate immigration
"""
import argparse
import json
import sys

from core.tools import (escalate_to_human, load_context, lookup_deadlines, match_programs,
                        search_knowledge_base)


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Run one advisor tool.")
    sub = ap.add_subparsers(dest="tool", required=True)
    s = sub.add_parser("search"); s.add_argument("query"); s.add_argument("--layer"); s.add_argument("--language", default="en")
    d = sub.add_parser("deadlines"); d.add_argument("--term", default=""); d.add_argument("--topic", default="")
    p = sub.add_parser("programs"); p.add_argument("--tags", nargs="*", default=[]); p.add_argument("--categories", nargs="*", default=[]); p.add_argument("--keywords", default="")
    e = sub.add_parser("escalate"); e.add_argument("topic")
    args = ap.parse_args(argv)

    ctx = load_context()
    if args.tool == "search":
        out = search_knowledge_base(ctx, args.query, language=args.language, layer=args.layer)
        for r in out["results"]:  # long texts: show a short preview on screen
            r["text"] = r["text"][:160] + " ..."
    elif args.tool == "deadlines":
        out = lookup_deadlines(ctx, term=args.term, topic=args.topic)
    elif args.tool == "programs":
        out = match_programs(ctx, tags=args.tags, categories=args.categories, keywords=args.keywords)
    else:
        out = escalate_to_human(ctx, args.topic)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
