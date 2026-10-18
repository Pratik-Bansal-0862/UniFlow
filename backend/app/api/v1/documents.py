
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_student, get_db
from app.models.document import Document
from app.models.student import Student
from app.schemas.document import DocumentResponse
from app.services.document_ingestion_service import DocumentIngestionService

router = APIRouter()

MAX_FILE_SIZE = 15 * 1024 * 1024
ALLOWED_EXTENSIONS = (".pdf", ".docx")


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def upload_document(
    file: Annotated[UploadFile, File()],
    current_student: Annotated[Student, Depends(get_current_student)],
    db: Annotated[Session, Depends(get_db)],
) -> Document:
    filename = file.filename or ""

    if not filename.lower().endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file type. Upload a PDF or DOCX.",
        )

    content = file.file.read(MAX_FILE_SIZE + 1)

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds the 15 MB upload limit.",
        )

    try:
        service = DocumentIngestionService()
        return service.ingest(
            db,
            student_id=current_student.id,
            filename=filename,
            content=content,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        # Avoid exposing database, storage, or model internals to clients.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document ingestion failed.",
        ) from exc


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    current_student: Annotated[Student, Depends(get_current_student)],
    db: Annotated[Session, Depends(get_db)],
) -> list[Document]:
    statement = (
        select(Document)
        .where(Document.student_id == current_student.id)
        .order_by(Document.created_at.desc())
    )
    return list(db.scalars(statement).all())
