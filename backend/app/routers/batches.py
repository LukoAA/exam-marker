"""Batches: create a batch under a course+scheme, upload scripts (PDFs) into
it, and check its status. No marking is triggered here — that's Phase 3
(Celery `mark_batch`/`mark_script`); this endpoint only ingests and
preprocesses the scans so a script and its pages exist to mark later.

Ownership is enforced transitively through the batch's course.
"""
from __future__ import annotations

import tempfile
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.marking.preprocess import preprocess_pdf
from app.models import Batch, Course, MarkingScheme, Script, ScriptPage, User
from app.routers.auth import get_current_user
from app.storage import StorageService, get_storage_service

router = APIRouter(prefix="/batches", tags=["batches"])


class BatchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_id: int
    scheme_id: int
    name: str = Field(min_length=1, max_length=255)


class BatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    scheme_id: int
    name: str
    status: str


class ScriptOut(BaseModel):
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


class BatchDetailOut(BatchOut):
    scripts: list[ScriptOut]


def _get_owned_batch(batch_id: int, current_user: User, db: Session) -> Batch:
    batch = (
        db.query(Batch)
        .join(Course, Batch.course_id == Course.id)
        .filter(Batch.id == batch_id, Course.user_id == current_user.id)
        .first()
    )
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="batch not found")
    return batch


@router.post("", response_model=BatchOut, status_code=status.HTTP_201_CREATED)
def create_batch(
    payload: BatchCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Batch:
    course = db.query(Course).filter(Course.id == payload.course_id).first()
    if course is None or course.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="course not found")

    scheme = (
        db.query(MarkingScheme)
        .filter(MarkingScheme.id == payload.scheme_id, MarkingScheme.course_id == course.id)
        .first()
    )
    if scheme is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="marking scheme not found for this course",
        )

    batch = Batch(course_id=course.id, scheme_id=scheme.id, name=payload.name)
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


@router.get("/{batch_id}", response_model=BatchDetailOut)
def get_batch(
    batch_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Batch:
    return _get_owned_batch(batch_id, current_user, db)


@router.post("/{batch_id}/scripts", response_model=list[ScriptOut], status_code=status.HTTP_201_CREATED)
def upload_scripts(
    batch_id: int,
    files: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> list[Script]:
    batch = _get_owned_batch(batch_id, current_user, db)

    for upload in files:
        if not (upload.filename or "").lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"'{upload.filename}' is not a PDF",
            )

    created: list[Script] = []
    for upload in files:
        data = upload.file.read()

        script = Script(
            batch_id=batch.id,
            original_filename=upload.filename,
            storage_key="",
            status="queued",
        )
        db.add(script)
        db.flush()  # assigns script.id without committing the transaction

        pdf_key = f"batches/{batch.id}/scripts/{script.id}/original.pdf"
        storage.save_bytes(pdf_key, data)
        script.storage_key = pdf_key

        tmp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(data)
                tmp_path = tmp.name
            pages = preprocess_pdf(tmp_path)
        except Exception:
            script.status = "failed"
            script.page_count = 0
            created.append(script)
            continue
        finally:
            if tmp_path is not None:
                Path(tmp_path).unlink(missing_ok=True)

        for page_number, image in enumerate(pages, start=1):
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            page_key = f"batches/{batch.id}/scripts/{script.id}/pages/{page_number}.png"
            storage.save_bytes(page_key, buffer.getvalue())
            db.add(
                ScriptPage(
                    script_id=script.id, page_number=page_number, image_storage_key=page_key
                )
            )

        script.page_count = len(pages)
        created.append(script)

    db.commit()
    for script in created:
        db.refresh(script)
    return created
