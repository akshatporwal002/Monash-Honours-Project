"""Production composition for source-grounded feedback context collection."""

from sqlalchemy.orm import Session

from app.services.feedback.context import DefaultFeedbackContextCollector
from app.services.feedback.providers import SqlAlchemyTaskProvider
from app.services.rag.feedback_adapter import RagFeedbackRetrievalProvider
from app.services.rag.retrieval import RetrievalService


def build_grounded_feedback_context_collector(
    session: Session, retrieval: RetrievalService
) -> DefaultFeedbackContextCollector:
    """Build the collector used by feedback workflows with grounded RAG evidence."""
    return DefaultFeedbackContextCollector(
        SqlAlchemyTaskProvider(session),
        retrieval_provider=RagFeedbackRetrievalProvider(retrieval),
    )
