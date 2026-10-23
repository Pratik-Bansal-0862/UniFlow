from fastapi import APIRouter

from app.api.v1.embedding_explorer import router as embedding_explorer_router
from app.api.v1 import auth, documents, health, opportunities, orchestrator, profile

api_router = APIRouter()

api_router.include_router(embedding_explorer_router)
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router, tags=["Authentication"])
api_router.include_router(
    documents.router,
    prefix="/documents",
    tags=["Documents"],
)
api_router.include_router(
    orchestrator.router,
    prefix="/orchestrator",
    tags=["Orchestrator"],
)
api_router.include_router(
    opportunities.router,
    prefix="/opportunities",
    tags=["Opportunities"],
)
api_router.include_router(
    profile.router,
    prefix="/profile",
    tags=["Student Profile"],
)
