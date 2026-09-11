"""One retrieval backend selection for API, generation and feedback."""

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.rag.vector_retrieval import LocalVectorRetrievalService

RetrievalBackend = LocalVectorRetrievalService


def build_retrieval_service(session: Session) -> RetrievalBackend:
    return LocalVectorRetrievalService(
        session, use_vectors=settings.rag_retrieval_backend == "local_vector"
    )
