"""What the Admin page does, without any Streamlit in it (so it can be tested).

An advisor uploads a document (PDF, Word, Markdown, HTML, text) or one of the two tables
(deadlines.csv, programs.csv). This module turns the document into a knowledge-base Markdown file
with front matter, checks it with the same validators the rest of the project uses, saves it into
the institution's folder, and re-indexes so the advisor can see what changed.

Only standard-library parsers are used for HTML and Word, and pypdf (already in requirements.txt)
for PDF, so the Admin page adds no new dependency.
"""
from __future__ import annotations

import datetime as dt
import io
import re
import shutil
import tempfile
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

import yaml

DOC_EXTENSIONS = (".md", ".txt", ".html", ".htm", ".docx", ".pdf")
TABLES = {"deadlines": "deadlines.csv", "programs": "programs.csv"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

FERPA_REMINDER = ("Upload only public institutional documents or staff-approved handouts. Student "
                  "records and anything covered by FERPA must never be uploaded.")

_FRONT_MATTER = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)", re.S)


# ------------------------------------------------------------------ reading files

def slugify(name: str) -> str:
    """'My File (2026).PDF' -> 'my-file-2026'. The slug becomes the document id the advisor cites."""
    stem = Path(name).stem.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", stem).strip("-")
    return slug or "document"


class _TextFromHtml(HTMLParser):
    SKIP = {"script", "style", "nav", "footer", "header", "noscript", "svg", "form"}
    BLOCK = {"p", "div", "br", "tr", "section", "article", "ul", "ol", "table"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif re.fullmatch(r"h[1-6]", tag):
            self.out.append("\n\n" + "#" * int(tag[1]) + " ")
        elif tag == "li":
            self.out.append("\n- ")
        elif tag in self.BLOCK:
            self.out.append("\n\n" if tag in {"p", "div", "section", "article", "table"} else "\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        elif re.fullmatch(r"h[1-6]", tag):
            self.out.append("\n\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def html_to_markdown(html: str) -> str:
    parser = _TextFromHtml()
    parser.feed(html)
    text = "".join(parser.out)
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_to_markdown(data: bytes) -> str:
    """Paragraphs of a .docx; 'Heading 1-6' styles become '#' headings, list items become '- '."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            root = ET.fromstring(z.read("word/document.xml"))
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as e:
        raise ValueError("This does not look like a Word (.docx) file.") from e
    lines = []
    for p in root.iter(_W + "p"):
        text = "".join(t.text or "" for t in p.iter(_W + "t")).strip()
        if not text:
            continue
        style = p.find(f"{_W}pPr/{_W}pStyle")
        style_name = (style.get(_W + "val") if style is not None else "") or ""
        m = re.fullmatch(r"(?i)heading\s*([1-6])", style_name)
        if m:
            lines.append("\n" + "#" * int(m.group(1)) + " " + text + "\n")
        elif p.find(f"{_W}pPr/{_W}numPr") is not None:
            lines.append("- " + text)
        else:
            lines.append(text + "\n")
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def pdf_to_markdown(data: bytes) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except Exception as e:
        raise ValueError("This PDF could not be read.") from e
    text = "\n\n".join(p for p in pages if p)
    if not text.strip():
        raise ValueError("This PDF has no text in it (it may be a scan). Upload a text version.")
    return text


def extract_text(filename: str, data: bytes) -> str:
    """The text of an uploaded document, as Markdown. Raises ValueError with a plain message."""
    ext = Path(filename).suffix.lower()
    if ext not in DOC_EXTENSIONS:
        raise ValueError(f"{ext or 'This file type'} is not supported. Use: {', '.join(DOC_EXTENSIONS)}.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("This file is larger than 10 MB.")
    if ext == ".pdf":
        text = pdf_to_markdown(data)
    elif ext == ".docx":
        text = docx_to_markdown(data)
    elif ext in (".html", ".htm"):
        text = html_to_markdown(data.decode("utf-8-sig", errors="replace"))
    else:
        text = data.decode("utf-8-sig", errors="replace").replace("\r\n", "\n")
    if not text.strip():
        raise ValueError("No text was found in this file.")
    return text


def privacy_warnings(text: str) -> list[str]:
    """Things that suggest a student record. A warning only: the advisor decides."""
    warnings = []
    if re.search(r"\b\d{3}-\d{2}-\d{4}\b", text):
        warnings.append("The text contains something that looks like a Social Security number.")
    if len(set(re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", text))) > 3:
        warnings.append("The text contains several email addresses. Is it a list of people?")
    return warnings


# ------------------------------------------------------------------ the knowledge-base document

def split_front_matter(text: str) -> tuple[dict | None, str]:
    m = _FRONT_MATTER.match(text.replace("\r\n", "\n"))
    if not m:
        return None, text
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return None, text
    return (meta if isinstance(meta, dict) else None), text[m.end():]


def first_heading(text: str) -> str:
    m = re.search(r"^#{1,2}\s+(.+)$", text, re.M)
    return m.group(1).strip() if m else ""


def _validate(text: str) -> None:
    """Run the project's own check on a document (core/kb.py). Raises ValueError."""
    from core.kb import load_doc

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "check.md"
        path.write_text(text, encoding="utf-8")
        load_doc(path)


def make_kb_document(filename: str, text: str, meta: dict | None = None,
                     today: dt.date | None = None) -> tuple[str, str]:
    """(slug, full Markdown) for the knowledge base.

    A Markdown upload that already has front matter is kept as it is (and checked). Otherwise the
    front matter is built from `meta` (title, source_url, layer, audience, language, effective_term);
    `retrieved_date` is today. Raises ValueError with a readable message if anything is missing."""
    existing, _body = split_front_matter(text)
    if existing is not None:
        full = text.replace("\r\n", "\n")
    else:
        meta = dict(meta or {})
        title = (meta.get("title") or first_heading(text) or Path(filename).stem.replace("-", " ")).strip()
        front = {
            "title": title,
            "source_url": (meta.get("source_url") or "").strip(),
            "layer": meta.get("layer") or "institution",
            "audience": meta.get("audience") or ["all"],
            "retrieved_date": (today or dt.date.today()).isoformat(),
            "language": meta.get("language") or "en",
        }
        if meta.get("effective_term"):
            front["effective_term"] = str(meta["effective_term"])
        full = "---\n" + yaml.safe_dump(front, allow_unicode=True, sort_keys=False) + "---\n\n" + text.strip() + "\n"
    _validate(full)
    return slugify(filename), full


def save_document(root, slug: str, full_text: str) -> str:
    """Write kb/<slug>.md in the institution folder. Returns 'added' or 'replaced'."""
    kb = Path(root) / "kb"
    kb.mkdir(parents=True, exist_ok=True)
    path = kb / f"{slug}.md"
    status = "replaced" if path.exists() else "added"
    path.write_text(full_text, encoding="utf-8")
    return status


def delete_document(root, slug: str) -> bool:
    path = Path(root) / "kb" / f"{slug}.md"
    if path.exists():
        path.unlink()
        return True
    return False


def list_documents(root) -> list[dict]:
    """Every knowledge-base document with its date, for the Admin page and the Coverage Report."""
    from core.kb import load_doc

    rows = []
    for p in sorted((Path(root) / "kb").glob("*.md")):
        try:
            d = load_doc(p)
            rows.append({"id": p.stem, "title": d.meta.title, "layer": d.meta.layer,
                         "retrieved_date": d.meta.retrieved_date, "language": d.meta.language})
        except ValueError:
            rows.append({"id": p.stem, "title": "(invalid front matter)", "layer": "",
                         "retrieved_date": None, "language": ""})
    return rows


# ------------------------------------------------------------------ the two tables

def save_table(root, kind: str, data: bytes) -> int:
    """Check an uploaded deadlines.csv or programs.csv, then replace the old one.
    The old file is kept as <name>.csv.bak. Returns the number of rows. Raises ValueError."""
    from core.tables import load_deadlines, load_programs

    if kind not in TABLES:
        raise ValueError(f"Unknown table: {kind}")
    loader = load_deadlines if kind == "deadlines" else load_programs
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d) / TABLES[kind]
        tmp.write_bytes(data)
        rows = loader(tmp)  # raises ValueError listing every bad row
    target = Path(root) / TABLES[kind]
    if target.exists():
        shutil.copyfile(target, target.with_suffix(".csv.bak"))
    target.write_bytes(data)
    return len(rows)


# ------------------------------------------------------------------ re-index and what changed

def index_snapshot(collection) -> dict[str, str]:
    """{doc_id: file_hash} for what the index holds right now."""
    out = {}
    for m in (collection.get(include=["metadatas"])["metadatas"] or []):
        out[m["doc_id"]] = m["file_hash"]
    return out


def describe_changes(before: dict, after: dict) -> dict:
    return {
        "added": sorted(after.keys() - before.keys()),
        "removed": sorted(before.keys() - after.keys()),
        "updated": sorted(d for d in before.keys() & after.keys() if before[d] != after[d]),
        "unchanged": sorted(d for d in before.keys() & after.keys() if before[d] == after[d]),
    }


def reindex(root, collection, embedder) -> dict:
    """Make the index match the kb/ folder. Returns {'added','updated','removed','unchanged'
    (lists of document ids), 'chunks_embedded', 'total_chunks'}. Raises ValueError if a document is
    invalid (core/kb.py lists every broken file at once)."""
    from core.ingest import load_chunks, sync_index
    from core.kb import load_kb

    load_kb(Path(root) / "kb")  # raises one ValueError that lists every broken document
    chunks = load_chunks(Path(root) / "kb")
    before = index_snapshot(collection)
    stats = sync_index(chunks, collection, embedder)
    changes = describe_changes(before, index_snapshot(collection))
    changes["chunks_embedded"] = stats["chunks_embedded"]
    changes["total_chunks"] = collection.count()
    return changes


def open_index(root, db: str = "chroma_db"):
    """The real Chroma collection and embedder for an institution folder (slow: loads the model)."""
    import chromadb

    from core.embeddings import get_embedder
    from core.ingest import open_collection

    embedder = get_embedder()
    client = chromadb.PersistentClient(path=db)
    return open_collection(client, Path(root).resolve().name, embedder), embedder


# ------------------------------------------------------------------ password and institutions

MAX_PASSWORD_TRIES = 5


def check_password(entered: str, expected: str | None) -> bool:
    """True only if a password is set AND the entered one matches. No password set means closed."""
    import hmac

    if not expected or not entered:
        return False
    return hmac.compare_digest(entered.encode("utf-8"), expected.encode("utf-8"))


def list_institutions(base="institutions") -> list[str]:
    """Institution folders that have a kb/ folder (demo-ccc, demo-second, ...)."""
    base = Path(base)
    return sorted(p.name for p in base.iterdir() if (p / "kb").is_dir()) if base.is_dir() else []
