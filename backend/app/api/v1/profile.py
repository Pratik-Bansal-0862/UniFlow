from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import get_current_student
from app.models.student import Student
from app.services.document_retrieval_service import DocumentRetrievalService
from app.services.llm_service import LLMUnavailableError
from app.services.student_profile_service import StudentProfileService

router = APIRouter()


@router.post("/extract")
def extract_student_profile(
    current_student: Student = Depends(get_current_student),
):
    """Extract an evidence-linked profile for the authenticated student."""
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

            # Fail closed: only positively identified student-owned chunks qualify.
            chunk_student_id = str(
                getattr(chunk, "student_id", "") or ""
            )
            if not chunk_student_id or chunk_student_id != student_id:
                continue

            evidence.append(
                {
                    "category": getattr(chunk, "category", None),
                    "text": getattr(chunk, "text", ""),
                    "document_id": str(
                        getattr(chunk, "document_id", "") or ""
                    ),
                    "filename": getattr(chunk, "source_name", None),
                    "chunk_index": getattr(chunk, "chunk_index", None),
                }
            )

        return StudentProfileService().extract_profile(evidence)

    except LLMUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Profile extraction is temporarily unavailable.",
        ) from exc
    except ValueError as exc:
        import logging
        logging.getLogger(__name__).exception(
            "Student profile extraction validation failed: %s", exc
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The profile response could not be validated.",
        ) from exc
