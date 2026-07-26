from fastapi import APIRouter

from app.api.routes import (
    analytics,
    feedback,
    health,
    learning_events,
    materials,
    retrieval,
    research_exports,
    students,
    task_generation,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(students.router, tags=["student learning"])
api_router.include_router(materials.router, tags=["learning materials"])
api_router.include_router(retrieval.router, tags=["retrieval"])
api_router.include_router(task_generation.router, tags=["task generation"])
api_router.include_router(feedback.router, tags=["feedback"])
api_router.include_router(learning_events.router, tags=["learning-events"])
api_router.include_router(analytics.router, tags=["analytics"])
api_router.include_router(research_exports.router, tags=["research"])
