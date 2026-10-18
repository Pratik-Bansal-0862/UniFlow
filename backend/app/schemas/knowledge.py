
from pydantic import BaseModel, Field


class KnowledgeChunk(BaseModel):
    chunk_id: str
    document_id: str
    student_id: str
    text: str = Field(min_length=1)
    chunk_index: int = Field(ge=0)
    source_name: str
    page_number: int | None = Field(default=None, ge=1)


class RetrievedChunk(BaseModel):
    chunk: KnowledgeChunk
    distance: float
