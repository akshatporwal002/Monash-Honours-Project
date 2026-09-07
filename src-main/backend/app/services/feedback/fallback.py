from app.schemas.feedback import SafeFallbackFeedback

SAFE_FALLBACK_CONTENT = {
    "summary": "Personalized feedback is temporarily unavailable.",
    "explanation": "Your submission was received, but no feedback passed validation.",
    "recommended_next_step": (
        "Review the relevant course material and try again, or ask your educator for help."
    ),
}


ASSESSED_SAFE_FALLBACK_CONTENT = {
    "summary": "Assessed feedback is unavailable.",
    "explanation": "Your response is saved. No assessment result has been changed.",
    "recommended_next_step": "Follow the approved task conditions. Ask your educator about permitted access support.",
}


def safe_fallback_feedback(*, assessed: bool = False) -> SafeFallbackFeedback:
    content = ASSESSED_SAFE_FALLBACK_CONTENT if assessed else SAFE_FALLBACK_CONTENT
    return SafeFallbackFeedback(feedback_content=dict(content))
