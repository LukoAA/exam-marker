"""SQLAlchemy 2.x table definitions for ExamMarker.

Mirrors the "DATABASE MODEL" section of PROJECT_SPEC.md field for field.
marking_reports, overrides, and audit_log are append-only: the app must only
ever INSERT into them, never UPDATE or DELETE existing rows (corrections and
re-marks are new rows) — see PROJECT_SPEC.md's immutability rule.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# JSONB on Postgres; falls back to plain (TEXT-backed) JSON on other dialects
# so the unit-test suite can use SQLite per PROJECT_SPEC.md.
JSONVariant = JSON().with_variant(JSONB(), "postgresql")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    courses: Mapped[list["Course"]] = relationship(back_populates="user")
    overrides: Mapped[list["Override"]] = relationship(back_populates="user")
    audit_entries: Mapped[list["AuditLog"]] = relationship(back_populates="user")


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    total_marks: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    grading_scale: Mapped[dict] = mapped_column(JSONVariant, nullable=False)
    language: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship(back_populates="courses")
    schemes: Mapped[list["MarkingScheme"]] = relationship(back_populates="course")
    batches: Mapped[list["Batch"]] = relationship(back_populates="course")


class MarkingScheme(Base):
    """Append-only: a new scheme edit is a new version row, never an UPDATE."""

    __tablename__ = "marking_schemes"
    __table_args__ = (
        UniqueConstraint("course_id", "version", name="uq_marking_schemes_course_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    special_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    selection_rule: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    course: Mapped["Course"] = relationship(back_populates="schemes")
    batches: Mapped[list["Batch"]] = relationship(back_populates="scheme")


class Batch(Base):
    __tablename__ = "batches"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_batches_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False, index=True)
    scheme_id: Mapped[int] = mapped_column(
        ForeignKey("marking_schemes.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pending")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    course: Mapped["Course"] = relationship(back_populates="batches")
    scheme: Mapped["MarkingScheme"] = relationship(back_populates="batches")
    scripts: Mapped[list["Script"]] = relationship(back_populates="batch")


class Script(Base):
    __tablename__ = "scripts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'processing', 'marked', 'failed', 'needs_review')",
            name="ck_scripts_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"), nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    student_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    matric_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="queued")
    total_awarded: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    grade: Mapped[str | None] = mapped_column(String(10), nullable=True)
    needs_human_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    model_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    batch: Mapped["Batch"] = relationship(back_populates="scripts")
    pages: Mapped[list["ScriptPage"]] = relationship(back_populates="script")
    marking_reports: Mapped[list["MarkingReport"]] = relationship(back_populates="script")
    overrides: Mapped[list["Override"]] = relationship(back_populates="script")
    appeals: Mapped[list["Appeal"]] = relationship(
        back_populates="script", foreign_keys="Appeal.script_id"
    )


class ScriptPage(Base):
    __tablename__ = "script_pages"
    __table_args__ = (
        UniqueConstraint("script_id", "page_number", name="uq_script_pages_script_page"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    script_id: Mapped[int] = mapped_column(ForeignKey("scripts.id"), nullable=False, index=True)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    image_storage_key: Mapped[str] = mapped_column(String(500), nullable=False)

    script: Mapped["Script"] = relationship(back_populates="pages")


class MarkingReport(Base):
    """Append-only: re-marks (appeals) add a new row, never update a prior report."""

    __tablename__ = "marking_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    script_id: Mapped[int] = mapped_column(ForeignKey("scripts.id"), nullable=False, index=True)
    report_json: Mapped[dict] = mapped_column(JSONVariant, nullable=False)
    transcription: Mapped[str | None] = mapped_column(Text, nullable=True)
    human_readable: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    script: Mapped["Script"] = relationship(back_populates="marking_reports")


class Override(Base):
    """Append-only: never UPDATE or DELETE — a correction is a new row."""

    __tablename__ = "overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    script_id: Mapped[int] = mapped_column(ForeignKey("scripts.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    question: Mapped[str] = mapped_column(String(100), nullable=False)
    old_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    new_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    script: Mapped["Script"] = relationship(back_populates="overrides")
    user: Mapped["User"] = relationship(back_populates="overrides")


class Appeal(Base):
    __tablename__ = "appeals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    script_id: Mapped[int] = mapped_column(ForeignKey("scripts.id"), nullable=False, index=True)
    questions: Mapped[list] = mapped_column(JSONVariant, nullable=False)
    appeal_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_report_id: Mapped[int | None] = mapped_column(
        ForeignKey("marking_reports.id"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="pending")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    script: Mapped["Script"] = relationship(back_populates="appeals", foreign_keys=[script_id])
    result_report: Mapped["MarkingReport | None"] = relationship(
        foreign_keys=[result_report_id]
    )


class AuditLog(Base):
    """Append-only: never UPDATE or DELETE."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    entity: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    detail: Mapped[dict | None] = mapped_column(JSONVariant, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    user: Mapped["User | None"] = relationship(back_populates="audit_entries")
