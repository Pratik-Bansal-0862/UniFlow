from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.dependencies import get_current_student
from app.services.embedding_explorer_service import EmbeddingExplorerService

router = APIRouter(prefix="/embedding-explorer", tags=["embedding-explorer"])


@router.get("")
def get_embedding_projection(
    limit: int = Query(default=500, ge=1, le=1500),
    current_student=Depends(get_current_student),
):
    student_id = getattr(current_student, "id", None)
    if student_id is None:
        student_id = getattr(current_student, "student_id", None)
    if student_id is None:
        raise HTTPException(status_code=401, detail="Authenticated student identity unavailable")
    try:
        return EmbeddingExplorerService().get_projection(str(student_id), limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail="Stored embedding data is invalid") from exc
