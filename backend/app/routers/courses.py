"""Authenticated CRUD for courses, plus append-only marking-scheme versions.

A course is only visible/editable by the user who owns it — every lookup
filters on Course.user_id and returns 404 (not 403) for another user's course
so existence isn't leaked. Marking schemes are append-only: POST always adds
a new version, never updates an existing row.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func as sa_func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Course, MarkingScheme, User
from app.routers.auth import get_current_user

router = APIRouter(prefix="/courses", tags=["courses"])


class CourseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=255)
    total_marks: Decimal = Field(gt=0)
    grading_scale: dict[str, Any]
    language: str = Field(min_length=1, max_length=50)


class CourseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str | None = Field(default=None, min_length=1, max_length=50)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    total_marks: Decimal | None = Field(default=None, gt=0)
    grading_scale: dict[str, Any] | None = None
    language: str | None = Field(default=None, min_length=1, max_length=50)


class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    code: str
    title: str
    total_marks: Decimal
    grading_scale: dict[str, Any]
    language: str


class SchemeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1)
    special_instructions: str | None = None
    selection_rule: str | None = None


class SchemeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    version: int
    content: str
    special_instructions: str | None
    selection_rule: str | None


def _get_owned_course(course_id: int, current_user: User, db: Session) -> Course:
    course = db.query(Course).filter(Course.id == course_id).first()
    if course is None or course.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="course not found")
    return course


@router.post("", response_model=CourseOut, status_code=status.HTTP_201_CREATED)
def create_course(
    payload: CourseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Course:
    course = Course(user_id=current_user.id, **payload.model_dump())
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


@router.get("", response_model=list[CourseOut])
def list_courses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Course]:
    return (
        db.query(Course).filter(Course.user_id == current_user.id).order_by(Course.id).all()
    )


@router.get("/{course_id}", response_model=CourseOut)
def get_course(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Course:
    return _get_owned_course(course_id, current_user, db)


@router.patch("/{course_id}", response_model=CourseOut)
def update_course(
    course_id: int,
    payload: CourseUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Course:
    course = _get_owned_course(course_id, current_user, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(course, field, value)
    db.commit()
    db.refresh(course)
    return course


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    course = _get_owned_course(course_id, current_user, db)
    db.delete(course)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="course has associated schemes or batches and cannot be deleted",
        )


@router.post(
    "/{course_id}/schemes", response_model=SchemeOut, status_code=status.HTTP_201_CREATED
)
def add_scheme_version(
    course_id: int,
    payload: SchemeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MarkingScheme:
    _get_owned_course(course_id, current_user, db)

    latest_version = (
        db.query(sa_func.max(MarkingScheme.version))
        .filter(MarkingScheme.course_id == course_id)
        .scalar()
    )
    scheme = MarkingScheme(
        course_id=course_id,
        version=(latest_version or 0) + 1,
        **payload.model_dump(),
    )
    db.add(scheme)
    db.commit()
    db.refresh(scheme)
    return scheme


@router.get("/{course_id}/schemes", response_model=list[SchemeOut])
def list_scheme_versions(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MarkingScheme]:
    _get_owned_course(course_id, current_user, db)
    return (
        db.query(MarkingScheme)
        .filter(MarkingScheme.course_id == course_id)
        .order_by(MarkingScheme.version)
        .all()
    )
