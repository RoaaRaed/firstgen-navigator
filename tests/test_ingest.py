from pathlib import Path

import pytest

from core.ingest import (
    MAX_CHARS,
    chunk_document,
    file_hash,
    load_chunks,
    merge_small,
    split_long,
    split_sections,
)

KB = Path("institutions/demo-ccc/kb")

FRONT = """---
title: "Sample Doc"
source_url: https://example.org/sample
layer: federal
audience: [applying, enrolled]
retrieved_date: 2026-10-28
language: en
effective_term: 2026-27
---

"""


def write_doc(tmp_path, body, name="sample.md"):
    p = tmp_path / name
    p.write_bytes((FRONT + body).encode("utf-8"))  # exact bytes: same on Windows and Linux
    return p


def test_split_by_heading_keeps_path():
    body = "# Top\n\nintro text\n\n## A\n\nalpha\n\n### A1\n\nalpha one\n\n## B\n\nbeta"
    sections = split_sections(body)
    assert [p for p, _ in sections] == ["Top", "Top > A", "Top > A > A1", "Top > B"]
    assert "alpha one" in sections[2][1]


def test_heading_inside_code_fence_is_not_a_heading():
    body = "## Real\n\n```\n# not a heading\n```\n\nafter"
    assert len(split_sections(body)) == 1


def test_tiny_sections_merge_forward():
    merged = merge_small([("A", "## A\n\nshort"), ("B", "## B\n\n" + "word " * 100)])
    assert len(merged) == 1 and merged[0][0] == "A" and "## B" in merged[0][1]


def test_long_section_splits_and_respects_limit():
    text = "\n\n".join(f"Paragraph {i}. " + "word " * 60 for i in range(20))
    parts = split_long(text)
    assert len(parts) > 1
    assert all(len(p) <= MAX_CHARS for p in parts)


def test_long_table_splits_and_repeats_header():
    header = "| Name | Deadline |\n|---|---|"
    rows = "\n".join(f"| University {i} | March {i % 28 + 1} |" for i in range(200))
    parts = split_long(header + "\n" + rows)
    assert len(parts) > 1
    assert all(p.startswith("| Name | Deadline |") for p in parts)
    assert all(len(p) <= MAX_CHARS for p in parts)


def test_metadata_is_attached_to_every_chunk(tmp_path):
    chunks = chunk_document(write_doc(tmp_path, "# T\n\n" + "text " * 80 + "\n\n## S\n\n" + "more " * 80))
    assert len(chunks) == 2
    for c in chunks:
        m = c.metadata
        assert m["title"] == "Sample Doc"
        assert m["layer"] == "federal"
        assert m["audience"] == "applying,enrolled"
        assert m["retrieved_date"] == "2026-10-28"
        assert m["effective_term"] == "2026-27"
        assert m["source_url"] == "https://example.org/sample"
        assert m["section"] == c.section
    assert [c.chunk_id for c in chunks] == ["sample::00", "sample::01"]


def test_embed_text_contains_title_and_section(tmp_path):
    c = chunk_document(write_doc(tmp_path, "## Eligibility\n\n" + "text " * 80))[0]
    assert "Sample Doc" in c.embed_text and "Eligibility" in c.embed_text


def test_file_hash_changes_with_content_and_ignores_line_endings(tmp_path):
    a = write_doc(tmp_path, "## A\n\nhello", "a.md")
    h1 = file_hash(a)
    assert h1 == file_hash(a)
    a.write_bytes(a.read_bytes().replace(b"\n", b"\r\n"))
    assert file_hash(a) == h1
    a.write_bytes((FRONT + "## A\n\nhello world").encode("utf-8"))
    assert file_hash(a) != h1


@pytest.mark.skipif(not KB.exists(), reason="demo-ccc KB not present")
def test_real_kb_chunks_are_valid():
    chunks = load_chunks(KB)
    assert len(chunks) >= 25
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids)), "chunk ids must be unique"
    assert all(c.text.strip() for c in chunks)
    assert all(len(c.text) <= MAX_CHARS + 200 for c in chunks)
    assert {c.metadata["layer"] for c in chunks} == {"federal", "state", "institution"}
