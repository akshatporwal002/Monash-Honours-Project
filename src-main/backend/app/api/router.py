from fastapi import APIRouter

from app.api.routes import (
    analytics,
    feedback,
    health,
    learning_events,
    research_exports,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(feedback.router, tags=["feedback"])
api_router.include_router(learning_events.router, tags=["learning-events"])
api_router.include_router(analytics.router, tags=["analytics"])
api_router.include_router(research_exports.router, tags=["research"])
