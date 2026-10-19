from app.schemas.document import (
    DocumentResponse,
    DocumentSearchRequest,
    DocumentSearchResponse,
    RetrievedDocumentChunk,
)

from typing import Annotated
import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_student, get_db
from app.models.document import Document
from app.models.student import Student
from app.schemas.document import DocumentResponse
from app.services.document_ingestion_service import DocumentIngestionService
from app.services.document_retrieval_service import DocumentRetrievalService

logger = logging.getLogger(__name__)

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
        logger.exception("Document ingestion failed for file %r", filename)
        # Keep internal details out of the API response.
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

@router.post("/search", response_model=DocumentSearchResponse)
def search_documents(
    request: DocumentSearchRequest,
    current_student: Annotated[Student, Depends(get_current_student)],
) -> DocumentSearchResponse:
    try:
        service = DocumentRetrievalService()

        retrieved_chunks = service.retrieve(
            request.query,
            student_id=str(current_student.id),
            limit=request.limit,
        )

        results = [
            RetrievedDocumentChunk(
                document_id=item.chunk.document_id,
                filename=item.chunk.source_name,
                text=item.chunk.text,
                chunk_index=item.chunk.chunk_index,
                distance=item.distance,
            )
            for item in retrieved_chunks
        ]

        return DocumentSearchResponse(results=results)

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document search failed.",
        ) from exc


