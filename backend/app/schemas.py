"""Pydantic v2 models for the marking engine's Part A JSON output.

Mirrors the JSON schema in app/marking/prompt_v3.md ("OUTPUT" section) field
for field, plus the `remark` object added in REMARK/appeal mode. engine.py
validates the model's raw JSON against `MarkingReport`; a validation failure
triggers the one-retry-then-fail path described in PROJECT_SPEC.md.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MarkPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scheme_point: str
    decision: Literal["AWARDED", "PARTIAL", "NOT AWARDED"]
    marks: float = Field(ge=0)
    evidence: str
    note: str


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    attempted: bool
    max_marks: float = Field(ge=0)
    awarded: float = Field(ge=0)
    provisional: bool
    mark_points: list[MarkPoint]
    strengths: str
    missing_points: str
    errors: str
    legibility_flags: list[str]

    @model_validator(mode="after")
    def _awarded_within_max(self) -> "Question":
        if self.awarded > self.max_marks:
            raise ValueError(
                f"question {self.question}: awarded ({self.awarded}) exceeds "
                f"max_marks ({self.max_marks})"
            )
        return self


class McqSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    present: bool
    answer_string: str
    correct: int = Field(ge=0)
    wrong: int = Field(ge=0)
    blank: int = Field(ge=0)
    ambiguous: int = Field(ge=0)
    score: float = Field(ge=0)


class PageAnomaly(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(ge=1)
    type: Literal["rotated", "faint", "missing", "torn", "out_of_order"]
    detail: str
    affected_questions: list[str]


class LowConfidenceSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page: int = Field(ge=1)
    question: str
    text: str
    impact: str


class OverallFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concepts_understood: str
    weak_areas: str
    topics_to_revise: str
    summary: str


class RemarkInfo(BaseModel):
    """The `remark` object added to Part A output when MODE = "REMARK"."""

    model_config = ConfigDict(extra="forbid")

    disputed_questions: list[str]
    original_score: float
    new_score: float
    change_justification: str
    appeal_upheld: Literal[True, False, "partial"]


class MarkingReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_name: str | None
    matric_number: str | None
    course_code: str
    needs_human_review: bool
    review_reasons: list[str]
    questions: list[Question]
    mcq_section: McqSection
    page_anomalies: list[PageAnomaly]
    identity_anomalies: list[str]
    total_awarded: float = Field(ge=0)
    total_possible: float = Field(ge=0)
    percentage: float = Field(ge=0, le=100)
    grade: str | None
    low_confidence_sections: list[LowConfidenceSection]
    overall_feedback: OverallFeedback
    remark: RemarkInfo | None = None

    @model_validator(mode="after")
    def _total_within_possible(self) -> "MarkingReport":
        if self.total_awarded > self.total_possible:
            raise ValueError(
                f"total_awarded ({self.total_awarded}) exceeds "
                f"total_possible ({self.total_possible})"
            )
        return self
