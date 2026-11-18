"""Pieces the first deployment needs: the index is built when a fresh machine has none, the
Groq key is read from Streamlit secrets, and the daily limit gets its own message."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import advisor, render
from app.secrets_env import export_secrets
from core.agent import _safe_fallback
from core.schema import AdvisorAnswer


class FakeCtx:
    """The retriever raises the 'no index' error until the build has run."""

    def __init__(self, built=False):
        self.root, self.db, self.built = Path("institutions/demo-ccc"), "chroma_db", built

    @property
    def retriever(self):
        if not self.built:
            raise RuntimeError("No index named 'demo-ccc' in 'chroma_db'. Run:  python -m core.ingest")
        return object()


def test_ensure_index_does_nothing_when_the_index_exists(monkeypatch):
    from core import ingest

    monkeypatch.setattr(ingest, "main", lambda argv: pytest.fail("must not rebuild"))
    assert advisor.ensure_index(FakeCtx(built=True)) is False


def test_ensure_index_builds_it_on_a_fresh_machine(monkeypatch):
    from core import ingest

    ctx, calls = FakeCtx(), []
    monkeypatch.setattr(ingest, "main", lambda argv: calls.append(argv) or setattr(ctx, "built", True) or 0)
    assert advisor.ensure_index(ctx) is True
    assert calls == [["--kb", str(Path("institutions/demo-ccc/kb")), "--db", "chroma_db"]]


def test_ensure_index_raises_if_the_build_did_not_work(monkeypatch):
    from core import ingest

    monkeypatch.setattr(ingest, "main", lambda argv: 0)  # builds nothing
    with pytest.raises(RuntimeError):
        advisor.ensure_index(FakeCtx())


def test_export_secrets_copies_only_missing_known_keys():
    env = {"GROQ_MODEL": "already-set"}
    secrets = {"GROQ_API_KEY": "k123", "GROQ_MODEL": "other", "SOMETHING_ELSE": "x"}
    assert export_secrets(secrets, env) == ["GROQ_API_KEY"]
    assert env == {"GROQ_MODEL": "already-set", "GROQ_API_KEY": "k123"}


def test_export_secrets_survives_a_missing_secrets_file():
    class NoSecrets:
        def __getitem__(self, key):
            raise FileNotFoundError("no secrets.toml")

    env = {}
    assert export_secrets(NoSecrets(), env) == [] and env == {}


def test_secrets_example_file_is_valid_toml_and_has_the_key():
    import tomllib

    data = tomllib.loads(open(".streamlit/secrets.toml.example", encoding="utf-8").read())
    assert "GROQ_API_KEY" in data


def test_the_daily_limit_fallback_is_recognised_and_a_minute_one_is_not():
    daily = _safe_fallback("RateLimitError: Error code: 429 ... on tokens per day (TPD): Limit 200000")
    minute = _safe_fallback("RateLimitError: Error code: 429 ... on tokens per minute (TPM)")
    assert render.is_daily_limit_fallback(daily) and not render.is_daily_limit_fallback(minute)
    ok = AdvisorAnswer(answer="Fine. tokens per day is a phrase", confidence="Low")
    assert not render.is_daily_limit_fallback(ok)
    msg = render.assistant_message(SimpleNamespace(answer=daily, tool_calls=[]), 1.0)
    assert msg["fallback"] and msg["daily_limit"]


@pytest.mark.parametrize("lang", ["en", "ar"])
def test_both_languages_have_the_daily_limit_text(lang):
    from app import strings

    text = strings.t(strings.load_strings(lang), "chat.daily_limit")
    assert text != "chat.daily_limit" and len(text) > 20
