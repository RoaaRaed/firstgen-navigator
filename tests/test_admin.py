import datetime as dt
import io
import zipfile

import pytest

from core import admin

TODAY = dt.date(2026, 11, 25)
META = {"title": "Late Registration", "source_url": "https://example.edu/late", "layer": "institution",
        "audience": ["enrolled"], "language": "en"}


def make_docx(paragraphs):
    """paragraphs: list of (style or None, text, is_list)"""
    ns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    body = ""
    for style, text, is_list in paragraphs:
        ppr = ""
        if style:
            ppr += f'<w:pStyle w:val="{style}"/>'
        if is_list:
            ppr += '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>'
        body += f"<w:p><w:pPr>{ppr}</w:pPr><w:r><w:t>{text}</w:t></w:r></w:p>"
    xml = f'<?xml version="1.0"?><w:document {ns}><w:body>{body}</w:body></w:document>'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", xml)
    return buf.getvalue()


# ---- reading files

def test_slugify():
    assert admin.slugify("My File (2026).PDF") == "my-file-2026"
    assert admin.slugify("!!!.md") == "document"


def test_html_keeps_headings_and_lists_and_drops_menus_and_scripts():
    html = ("<html><nav>Home | About</nav><script>var x=1;</script><h1>Apply</h1><p>Fill in the form.</p>"
            "<ul><li>Step one</li><li>Step two</li></ul><footer>Copyright</footer></html>")
    text = admin.html_to_markdown(html)
    assert "# Apply" in text and "- Step one" in text and "- Step two" in text
    assert "Home" not in text and "var x" not in text and "Copyright" not in text


def test_docx_headings_and_lists():
    data = make_docx([("Heading1", "Late registration", False), (None, "You may register late.", False),
                      (None, "Pay the fee", True)])
    text = admin.docx_to_markdown(data)
    assert "# Late registration" in text and "You may register late." in text and "- Pay the fee" in text


def test_docx_that_is_not_a_docx_gives_a_readable_error():
    with pytest.raises(ValueError, match="Word"):
        admin.docx_to_markdown(b"not a zip")


def test_pdf_text_is_read_and_an_empty_pdf_is_explained():
    from pypdf import PdfWriter
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 720, "Tuition is due on the first day.")
    c.save()
    assert "Tuition is due" in admin.pdf_to_markdown(buf.getvalue())

    blank = io.BytesIO()
    w = PdfWriter()
    w.add_blank_page(width=200, height=200)
    w.write(blank)
    with pytest.raises(ValueError, match="scan"):
        admin.pdf_to_markdown(blank.getvalue())


def test_extract_text_rejects_unknown_types_and_huge_files_and_empty_files():
    with pytest.raises(ValueError, match="not supported"):
        admin.extract_text("a.exe", b"x")
    with pytest.raises(ValueError, match="10 MB"):
        admin.extract_text("a.md", b"x" * (admin.MAX_UPLOAD_BYTES + 1))
    with pytest.raises(ValueError, match="No text"):
        admin.extract_text("a.md", b"   \n")
    assert admin.extract_text("a.txt", "héllo\r\nworld".encode("utf-8")) == "héllo\nworld"


def test_privacy_warnings():
    assert admin.privacy_warnings("Call 555-12-3456 now")
    assert admin.privacy_warnings("a@x.com b@x.com c@x.com d@x.com")
    assert admin.privacy_warnings("Tuition is due on Monday.") == []


# ---- the knowledge-base document

def test_front_matter_is_built_and_checked():
    slug, full = admin.make_kb_document("Late Registration.docx", "# Late\n\nText here.", META, today=TODAY)
    assert slug == "late-registration" and full.startswith("---\n")
    assert "retrieved_date: '2026-11-25'" in full or "retrieved_date: 2026-11-25" in full
    assert "Text here." in full


def test_title_falls_back_to_the_first_heading():
    meta = {k: v for k, v in META.items() if k != "title"}
    _slug, full = admin.make_kb_document("x.md", "# Drop Dates\n\nBody.", meta, today=TODAY)
    assert "title: Drop Dates" in full


def test_a_missing_source_url_is_refused_with_a_clear_message():
    meta = dict(META, source_url="")
    with pytest.raises(ValueError, match="source_url"):
        admin.make_kb_document("x.md", "Body", meta, today=TODAY)


def test_a_markdown_file_with_its_own_front_matter_is_kept_but_still_checked():
    good = ("---\ntitle: T\nsource_url: https://e.edu\nlayer: federal\naudience: [all]\n"
            "retrieved_date: 2026-10-01\n---\n\nBody text.\n")
    slug, full = admin.make_kb_document("t.md", good, None)
    assert full == good and slug == "t"
    bad = good.replace("layer: federal", "layer: galaxy")
    with pytest.raises(ValueError):
        admin.make_kb_document("t.md", bad, None)


def test_save_list_and_delete_documents(tmp_path):
    _slug, full = admin.make_kb_document("a.md", "Body.", META, today=TODAY)
    assert admin.save_document(tmp_path, "a", full) == "added"
    assert admin.save_document(tmp_path, "a", full) == "replaced"
    rows = admin.list_documents(tmp_path)
    assert rows[0]["id"] == "a" and rows[0]["retrieved_date"] == TODAY
    assert admin.delete_document(tmp_path, "a") and not admin.delete_document(tmp_path, "a")


# ---- the two tables

DEADLINES_HEADER = "id,layer,institution,term,item,date,applies_to,source_url,retrieved_date,notes,language\n"
GOOD_DEADLINE = ("d1,institution,City College,Spring 2027,Last day to drop,2027-04-08,all,"
                 "https://example.edu/drop,2026-10-29,,en\n")


def test_a_good_table_replaces_the_old_one_and_keeps_a_backup(tmp_path):
    (tmp_path / "deadlines.csv").write_text("old", encoding="utf-8")
    n = admin.save_table(tmp_path, "deadlines", (DEADLINES_HEADER + GOOD_DEADLINE).encode())
    assert n == 1
    assert "Last day to drop" in (tmp_path / "deadlines.csv").read_text(encoding="utf-8")
    assert (tmp_path / "deadlines.csv.bak").read_text(encoding="utf-8") == "old"


def test_a_bad_table_is_refused_and_the_old_one_stays(tmp_path):
    (tmp_path / "deadlines.csv").write_text("old", encoding="utf-8")
    bad = DEADLINES_HEADER + GOOD_DEADLINE.replace("2027-04-08", "next spring")
    with pytest.raises(ValueError, match="line 2"):
        admin.save_table(tmp_path, "deadlines", bad.encode())
    with pytest.raises(ValueError, match="missing columns"):
        admin.save_table(tmp_path, "deadlines", b"id,item\n1,2\n")
    assert (tmp_path / "deadlines.csv").read_text(encoding="utf-8") == "old"
    with pytest.raises(ValueError, match="Unknown"):
        admin.save_table(tmp_path, "grades", b"x")


# ---- re-index and the change summary

class FakeCollection:
    def __init__(self):
        self.rows = {}   # id -> metadata

    def get(self, include=None, **kw):
        return {"metadatas": list(self.rows.values())}

    def add(self, ids, documents, embeddings, metadatas):
        for i, m in zip(ids, metadatas):
            self.rows[i] = m

    def delete(self, where):
        self.rows = {i: m for i, m in self.rows.items() if m["doc_id"] != where["doc_id"]}

    def count(self):
        return len(self.rows)


class FakeEmbedder:
    name = "fake"

    def embed_passages(self, texts):
        return [[0.0] for _ in texts]


def test_reindex_reports_added_updated_removed_and_unchanged(tmp_path):
    col, emb = FakeCollection(), FakeEmbedder()
    for slug, body in (("a", "Alpha text."), ("b", "Beta text.")):
        _s, full = admin.make_kb_document(slug + ".md", body, META, today=TODAY)
        admin.save_document(tmp_path, slug, full)
    first = admin.reindex(tmp_path, col, emb)
    assert first["added"] == ["a", "b"] and first["total_chunks"] == col.count() >= 2

    _s, changed = admin.make_kb_document("a.md", "Alpha text changed.", META, today=TODAY)
    admin.save_document(tmp_path, "a", changed)
    _s, new = admin.make_kb_document("c.md", "Gamma text.", META, today=TODAY)
    admin.save_document(tmp_path, "c", new)
    admin.delete_document(tmp_path, "b")
    second = admin.reindex(tmp_path, col, emb)
    assert second["updated"] == ["a"] and second["added"] == ["c"] and second["removed"] == ["b"]
    assert second["unchanged"] == []


def test_reindex_lists_every_broken_document_at_once(tmp_path):
    kb = tmp_path / "kb"
    kb.mkdir()
    (kb / "x.md").write_text("no front matter", encoding="utf-8")
    (kb / "y.md").write_text("also none", encoding="utf-8")
    with pytest.raises(ValueError) as e:
        admin.reindex(tmp_path, FakeCollection(), FakeEmbedder())
    assert "x.md" in str(e.value) and "y.md" in str(e.value)
