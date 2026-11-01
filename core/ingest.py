"""Step 1 of ingestion: load every KB document and split it into chunks.

Embedding and Chroma are added in the next step. This file only does the part
that needs no model: load -> split by heading -> attach metadata -> hash.

    python -m core.ingest                       # summary for demo-ccc
    python -m core.ingest --kb path/to/kb       # another institution
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from core.kb import load_doc

MAX_CHARS = 1800  # a section longer than this is split into several chunks
MIN_CHARS = 200   # a section shorter than this is merged with the next one

_HEADING = re.compile(r"^(#{1,4})\s+(.*?)\s*#*\s*$")
_TABLE_SEP = re.compile(r"^\|[\s:|-]+\|?\s*$")
_SENTENCE = re.compile(r"(?<=[.!?؟])\s+")


@dataclass
class Chunk:
    chunk_id: str            # "<doc_id>::<nn>", the identifier used in citations
    doc_id: str              # file name without .md
    text: str                # what the student sees in a citation card
    section: str             # heading path, e.g. "Title > Eligibility"
    metadata: dict = field(default_factory=dict)

    @property
    def embed_text(self) -> str:
        """Text sent to the embedding model: title and section help retrieval."""
        return f"{self.metadata['title']} - {self.section}\n\n{self.text}"


def file_hash(path: Path) -> str:
    """Hash of the file's content. If it did not change, we skip re-indexing it."""
    data = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()[:16]


def split_sections(body: str) -> list[tuple[str, str]]:
    """Split Markdown into (heading_path, text) pairs. Text keeps its heading line."""
    sections: list[tuple[str, str]] = []
    stack: list[tuple[int, str]] = []
    buf: list[str] = []
    path = ""
    in_fence = False

    def flush():
        text = "\n".join(buf).strip()
        if text and any(not l.lstrip().startswith("#") for l in text.splitlines()):
            sections.append((path, text))
        buf.clear()

    for line in body.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        m = None if in_fence else _HEADING.match(line)
        if m:
            flush()
            level, title = len(m.group(1)), m.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            path = " > ".join(t for _, t in stack)
        buf.append(line)
    flush()
    return sections


def _split_block(block: str, limit: int) -> list[str]:
    """Split one oversized block (a long table, list or paragraph) by lines."""
    lines = block.split("\n")
    header: list[str] = []
    if len(lines) > 2 and lines[0].startswith("|") and _TABLE_SEP.match(lines[1]):
        header, lines = lines[:2], lines[2:]  # repeat the table header in each part
    pieces: list[str] = []
    for line in lines:
        if len(line) > limit:  # one giant line: fall back to sentences
            pieces.extend(s for s in _SENTENCE.split(line) if s)
        else:
            pieces.append(line)
    out: list[str] = []
    cur = list(header)
    size = sum(len(l) + 1 for l in cur)
    for p in pieces:
        if size + len(p) + 1 > limit and len(cur) > len(header):
            out.append("\n".join(cur))
            cur, size = list(header), sum(len(l) + 1 for l in header)
        cur.append(p)
        size += len(p) + 1
    if len(cur) > len(header):
        out.append("\n".join(cur))
    return out


def split_long(text: str, limit: int = MAX_CHARS) -> list[str]:
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    cur = ""
    for block in re.split(r"\n\s*\n", text):
        pieces = _split_block(block, limit) if len(block) > limit else [block]
        for piece in pieces:
            if cur and len(cur) + len(piece) + 2 > limit:
                parts.append(cur)
                cur = piece
            else:
                cur = f"{cur}\n\n{piece}" if cur else piece
    if cur:
        parts.append(cur)
    return parts


def merge_small(sections: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """A tiny section embeds badly, so glue it to the section after it."""
    out: list[tuple[str, str]] = []
    i = 0
    while i < len(sections):
        path, text = sections[i]
        while len(text) < MIN_CHARS and i + 1 < len(sections):
            i += 1
            text = f"{text}\n\n{sections[i][1]}"
        out.append((path, text))
        i += 1
    return out


def chunk_document(path: Path) -> list[Chunk]:
    path = Path(path)
    doc = load_doc(path)
    meta, body = doc.meta, doc.body
    doc_id = path.stem
    base = {
        "doc_id": doc_id,
        "title": meta.title,
        "source_url": meta.source_url,
        "layer": meta.layer,
        "audience": ",".join(meta.audience),
        "retrieved_date": meta.retrieved_date.isoformat(),
        "language": meta.language,
        "effective_term": meta.effective_term or "",
        "file_hash": file_hash(path),
    }
    chunks: list[Chunk] = []
    for section, text in merge_small(split_sections(body)):
        for piece in split_long(text):
            n = len(chunks)
            chunks.append(Chunk(
                chunk_id=f"{doc_id}::{n:02d}",
                doc_id=doc_id,
                text=piece,
                section=section,
                metadata={**base, "section": section, "chunk_index": n},
            ))
    return chunks


def load_chunks(kb_dir: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    for p in sorted(Path(kb_dir).glob("*.md")):
        chunks.extend(chunk_document(p))
    return chunks


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Split the KB into chunks (no embedding yet).")
    ap.add_argument("--kb", default="institutions/demo-ccc/kb")
    args = ap.parse_args(argv)
    chunks = load_chunks(Path(args.kb))
    by_doc: dict[str, list[Chunk]] = {}
    for c in chunks:
        by_doc.setdefault(c.doc_id, []).append(c)
    print(f"{'document':58} {'chunks':>6} {'longest':>8}")
    for doc, cs in by_doc.items():
        print(f"{doc:58} {len(cs):>6} {max(len(c.text) for c in cs):>8}")
    sizes = sorted(len(c.text) for c in chunks)
    print(f"\nOK: {len(by_doc)} documents -> {len(chunks)} chunks "
          f"(median {sizes[len(sizes) // 2]} chars, max {sizes[-1]}, min {sizes[0]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
