from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_student, get_db
from app.models.student import Student
from app.models.student_profile import StudentProfile
from app.services.document_retrieval_service import DocumentRetrievalService
from app.services.llm_service import LLMUnavailableError
from app.services.student_profile_persistence import validate_corrected_profile
from app.services.student_profile_service import PROFILE_FIELDS, StudentProfileService

logger = logging.getLogger(__name__)
router = APIRouter()


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile: dict[str, Any]


def _serialize(row: StudentProfile | None) -> dict[str, Any]:
    if row is None:
        return {
            "profile": {field: [] for field in PROFILE_FIELDS},
            "sources": {},
            "status": "not_generated",
            "updated_at": None,
        }
    return {
        "profile": row.profile,
        "sources": row.sources,
        "status": row.status,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.get("")
def get_student_profile(
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    row = db.get(StudentProfile, current_student.id)
    return _serialize(row)


@router.post("/extract")
def extract_student_profile(
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    student_id = str(current_student.id)

    try:
        results = DocumentRetrievalService().retrieve(
            query=(
                "student personal education skills projects experience "
                "internships certifications interests career goals"
            ),
            student_id=student_id,
            limit=20,
        )

        evidence = []
        for result in results:
            chunk = getattr(result, "chunk", None)
            if chunk is None:
                continue
            chunk_student_id = str(getattr(chunk, "student_id", "") or "")
            if chunk_student_id != student_id:
                continue
            evidence.append({
                "category": getattr(chunk, "category", None),
                "text": getattr(chunk, "text", ""),
                "document_id": str(getattr(chunk, "document_id", "") or ""),
                "filename": getattr(chunk, "source_name", None),
                "chunk_index": getattr(chunk, "chunk_index", None),
            })

        extracted = StudentProfileService().extract_profile(evidence)

        # Do not overwrite a useful saved profile with an empty extraction.
        if extracted["status"] == "no_personal_evidence":
            existing = db.get(StudentProfile, current_student.id)
            if existing is not None:
                return _serialize(existing)
            return extracted

        row = db.get(StudentProfile, current_student.id)
        if row is None:
            row = StudentProfile(
                student_id=current_student.id,
                profile=extracted["profile"],
                sources=extracted["sources"],
                status=extracted["status"],
            )
            db.add(row)
        else:
            row.profile = extracted["profile"]
            row.sources = extracted["sources"]
            row.status = extracted["status"]

        db.commit()
        db.refresh(row)
        return _serialize(row)

    except LLMUnavailableError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Profile extraction is temporarily unavailable.",
        ) from exc
    except ValueError as exc:
        db.rollback()
        logger.warning("Student profile extraction validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The profile response could not be validated.",
        ) from exc
    except Exception:
        db.rollback()
        logger.exception("Could not save student profile")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Profile persistence is unavailable. Check database setup.",
        ) from None


@router.put("")
def update_student_profile(
    payload: ProfileUpdate,
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    row = db.get(StudentProfile, current_student.id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Extract a profile before saving corrections.",
        )

    try:
        allowed_ids = set((row.sources or {}).keys())
        corrected = validate_corrected_profile(payload.profile, allowed_ids)
        row.profile = corrected
        row.status = "corrected"
        db.commit()
        db.refresh(row)
        return _serialize(row)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception:
        db.rollback()
        logger.exception("Could not update student profile")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Profile persistence is unavailable. Check database setup.",
        ) from None
