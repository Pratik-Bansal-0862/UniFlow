
from typing import Literal, Optional

from pydantic import BaseModel, Field


DocumentCategory = Literal["personal", "reference", "unverified"]


class KnowledgeChunk(BaseModel):
    chunk_id: str
    document_id: str
    student_id: str
    text: str = Field(min_length=1)
    chunk_index: int = Field(ge=0)
    source_name: str
    page_number: int | None = Field(default=None, ge=1)
    category: DocumentCategory = "unverified"


class RetrievedChunk(BaseModel):
    chunk: KnowledgeChunk
    distance: Optional[float]
