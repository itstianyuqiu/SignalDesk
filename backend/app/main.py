import logging
from uuid import uuid4

from app.core.config import get_settings
from app.services.observability.langsmith_setup import configure_langsmith

configure_langsmith(get_settings())

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

import app.models.case  # noqa: F401  # FK targets before chat/document
import app.models.user  # noqa: F401
import app.models.chat  # noqa: F401  # Register ORM mappers
import app.models.document  # noqa: F401

from app.api.v1.health import router as health_router
from app.api.v1.router import api_router as api_v1_router

_log = logging.getLogger("app.main")


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

    @application.middleware("http")
    async def unhandled_exception_middleware(request: Request, call_next):
        request_id = str(uuid4())
        request.state.request_id = request_id
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        except StarletteHTTPException:
            raise
        except RequestValidationError:
            raise
        except Exception as exc:
            _log.exception(
                "%s %s failed (request_id=%s)",
                request.method,
                request.url.path,
                request_id,
            )
            return JSONResponse(
                status_code=500,
                headers={"X-Request-ID": request_id},
                content={
                    "detail": "Internal server error.",
                    "request_id": request_id,
                },
            )

    # Root health for load balancers / probes (no version prefix).
    application.include_router(health_router)
    # Same contract under the versioned namespace (mirrors root /health).
    application.include_router(health_router, prefix="/api/v1")

    application.include_router(api_v1_router, prefix="/api/v1")

    return application


app = create_app()
