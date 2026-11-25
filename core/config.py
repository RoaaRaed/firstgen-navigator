"""Which institution this copy of the app serves, and its settings (institutions/<slug>/config.yaml).

A new institution needs NO code change: a folder under institutions/ and one setting,
INSTITUTION=<slug>, in .env or in the app's Streamlit Secrets.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

DEFAULT_INSTITUTION = "demo-ccc"
_SLUG = re.compile(r"[a-z0-9][a-z0-9-]*")


class InstitutionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")    # a typo in a setting name is an error, not silence

    name: str                                    # full name, used in the advisor prompt and My Plan
    short_name: str = ""                         # for tight spaces
    state: Optional[str] = None                  # for example "Illinois"
    default_language: Literal["en", "ar"] = "en"
    website: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v):
        if not v.strip():
            raise ValueError("must not be empty")
        return v.strip()


def active_institution(environ=None) -> str:
    """The folder name from the INSTITUTION setting (default demo-ccc). Raises ValueError if it is
    not a plain folder name, so a typo can never point outside institutions/."""
    environ = os.environ if environ is None else environ
    slug = (environ.get("INSTITUTION") or DEFAULT_INSTITUTION).strip()
    if not _SLUG.fullmatch(slug):
        raise ValueError(f"INSTITUTION={slug!r} is not a valid folder name (use lowercase letters, digits, dashes)")
    return slug


def load_config(institution: str, root="institutions") -> InstitutionConfig:
    path = Path(root) / institution / "config.yaml"
    if not path.exists():
        raise ValueError(f"{path} not found. Create it with: python scripts/new_institution.py start {institution} --name \"...\"")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return InstitutionConfig(**data)
    except yaml.YAMLError as e:
        raise ValueError(f"{path}: not valid YAML: {e}") from e
    except ValidationError as e:
        problems = "; ".join(f"{'.'.join(str(p) for p in x['loc'])}: {x['msg']}" for x in e.errors())
        raise ValueError(f"{path}: {problems}") from e
