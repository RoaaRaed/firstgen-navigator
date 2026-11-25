"""The Admin page: an advisor adds documents and tables, re-indexes, and sees what changed.

Streamlit UI only. The work (reading files, checking them, saving, re-indexing) is in
core/admin.py, which is tested. This page is for staff, so its text is English only and is not in
app/i18n. It never touches what students type: it only handles public documents.
"""
import os
from pathlib import Path

import streamlit as st

from core import admin

ROOT = Path(__file__).resolve().parent.parent
LAYERS = ["institution", "state", "federal"]
AUDIENCES = ["all", "applying", "enrolled", "transfer"]


def _expected_password() -> str | None:
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")  # local runs keep ADMIN_PASSWORD in .env; this page does not start the advisor
    except ImportError:
        pass
    try:
        value = st.secrets["ADMIN_PASSWORD"]
    except Exception:  # no secrets file, or the key is missing
        value = None
    return str(value) if value else os.environ.get("ADMIN_PASSWORD")


def _login() -> bool:
    """True once the right password was typed in this browser session."""
    if st.session_state.get("admin_ok"):
        return True
    expected = _expected_password()
    if not expected:
        st.error("The Admin page is closed because no password is set. Add ADMIN_PASSWORD to the "
                 "app's Secrets (or to .env when running on your own computer).")
        return False
    tries = st.session_state.get("admin_tries", 0)
    if tries >= admin.MAX_PASSWORD_TRIES:
        st.error("Too many wrong passwords. Reload the page to try again.")
        return False
    entered = st.text_input("Admin password", type="password")
    if st.button("Log in", type="primary"):
        if admin.check_password(entered, expected):
            st.session_state["admin_ok"] = True
            st.rerun()
        st.session_state["admin_tries"] = tries + 1
        st.error("Wrong password.")
    return False


def _documents_tab(root: Path) -> None:
    st.write("Add or replace one document. It becomes a knowledge-base file that the advisor can cite.")
    upload = st.file_uploader("Document", type=[e.lstrip(".") for e in admin.DOC_EXTENSIONS], key="doc_upload")
    c1, c2 = st.columns(2)
    source_url = c1.text_input("Source URL (where this document is published)", placeholder="https://")
    title = c2.text_input("Title (optional, the first heading is used if empty)")
    c3, c4, c5 = st.columns(3)
    layer = c3.selectbox("Layer", LAYERS)
    audience = c4.multiselect("Audience", AUDIENCES, default=["all"])
    language = c5.selectbox("Language", ["en", "ar"])
    term = st.text_input("Effective term (optional, for example 2027-28)")
    if st.button("Save document", disabled=upload is None):
        try:
            text = admin.extract_text(upload.name, upload.getvalue())
            for warning in admin.privacy_warnings(text):
                st.warning(warning + " Check the file before you continue.")
            meta = {"title": title, "source_url": source_url, "layer": layer,
                    "audience": audience or ["all"], "language": language, "effective_term": term}
            slug, full = admin.make_kb_document(upload.name, text, meta)
            status = admin.save_document(root, slug, full)
            st.success(f"Saved as kb/{slug}.md ({status}). Now open the Re-index tab and press Re-index.")
        except ValueError as e:
            st.error(str(e))
    st.subheader("Documents now in the knowledge base")
    rows = admin.list_documents(root)
    if not rows:
        st.info("No documents yet.")
    else:
        st.dataframe(rows, use_container_width=True)
        remove = st.selectbox("Remove a document", [""] + [r["id"] for r in rows])
        if remove and st.button(f"Remove {remove}"):
            admin.delete_document(root, remove)
            st.success(f"Removed {remove}. Press Re-index to update the search.")


def _tables_tab(root: Path) -> None:
    st.write("Replace deadlines.csv or programs.csv. The file is checked row by row first, and the "
             "old one is kept as a .bak file.")
    for kind in admin.TABLES:
        upload = st.file_uploader(f"{admin.TABLES[kind]}", type=["csv"], key=f"upload_{kind}")
        if st.button(f"Save {admin.TABLES[kind]}", disabled=upload is None, key=f"save_{kind}"):
            try:
                n = admin.save_table(root, kind, upload.getvalue())
                st.success(f"Saved {admin.TABLES[kind]}: {n} rows. Re-index to refresh the app.")
            except ValueError as e:
                st.error("Not saved. The old file is unchanged.")
                st.code(str(e))


def _reindex_tab(root: Path) -> None:
    st.write("Make the search match the documents in the knowledge base. Only new or changed "
             "documents are processed.")
    if st.button("Re-index", type="primary"):
        with st.spinner("Re-indexing (the first time can take a minute)..."):
            try:
                collection, embedder = admin.open_index(root)
                changes = admin.reindex(root, collection, embedder)
            except ValueError as e:
                st.error("Re-index stopped because a document is not valid:")
                st.code(str(e))
                return
        st.cache_resource.clear()  # the chat page must load the new documents and tables
        st.success(f"Done. The search now holds {changes['total_chunks']} passages "
                   f"({changes['chunks_embedded']} newly processed).")
        for key in ("added", "updated", "removed"):
            st.write(f"**{key.capitalize()}** ({len(changes[key])}): " + (", ".join(changes[key]) or "none"))
        st.write(f"**Unchanged**: {len(changes['unchanged'])}")


def render() -> None:
    st.set_page_config(page_title="FirstGen Navigator - Admin", page_icon="🧭", layout="centered")
    st.title("Admin")
    st.warning(admin.FERPA_REMINDER)
    if not _login():
        return
    names = admin.list_institutions(ROOT / "institutions")
    if not names:
        st.error("No institution folders found.")
        return
    institution = st.selectbox("Institution", names)
    root = ROOT / "institutions" / institution
    docs_tab, tables_tab, index_tab = st.tabs(["Documents", "Tables", "Re-index"])
    with docs_tab:
        _documents_tab(root)
    with tables_tab:
        _tables_tab(root)
    with index_tab:
        _reindex_tab(root)
    st.caption("On Streamlit Community Cloud the server's disk is erased when the app restarts. "
               "To keep an upload for good, add the file to the repository in Git.")
