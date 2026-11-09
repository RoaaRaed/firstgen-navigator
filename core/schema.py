"""The agent's structured output. Every advisor turn must fit this shape: answer, citations,
confidence, next_steps, human_contact (the five fields the brief asks for).

    from core.schema import AdvisorAnswer
    AdvisorAnswer(answer="...", citations=[...], confidence="High", next_steps=[...])
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

Confidence = Literal["High", "Medium", "Low"]


class Citation(BaseModel):
    source_id: str = Field(description=(
        "Exactly as a tool returned it this turn: 'state-isac-map::03' (knowledge base), "
        "'deadlines:ccc-spring27-first-day-16wk', or 'programs:ccc-food-pantries'. Never invented."
    ))
    label: str = Field(description="Short human-readable label: the document title, item, or program name.")


class Contact(BaseModel):
    office: str
    url: str = ""
    phone: str = ""


class AdvisorAnswer(BaseModel):
    """One advisor turn.

    confidence is always one of High / Medium / Low (the brief's three-level label) - a
    question nothing useful was found for still uses "Low", with an empty citations list and
    `answer` plainly saying it was not found; "Low" does not mean a wrong or bad answer.
    """

    answer: str = Field(description="The prose answer to the student, in the student's own language.")
    citations: list[Citation] = Field(default_factory=list)
    confidence: Confidence
    next_steps: list[str] = Field(default_factory=list, description="0-3 short, concrete next steps.")
    human_contact: Optional[Contact] = None

    @model_validator(mode="after")
    def high_or_medium_needs_a_citation(self):
        if self.confidence in ("High", "Medium") and not self.citations:
            raise ValueError(
                f"confidence={self.confidence!r} needs at least one citation "
                "(an answer with no source must use confidence='Low')"
            )
        return self

    @model_validator(mode="after")
    def next_steps_stay_short(self):
        if len(self.next_steps) > 3:
            raise ValueError("next_steps should be at most 3 items")
        return self

    @model_validator(mode="after")
    def citation_ids_look_real(self):
        for c in self.citations:
            sid = c.source_id
            if not (sid.startswith("deadlines:") or sid.startswith("programs:") or "::" in sid):
                raise ValueError(
                    f"citation source_id {sid!r} does not look like a real tool id "
                    "(expected 'doc::NN', 'deadlines:id' or 'programs:id')"
                )
        return self
