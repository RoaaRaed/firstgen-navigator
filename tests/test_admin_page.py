"""Smoke test of the Admin page with a stand-in for Streamlit (no browser)."""
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from core import admin

DOC_META_OK = "# Late Registration\n\nYou can register late until the second week."


def fake_st(state=None, clicked=(), upload=None, typed="", secrets=None, url="https://example.edu/late"):
    st = MagicMock()
    st.session_state = state if state is not None else {}
    st.secrets = secrets if secrets is not None else {}
    st.text_input.side_effect = lambda label, **kw: typed if "password" in label.lower() else (
        url if label.startswith("Source URL") else "")
    st.button.side_effect = lambda label, **kw: label in clicked
    st.file_uploader.return_value = upload
    st.selectbox.side_effect = lambda label, options, **kw: options[0]
    st.multiselect.side_effect = lambda label, options, **kw: kw.get("default", [])
    st.columns.side_effect = lambda n: [st] * (n if isinstance(n, int) else len(n))  # c1.text_input is st.text_input
    st.tabs.side_effect = lambda names: [MagicMock() for _ in names]
    st.rerun.side_effect = RuntimeError("rerun")
    return st


@pytest.fixture
def page(monkeypatch, tmp_path):
    kb = tmp_path / "institutions" / "demo" / "kb"
    kb.mkdir(parents=True)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)

    def load(st):
        monkeypatch.setitem(sys.modules, "streamlit", st)
        import app

        sys.modules.pop("app.admin_page", None)
        if hasattr(app, "admin_page"):
            delattr(app, "admin_page")
        from app import admin_page

        monkeypatch.setattr(admin_page, "ROOT", tmp_path)
        return admin_page

    yield load, tmp_path
    import app

    sys.modules.pop("app.admin_page", None)
    if hasattr(app, "admin_page"):
        delattr(app, "admin_page")


def test_the_page_is_closed_when_no_password_is_set(page):
    load, _ = page
    st = fake_st()
    load(st).render()
    assert st.error.called and not st.tabs.called and st.warning.called   # FERPA reminder is shown


def test_a_wrong_password_is_counted_and_does_not_open_the_page(page):
    load, _ = page
    st = fake_st(clicked=("Log in",), typed="nope", secrets={"ADMIN_PASSWORD": "right"})
    load(st).render()
    assert st.session_state["admin_tries"] == 1 and not st.tabs.called


def test_too_many_wrong_passwords_lock_the_form(page):
    load, _ = page
    st = fake_st(state={"admin_tries": admin.MAX_PASSWORD_TRIES}, secrets={"ADMIN_PASSWORD": "right"})
    load(st).render()
    assert not st.text_input.called and not st.tabs.called


def test_the_right_password_opens_the_page(page):
    load, _ = page
    st = fake_st(clicked=("Log in",), typed="right", secrets={"ADMIN_PASSWORD": "right"})
    with pytest.raises(RuntimeError, match="rerun"):       # st.rerun() is called after the login
        load(st).render()
    assert st.session_state["admin_ok"] is True


def test_a_logged_in_advisor_sees_the_three_tabs_and_can_save_a_document(page):
    load, root = page
    upload = SimpleNamespace(name="Late Registration.md", getvalue=lambda: DOC_META_OK.encode())
    st = fake_st(state={"admin_ok": True}, clicked=("Save document",), upload=upload)
    load(st).render()
    assert st.tabs.call_args[0][0] == ["Documents", "Tables", "Re-index"]
    saved = root / "institutions" / "demo" / "kb" / "late-registration.md"
    assert saved.exists() and "source_url: https://example.edu/late" in saved.read_text(encoding="utf-8")
    assert any("late-registration" in str(c) for c in st.success.call_args_list)


def test_a_document_with_no_source_url_is_refused_on_the_page(page):
    load, root = page
    upload = SimpleNamespace(name="x.md", getvalue=lambda: b"Some text.")
    st = fake_st(state={"admin_ok": True}, clicked=("Save document",), upload=upload, url="")
    load(st).render()
    assert st.error.called and not list((root / "institutions" / "demo" / "kb").glob("*.md"))


def test_the_admin_stub_page_and_menu_setting_exist():
    from pathlib import Path
    import tomllib

    assert "admin_page.render()" in Path("app/pages/9_Admin.py").read_text(encoding="utf-8")
    cfg = tomllib.load(open(".streamlit/config.toml", "rb"))
    assert cfg["client"]["showSidebarNavigation"] is False
    assert "ADMIN_PASSWORD" in Path(".streamlit/secrets.toml.example").read_text(encoding="utf-8")


def test_check_password_and_institution_list(tmp_path):
    assert admin.check_password("abc", "abc") and not admin.check_password("abd", "abc")
    assert not admin.check_password("", "") and not admin.check_password("x", None)
    (tmp_path / "a" / "kb").mkdir(parents=True)
    (tmp_path / "b").mkdir()
    assert admin.list_institutions(tmp_path) == ["a"] and admin.list_institutions(tmp_path / "none") == []


def test_the_password_is_read_from_the_dotenv_file(page, monkeypatch, tmp_path):
    load, _ = page
    (tmp_path / ".env").write_text("ADMIN_PASSWORD=from-dotenv\n", encoding="utf-8")
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    try:
        import dotenv  # noqa: F401
    except ImportError:
        pytest.skip("python-dotenv is not installed here")
    module = load(fake_st())            # load() points the page's ROOT at tmp_path
    assert module.ROOT == tmp_path and module._expected_password() == "from-dotenv"
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
