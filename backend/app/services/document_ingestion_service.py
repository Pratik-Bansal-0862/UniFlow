import uuid

from sqlalchemy.orm import Session

from app.integrations.chroma_vector_store import ChromaVectorStore
from app.schemas.knowledge import KnowledgeChunk
from app.services.document_chunking_service import chunk_text
from app.services.document_extraction_service import extract_text
from app.services.embedding_service import EmbeddingService
from app.models.document import Document


class DocumentIngestionService:
    def __init__(
        self,
        vector_store: ChromaVectorStore | None = None,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self.vector_store = vector_store or ChromaVectorStore()
        self.embedding_service = embedding_service or EmbeddingService()

    def ingest(
        self,
        db: Session,
        *,
        student_id: uuid.UUID,
        filename: str,
        content: bytes,
    ) -> Document:
        if not content:
            raise ValueError("Uploaded file is empty.")
        if len(content) > 15 * 1024 * 1024:
            raise ValueError("File exceeds the 15 MB upload limit.")

        safe_filename = filename.replace("\\", "/").rsplit("/", 1)[-1]
        if not safe_filename or safe_filename in {".", ".."}:
            raise ValueError("Invalid filename.")
        if not safe_filename.lower().endswith((".pdf", ".docx")):
            raise ValueError("Unsupported file type. Upload a PDF or DOCX.")

        text = extract_text(safe_filename, content)
        pieces = chunk_text(text)
        if not pieces:
            raise ValueError("No readable text found in the document.")

        document_id = uuid.uuid4()
        document = Document(
            id=document_id,
            student_id=student_id,
            filename=safe_filename[:255],
            content_type=(
                "application/pdf"
                if safe_filename.lower().endswith(".pdf")
                else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ),
            file_size=len(content),
            chunk_count=len(pieces),
            status="indexed",
        )

        chunks = [
            KnowledgeChunk(
                chunk_id=f"{document_id}:{index}",
                document_id=str(document_id),
                student_id=str(student_id),
                text=piece,
                chunk_index=index,
                source_name=safe_filename,
            )
            for index, piece in enumerate(pieces)
        ]

        embeddings = self.embedding_service.embed_texts(pieces)

        try:
            self.vector_store.upsert(chunks, embeddings)
            db.add(document)
            db.commit()
            db.refresh(document)
            return document
        except Exception:
            db.rollback()
            # Remove any vector chunks written before a database failure.
            self.vector_store.delete_document(str(document_id), str(student_id))
            raise
