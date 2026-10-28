"""Load and validate knowledge-base Markdown documents (front matter + body)."""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

Layer = Literal["federal", "state", "institution"]
Audience = Literal["applying", "enrolled", "transfer", "all"]

# ---, then the YAML, then ---, then the document body
_FRONT_MATTER = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)(.*)\Z", re.S)


class KBMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")  # a typo like "retreived_date" is an error

    title: str
    source_url: str
    layer: Layer
    audience: list[Audience]
    retrieved_date: dt.date
    language: Literal["en", "ar"] = "en"
    effective_term: Optional[str] = None

    @field_validator("audience", mode="before")
    @classmethod
    def audience_as_list(cls, v):
        return [v] if isinstance(v, str) else v  # "all" -> ["all"]

    @field_validator("effective_term", mode="before")
    @classmethod
    def term_as_text(cls, v):
        return None if v is None else str(v)  # YAML reads 2026 as a number

    @field_validator("title", "source_url")
    @classmethod
    def not_blank(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v

    @field_validator("source_url")
    @classmethod
    def must_be_url(cls, v):
        if not v.startswith(("http://", "https://")):
            raise ValueError("must start with http:// or https://")
        return v

    @field_validator("audience")
    @classmethod
    def audience_not_empty(cls, v):
        if not v:
            raise ValueError("must list at least one audience")
        return v


class KBDoc(BaseModel):
    path: str
    meta: KBMeta
    body: str


def _explain(err: ValidationError) -> str:
    return "\n".join(
        f"  - {'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in err.errors()
    )


def load_doc(path) -> KBDoc:
    """Read one .md file, validate its front matter, return it. Raises ValueError."""
    path = Path(path)
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")

    match = _FRONT_MATTER.match(text)
    if not match:
        raise ValueError(f"{path}: file must start with a front matter block between two '---' lines")

    try:
        raw = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"{path}: front matter is not valid YAML: {e}") from e
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: front matter must be 'field: value' lines")

    try:
        meta = KBMeta(**raw)
    except ValidationError as e:
        raise ValueError(f"{path}: invalid front matter:\n{_explain(e)}") from e

    body = match.group(2).strip()
    if not body:
        raise ValueError(f"{path}: document body is empty")
    return KBDoc(path=str(path), meta=meta, body=body)


def load_kb(folder) -> list[KBDoc]:
    """Load every .md file under a folder. Reports ALL broken files at once."""
    docs, errors = [], []
    for p in sorted(Path(folder).rglob("*.md")):
        try:
            docs.append(load_doc(p))
        except ValueError as e:
            errors.append(str(e))
    if errors:
        raise ValueError("Invalid knowledge base:\n" + "\n".join(errors))
    return docs


if __name__ == "__main__":  # quick check:  python -m core.kb
    import sys

    folder = sys.argv[1] if len(sys.argv) > 1 else "institutions/demo-ccc/kb"
    print(f"OK: {len(load_kb(folder))} documents valid")