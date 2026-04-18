from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models.document  # noqa: F401  # Register ORM mappers

from app.api.v1.health import router as health_router
from app.api.v1.router import api_router as api_v1_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="Support Intelligence Platform API",
        version="0.1.0",
        description="Backend API for the Support Intelligence Platform.",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Root health for load balancers / probes (no version prefix).
    application.include_router(health_router)
    # Same contract under the versioned namespace (mirrors root /health).
    application.include_router(health_router, prefix="/api/v1")

    application.include_router(api_v1_router, prefix="/api/v1")

    return application


app = create_app()
