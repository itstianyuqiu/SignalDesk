from fastapi import APIRouter

from app.api.v1 import documents, retrieve, sessions

# Aggregates versioned routes (RAG, tools, observability hooks attach here).
api_router = APIRouter()
api_router.include_router(documents.router)
api_router.include_router(retrieve.router)
api_router.include_router(sessions.router)
