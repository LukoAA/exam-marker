"""Script detail and page-image serving.

Ownership is enforced transitively: script -> batch -> course -> user,
same pattern as batches.py.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Batch, Course, MarkingReport, Script, ScriptPage, User
from app.routers.auth import get_current_user
from app.storage import StorageService, get_storage_service

router = APIRouter(prefix="/scripts", tags=["scripts"])


class MarkingReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    report_json: dict[str, Any]
    transcription: str | None
    human_readable: str | None
    created_at: datetime


class ScriptDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_id: int
    original_filename: str
    page_count: int | None
    student_name: str | None
    matric_number: str | None
    status: str
    total_awarded: Decimal | None
    percentage: Decimal | None
    grade: str | None
    needs_human_review: bool
    latest_report: MarkingReportOut | None


def _get_owned_script(script_id: int, current_user: User, db: Session) -> Script:
    script = (
        db.query(Script)
        .join(Batch, Script.batch_id == Batch.id)
        .join(Course, Batch.course_id == Course.id)
        .filter(Script.id == script_id, Course.user_id == current_user.id)
        .first()
    )
    if script is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="script not found")
    return script


@router.get("/{script_id}", response_model=ScriptDetailOut)
def get_script(
    script_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ScriptDetailOut:
    script = _get_owned_script(script_id, current_user, db)

    latest_report = (
        db.query(MarkingReport)
        .filter(MarkingReport.script_id == script.id)
        .order_by(MarkingReport.created_at.desc(), MarkingReport.id.desc())
        .first()
    )

    return ScriptDetailOut(
        id=script.id,
        batch_id=script.batch_id,
        original_filename=script.original_filename,
        page_count=script.page_count,
        student_name=script.student_name,
        matric_number=script.matric_number,
        status=script.status,
        total_awarded=script.total_awarded,
        percentage=script.percentage,
        grade=script.grade,
        needs_human_review=script.needs_human_review,
        latest_report=(
            MarkingReportOut.model_validate(latest_report) if latest_report is not None else None
        ),
    )


@router.get("/{script_id}/pages/{page_number}.png")
def get_script_page(
    script_id: int,
    page_number: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> Response:
    script = _get_owned_script(script_id, current_user, db)

    page = (
        db.query(ScriptPage)
        .filter(ScriptPage.script_id == script.id, ScriptPage.page_number == page_number)
        .first()
    )
    if page is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="page not found")

    try:
        data = storage.read_bytes(page.image_storage_key)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="page image not found in storage"
        )

    return Response(content=data, media_type="image/png")
