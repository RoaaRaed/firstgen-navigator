"""Load and validate the structured tables (deadlines.csv, programs.csv)."""

import datetime as dt
from pathlib import Path
from typing import Literal, Optional

import pandas as pd
from pydantic import BaseModel, ValidationError, field_validator, model_validator


class _Row(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def blank_to_none(cls, data):
        """Empty CSV cells arrive as '' - treat them as missing (None)."""
        if isinstance(data, dict):
            return {
                k: (None if isinstance(v, str) and not v.strip() else v)
                for k, v in data.items()
            }
        return data


class DeadlineRow(_Row):
    id: str
    layer: Literal["federal", "state", "institution"]
    institution: Optional[str] = None
    term: str
    item: str
    date: dt.date
    applies_to: Literal["applying", "enrolled", "transfer", "all"]
    source_url: str
    retrieved_date: dt.date
    notes: Optional[str] = None
    language: Literal["en", "ar"] = "en"


Category = Literal[
    "financial", "academic", "wellness", "transfer",
    "immigrant_services", "childcare", "food", "disability",
]
Tag = Literal[
    "first_gen", "working_20plus", "working_30plus", "caregiver",
    "fafsa_ineligible_or_unsure", "esl", "transfer",
]


class ProgramRow(_Row):
    id: str
    institution: str
    name: str
    category: Category
    eligibility_tags: list[Tag] = []
    description: str
    contact_office: str
    contact_url: Optional[str] = None
    contact_phone: Optional[str] = None
    hours: Optional[str] = None
    language_support: list[str] = []
    source_url: str
    retrieved_date: dt.date

    @field_validator("eligibility_tags", "language_support", mode="before")
    @classmethod
    def split_semicolons(cls, v):
        """'first_gen;caregiver' -> ['first_gen', 'caregiver']"""
        if v is None:
            return []
        if isinstance(v, str):
            return [part.strip() for part in v.split(";") if part.strip()]
        return v


def _load(path, model):
    path = Path(path)
    # utf-8-sig also accepts files saved by Excel (which add an invisible BOM)
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")

    expected = set(model.model_fields)
    missing = expected - set(df.columns)
    extra = set(df.columns) - expected
    if missing or extra:
        raise ValueError(
            f"{path.name}: missing columns {sorted(missing)}, "
            f"unexpected columns {sorted(extra)}"
        )

    rows, errors = [], []
    for line, record in enumerate(df.to_dict(orient="records"), start=2):
        try:
            rows.append(model(**record))
        except ValidationError as err:
            problems = "; ".join(
                f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}"
                for e in err.errors()
            )
            errors.append(f"{path.name} line {line}: {problems}")

    ids = [r.id for r in rows]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        errors.append(f"{path.name}: duplicate id '{dup}'")

    if errors:
        raise ValueError("Invalid table:\n" + "\n".join(errors))
    return rows


def load_deadlines(path):
    return _load(path, DeadlineRow)


def load_programs(path):
    return _load(path, ProgramRow)