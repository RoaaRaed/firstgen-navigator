import datetime as dt
import importlib.util
from pathlib import Path

import pytest

from core import admin, config
from core.tools import load_context

spec = importlib.util.spec_from_file_location("new_institution", Path("scripts/new_institution.py"))
ni = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ni)

T0 = dt.datetime(2026, 12, 1, 9, 0)


@pytest.fixture
def root(tmp_path):
    """A copy of just what the scaffold needs from the template institution."""
    (tmp_path / "demo-ccc").mkdir()
    (tmp_path / "demo-ccc" / "handoffs.yaml").write_text(
        Path("institutions/demo-ccc/handoffs.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


# ---- config

def test_active_institution_defaults_and_rejects_bad_names():
    assert config.active_institution({}) == "demo-ccc"
    assert config.active_institution({"INSTITUTION": " uic "}) == "uic"
    for bad in ("../etc", "UIC", "a b", "-x"):
        with pytest.raises(ValueError):
            config.active_institution({"INSTITUTION": bad})


def test_the_real_demo_config_loads():
    cfg = config.load_config("demo-ccc")
    assert cfg.name == "City Colleges of Chicago" and cfg.default_language == "en"


def test_config_errors_are_readable(tmp_path):
    (tmp_path / "x").mkdir()
    with pytest.raises(ValueError, match="new_institution.py"):
        config.load_config("x", tmp_path)
    (tmp_path / "x" / "config.yaml").write_text("name: A\nnmae: typo\n", encoding="utf-8")
    with pytest.raises(ValueError, match="nmae"):
        config.load_config("x", tmp_path)
    (tmp_path / "x" / "config.yaml").write_text("name: ' '\n", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        config.load_config("x", tmp_path)


# ---- the scaffold

def test_a_new_institution_loads_with_no_code_change(root):
    base = ni.create("uic", "University of Illinois Chicago", root, now=T0, website="https://www.uic.edu")
    assert config.load_config("uic", root).name == "University of Illinois Chicago"
    ctx = load_context("uic", root=str(root))
    assert ctx.deadlines == [] and [p.id for p in ctx.programs] == ["uic-student-services"]
    assert all(t["program"] == "uic-student-services" for t in ctx.handoffs["topics"].values())
    assert any(t.get("sensitive") for t in ctx.handoffs["topics"].values())     # the gentle-tone flag is kept
    from core.rules import load_rules
    assert load_rules(base / "rules.yaml").rules == []
    assert (base / "kb").is_dir() and admin.list_institutions(root) == ["uic"]


def test_escalate_names_the_placeholder_office_for_every_topic(root):
    ni.create("uic", "UIC", root, now=T0)
    from core.tools.escalate import escalate_to_human
    ctx = load_context("uic", root=str(root))
    out = escalate_to_human(ctx, "immigration")
    assert out["sensitive"] is True and out["contacts"][0]["source_id"] == "programs:uic-student-services"


def test_create_refuses_a_second_time_and_bad_names(root):
    ni.create("uic", "UIC", root, now=T0)
    with pytest.raises(ValueError, match="already"):
        ni.create("uic", "UIC", root, now=T0)
    with pytest.raises(ValueError, match="lowercase"):
        ni.create("Bad Name", "X", root, now=T0)


def test_the_timer_measures_the_setup(root):
    ni.create("uic", "UIC", root, now=T0)
    sentence = ni.finish("uic", root, now=T0 + dt.timedelta(hours=2, minutes=5))
    assert "2 h 5 min" in sentence
    assert "within the target" in (root / "uic" / "SETUP_TIME.md").read_text(encoding="utf-8")
    ni.finish("uic", root, now=T0 + dt.timedelta(hours=5))
    assert "OVER" in (root / "uic" / "SETUP_TIME.md").read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="start"):
        ni.finish("nope", root)


def test_an_empty_knowledge_base_is_explained_not_a_crash(tmp_path, capsys):
    from core import ingest
    (tmp_path / "kb").mkdir()
    assert ingest.main(["--kb", str(tmp_path / "kb")]) == 0
    assert "No documents" in capsys.readouterr().out


# ---- the app reads the setting

def test_the_app_uses_the_configured_institution(monkeypatch):
    from app import advisor

    monkeypatch.setenv("INSTITUTION", "demo-ccc")
    assert advisor.institution_slug() == "demo-ccc" and advisor.institution_name() == "City Colleges of Chicago"


def test_institution_is_one_of_the_settings_copied_from_secrets():
    from app.secrets_env import KEYS
    assert "INSTITUTION" in KEYS


def test_an_institution_name_with_a_comma_still_makes_a_valid_table(root):
    ni.create("odd", "College of Arts, Letters and Science", root, now=T0)
    ctx = load_context("odd", root=str(root))
    assert ctx.programs[0].institution == "College of Arts, Letters and Science"
