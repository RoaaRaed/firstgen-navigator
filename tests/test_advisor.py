"""Tests for the background warm-up in app/advisor.py (no model, no network)."""
import threading
import time
from types import SimpleNamespace

import pytest

from app import advisor


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    monkeypatch.setattr(advisor, "_warm_thread", None)


def fake_ctx(searches, delay=0.0):
    def search(query, k):
        time.sleep(delay)
        searches.append((query, threading.current_thread().name))
    return SimpleNamespace(retriever=SimpleNamespace(search=search))


def test_warm_up_runs_one_search_in_a_background_thread():
    searches = []
    advisor.warm_up(fake_ctx(searches))
    advisor.wait_for_warm_up()
    assert searches == [("warm up", "warm-up")]


def test_warm_up_only_starts_once_even_if_called_on_every_rerun():
    searches = []
    ctx = fake_ctx(searches)
    for _ in range(5):
        advisor.warm_up(ctx)
    advisor.wait_for_warm_up()
    assert len(searches) == 1


def test_warm_up_does_not_block_the_caller():
    searches = []
    t0 = time.time()
    advisor.warm_up(fake_ctx(searches, delay=0.5))
    assert time.time() - t0 < 0.3 and searches == []
    advisor.wait_for_warm_up()
    assert len(searches) == 1


def test_wait_for_warm_up_returns_at_once_when_nothing_is_running():
    t0 = time.time()
    advisor.wait_for_warm_up()
    assert time.time() - t0 < 0.1


def test_a_failing_warm_up_is_swallowed():
    def boom(query, k):
        raise RuntimeError("no index")

    advisor.warm_up(SimpleNamespace(retriever=SimpleNamespace(search=boom)))
    advisor.wait_for_warm_up()  # must not raise


def test_answer_waits_for_the_warm_up_before_asking(monkeypatch):
    from tests.fake_langchain import install

    install()
    import core.agent as agent_mod

    order = []
    advisor.warm_up(fake_ctx(order, delay=0.3))
    monkeypatch.setattr(agent_mod, "run_agent", lambda a, q, language="en", profile="": order.append("asked") or "result")
    advisor.answer(object(), "hi", "en")
    assert [o[0] if isinstance(o, tuple) else o for o in order] == ["warm up", "asked"]
