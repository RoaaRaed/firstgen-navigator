"""Where does the time go? Times each phase of one question so we can see what is slow.

    python -m scripts.time_phases
"""
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_last = time.time()


def lap(label: str) -> None:
    global _last
    now = time.time()
    print(f"{now - _last:7.1f}s  {label}", flush=True)
    _last = now


def main() -> int:
    from dotenv import load_dotenv

    load_dotenv()
    lap("start")

    import core.agent as agent
    from core.tools import load_context, search_knowledge_base

    lap("imports (langchain, groq, ...)")

    ctx = load_context("demo-ccc")
    lap("load_context (csv/yaml files)")

    search_knowledge_base(ctx, "Illinois MAP grant")
    lap("first search (loads the embedding model + Chroma)")

    search_knowledge_base(ctx, "food help on campus")
    lap("second search (should be fast)")

    llm = agent.get_llm()
    lap("create the Groq client")

    llm.invoke("Reply with one word: hello")
    lap("Groq call 1 (tiny prompt)")

    llm.invoke("Reply with one word: hello")
    lap("Groq call 2 (tiny prompt)")

    print("\nDone. Send me this whole table.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
