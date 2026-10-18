from fastapi import APIRouter

from app.api.v1 import auth, documents, health

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router, tags=["Authentication"])
api_router.include_router(
    documents.router,
    prefix="/documents",
    tags=["Documents"],
)
