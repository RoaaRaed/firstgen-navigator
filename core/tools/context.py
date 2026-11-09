"""Everything the four tools need for one institution, loaded once.

    ctx = load_context("demo-ccc")          # reads the CSV/YAML files; the index loads on first search
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from core.tables import DeadlineRow, ProgramRow, load_deadlines, load_programs


@dataclass
class ToolContext:
    institution: str
    root: Path
    deadlines: list[DeadlineRow]
    programs: list[ProgramRow]
    handoffs: dict
    db: str = "chroma_db"
    today: dt.date = field(default_factory=dt.date.today)
    _retriever: object = None

    @property
    def retriever(self):
        """The Chroma retriever is slow to load, so it is created on the first search only."""
        if self._retriever is None:
            from core.retriever import load_retriever

            self._retriever = load_retriever(self.institution, self.db)
        return self._retriever

    def program(self, program_id: str) -> ProgramRow | None:
        return next((p for p in self.programs if p.id == program_id), None)


def load_handoffs(path) -> dict:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "topics" not in data:
        raise ValueError(f"{path}: needs a 'topics' section")
    return data


def load_context(institution: str = "demo-ccc", root: str = "institutions",
                 db: str = "chroma_db", retriever=None, today: dt.date | None = None) -> ToolContext:
    base = Path(root) / institution
    ctx = ToolContext(
        institution=institution,
        root=base,
        deadlines=load_deadlines(base / "deadlines.csv"),
        programs=load_programs(base / "programs.csv"),
        handoffs=load_handoffs(base / "handoffs.yaml"),
        db=db,
        today=today or dt.date.today(),
    )
    ctx._retriever = retriever
    return ctx
