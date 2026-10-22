
import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_student, get_db
from app.integrations.chroma_vector_store import ChromaVectorStore
from app.models.document import DOCUMENT_CATEGORIES, Document
from app.models.student import Student
from app.schemas.document import (
    DocumentCategoryUpdate,
    DocumentResponse,
    DocumentSearchRequest,
    DocumentSearchResponse,
    RetrievedDocumentChunk,
)
from app.services.document_answer_service import DocumentAnswerService
from app.services.document_ingestion_service import DocumentIngestionService
from app.services.document_retrieval_service import DocumentRetrievalService
from app.services.embedding_service import EmbeddingService

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
        return DocumentIngestionService().ingest(
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


@router.patch("/{document_id}/category", response_model=DocumentResponse)
def update_document_category(
    document_id: UUID,
    request: DocumentCategoryUpdate,
    current_student: Annotated[Student, Depends(get_current_student)],
    db: Annotated[Session, Depends(get_db)],
) -> Document:
    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.student_id == current_student.id,
        )
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    if request.category not in DOCUMENT_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid document category.",
        )

    vector_store = ChromaVectorStore()

    try:
        # Update Chroma metadata first. If this fails, leave the database
        # record unchanged rather than creating an inconsistent category.
        vector_store.update_document_category(
            document_id=str(document.id),
            student_id=str(current_student.id),
            category=request.category,
        )

        document.category = request.category
        db.commit()
        db.refresh(document)
        return document
    except Exception as exc:
        db.rollback()
        logger.exception(
            "Failed to update category for document %s", document_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update document category.",
        ) from exc


@router.post("/search", response_model=DocumentSearchResponse)
def search_documents(
    request: DocumentSearchRequest,
    current_student: Annotated[Student, Depends(get_current_student)],
) -> DocumentSearchResponse:
    try:
        service = DocumentRetrievalService(
            embedding_service=EmbeddingService(),
            vector_store=ChromaVectorStore(),
        )

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
                category=item.chunk.category,
            )
            for item in retrieved_chunks
        ]

        evidence = [
            {
                "source_name": item.chunk.source_name,
                "page_number": item.chunk.page_number,
                "chunk_index": item.chunk.chunk_index,
                "category": item.chunk.category,
                "text": item.chunk.text[:4000],
            }
            for item in retrieved_chunks
        ]

        answer, answer_status = DocumentAnswerService().answer(
            request.query,
            evidence,
        )

        return DocumentSearchResponse(
            results=results,
            answer=answer,
            answer_status=answer_status,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Document search failed.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document search failed.",
        ) from exc
