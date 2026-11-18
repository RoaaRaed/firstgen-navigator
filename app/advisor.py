"""The bridge from the app to the Week 3 agent. No Streamlit in here.

The slow parts (the embedding model and the Chroma index) are loaded once and reused;
the page wraps `get_context` / `get_agent` in st.cache_resource."""
from __future__ import annotations

import threading
import time

INSTITUTION = "demo-ccc"
INSTITUTION_NAME = "City Colleges of Chicago"  # same text as core.agent.DEFAULT_INSTITUTION_NAME

_warm_lock = threading.Lock()
_warm_thread: threading.Thread | None = None


def get_context(institution: str = INSTITUTION):
    from core.tools import load_context

    return load_context(institution)


def get_ruleset(ctx):
    """The personalization rules (institutions/<name>/rules.yaml), validated on load."""
    from core.rules import load_rules

    return load_rules(ctx.root / "rules.yaml")


def ensure_index(ctx) -> bool:
    """Build the Chroma index if this machine has none; True if it had to.

    chroma_db/ is not in git (it is a build product), so a fresh machine such as Streamlit
    Community Cloud starts without it. Building takes about a minute: it embeds the knowledge
    base once, and the model it loads is the one the search needs anyway."""
    try:
        ctx.retriever  # loads the existing index
        return False
    except RuntimeError:
        pass
    from core import ingest

    ingest.main(["--kb", str(ctx.root / "kb"), "--db", ctx.db])
    ctx.retriever  # raises here if the build did not work
    return True


def warm_up(ctx) -> None:
    """Load the embedding model and the Chroma index in a background thread, once.

    The first search takes about 30 seconds (it loads the model). Starting that while the
    student is still filling in the questionnaire means their first question is not slow.
    A failure here is not fatal (the first real search will raise it where the page can show
    it), but it is printed to the terminal."""
    global _warm_thread
    with _warm_lock:
        if _warm_thread is not None:
            return

        def work():
            try:
                ensure_index(ctx)
                ctx.retriever.search("warm up", k=1)
            except Exception:
                import traceback

                traceback.print_exc()  # not fatal here, but the terminal should show why

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


def profile_for(ctx, answers: dict, language: str) -> str:
    """The background block about the student, built from their questionnaire answers and
    rules.yaml. "" if there are no answers. If the rules cannot be loaded the chat must still
    work, so any failure here gives "" (the student just gets an untailored answer)."""
    if not answers:
        return ""
    try:
        from app.profile_block import build_profile_block
        from app.strings import load_strings

        return build_profile_block(get_ruleset(ctx), load_strings("en"), answers, language)
    except Exception:
        return ""


def answer(agent, question: str, language: str, profile: str = ""):
    """Run one question. Returns (AgentResult, seconds). `profile` is the block from profile_for."""
    from core.agent import run_agent

    wait_for_warm_up()
    t0 = time.time()
    result = run_agent(agent, question, language=language, profile=profile)
    return result, time.time() - t0
