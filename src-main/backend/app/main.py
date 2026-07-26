import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.feedback_dependencies import (
    FeedbackApiException,
    feedback_api_exception_handler,
    feedback_pipeline_exception_handler,
    feedback_request_validation_handler,
)
from app.api.router import api_router
from app.core.config import settings
from app.core.request_context import RequestContextMiddleware
from app.core.security import RequestSizeLimitMiddleware
from app.services.feedback.errors import FeedbackPipelineError


def create_app() -> FastAPI:
    # Raw request targets can contain sensitive identifiers. Application
    # request logging is performed by RequestContextMiddleware using route
    # templates and bounded, sanitized fields.
    logging.getLogger("uvicorn.access").disabled = True
    docs_enabled = not settings.production or settings.api_docs_enabled
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    app.add_middleware(
        RequestSizeLimitMiddleware,
        maximum_bytes=settings.max_request_body_bytes,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Correlation-ID",
            settings.csrf_header_name,
        ],
        expose_headers=[
            "Content-Disposition",
            "Location",
            "Retry-After",
            "X-Correlation-ID",
            "X-Export-ID",
        ],
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_exception_handler(FeedbackApiException, feedback_api_exception_handler)
    app.add_exception_handler(
        FeedbackPipelineError,
        feedback_pipeline_exception_handler,
    )
    app.add_exception_handler(
        RequestValidationError,
        feedback_request_validation_handler,
    )
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
