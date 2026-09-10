from fastapi import APIRouter

from app.api.routes import (
    activity_continuation,
    analytics,
    assessment,
    assessment_evaluation,
    authentication,
    curriculum,
    escalation,
    feedback,
    gamification,
    health,
    learner_model,
    learner_preferences,
    learner_results,
    learning_events,
    lms,
    materials,
    misconceptions,
    progress,
    reassessment,
    reminders,
    research_exports,
    research_governance,
    research_instruments,
    retrieval,
    support_preferences,
    task_generation,
    task_review,
    tutor,
)

api_router = APIRouter()
api_router.include_router(progress.router)
api_router.include_router(health.router, tags=["health"])
api_router.include_router(authentication.router, tags=["authentication"])
api_router.include_router(lms.router, tags=["learning management"])
api_router.include_router(assessment.router, tags=["assessment"])
api_router.include_router(assessment_evaluation.router, tags=["assessment"])
api_router.include_router(materials.router, tags=["learning materials"])
api_router.include_router(retrieval.router, tags=["retrieval"])
api_router.include_router(task_generation.router, tags=["task generation"])
api_router.include_router(task_review.router, tags=["task review"])
api_router.include_router(feedback.router, tags=["feedback"])
api_router.include_router(learning_events.router, tags=["learning-events"])
api_router.include_router(learner_model.router)
api_router.include_router(learner_preferences.router)
api_router.include_router(learner_results.router)
api_router.include_router(reassessment.router)
api_router.include_router(escalation.router)
api_router.include_router(gamification.router)
api_router.include_router(reminders.router)
api_router.include_router(tutor.router)
api_router.include_router(analytics.router, tags=["analytics"])
api_router.include_router(research_exports.router, tags=["research"])
api_router.include_router(research_governance.router)
api_router.include_router(research_instruments.router)

api_router.include_router(curriculum.router)

api_router.include_router(activity_continuation.router)
api_router.include_router(misconceptions.router)


api_router.include_router(support_preferences.router)
