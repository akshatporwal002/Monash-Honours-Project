from app.schemas.feedback import SafeFallbackFeedback

SAFE_FALLBACK_CONTENT = {
    "summary": "Personalized feedback is temporarily unavailable.",
    "explanation": "Your submission was received, but no feedback passed validation.",
    "recommended_next_step": (
        "Review the relevant course material and try again, or ask your educator for help."
    ),
}


def safe_fallback_feedback() -> SafeFallbackFeedback:
    return SafeFallbackFeedback(feedback_content=dict(SAFE_FALLBACK_CONTENT))
