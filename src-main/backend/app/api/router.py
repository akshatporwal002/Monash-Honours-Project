from fastapi import APIRouter

from app.api.routes import (
    analytics,
    assessment,
    assessment_evaluation,
    authentication,
    feedback,
    health,
    learning_events,
    lms,
    materials,
    research_exports,
    retrieval,
    task_generation,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(authentication.router, tags=["authentication"])
api_router.include_router(lms.router, tags=["learning management"])
api_router.include_router(assessment.router, tags=["assessment"])
api_router.include_router(assessment_evaluation.router, tags=["assessment"])
api_router.include_router(materials.router, tags=["learning materials"])
api_router.include_router(retrieval.router, tags=["retrieval"])
api_router.include_router(task_generation.router, tags=["task generation"])
api_router.include_router(feedback.router, tags=["feedback"])
api_router.include_router(learning_events.router, tags=["learning-events"])
api_router.include_router(analytics.router, tags=["analytics"])
api_router.include_router(research_exports.router, tags=["research"])
