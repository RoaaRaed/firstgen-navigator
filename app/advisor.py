"""The bridge from the app to the Week 3 agent. No Streamlit in here.

The slow parts (the embedding model and the Chroma index) are loaded once and reused;
the page wraps `get_context` / `get_agent` in st.cache_resource."""
from __future__ import annotations

import threading
import time

INSTITUTION = "demo-ccc"

_warm_lock = threading.Lock()
_warm_thread: threading.Thread | None = None


def get_context(institution: str = INSTITUTION):
    from core.tools import load_context

    return load_context(institution)


def warm_up(ctx) -> None:
    """Load the embedding model and the Chroma index in a background thread, once.

    The first search takes about 30 seconds (it loads the model). Starting that while the
    student is still filling in the questionnaire means their first question is not slow.
    A failure here is ignored on purpose: the first real search will raise it where the page
    can show it."""
    global _warm_thread
    with _warm_lock:
        if _warm_thread is not None:
            return

        def work():
            try:
                ctx.retriever.search("warm up", k=1)
            except Exception:
                pass

        _warm_thread = threading.Thread(target=work, name="warm-up", daemon=True)
        _warm_thread.start()


def wait_for_warm_up(timeout: float = 300) -> None:
    """If the warm-up is still running, wait for it, so two threads never load the model at once."""
    thread = _warm_thread
    if thread is not None and thread.is_alive():
        thread.join(timeout)


def get_agent(ctx, language: str):
    from core.agent import build_agent

    return build_agent(ctx, language=language)


def answer(agent, question: str, language: str):
    """Run one question. Returns (AgentResult, seconds)."""
    from core.agent import run_agent

    wait_for_warm_up()
    t0 = time.time()
    result = run_agent(agent, question, language=language)
    return result, time.time() - t0
