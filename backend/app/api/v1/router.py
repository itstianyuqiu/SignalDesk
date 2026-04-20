from fastapi import APIRouter

from app.api.v1 import cases, copilot, documents, qa, retrieve, sessions

# Aggregates versioned routes (RAG, tools, observability hooks attach here).
api_router = APIRouter()
api_router.include_router(documents.router)
api_router.include_router(retrieve.router)
api_router.include_router(cases.router)
api_router.include_router(sessions.router)
api_router.include_router(copilot.router)
api_router.include_router(qa.router)
