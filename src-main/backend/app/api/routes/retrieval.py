"""Course-scoped source retrieval API."""
# ruff: noqa: B008

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.routes.materials import _require_read, get_actor_id, get_course_access_policy
from app.db.session import get_db_session
from app.schemas.content import RetrievalResultRead, RetrievalSearchRequest
from app.services.rag.contracts import CourseAccessPolicy, RetrievalPurpose, RetrievalQuery
from app.services.rag.embeddings import SentenceTransformerEmbeddingProvider
from app.services.rag.retrieval import RetrievalService
from app.services.rag.vector_store import ChromaVectorStore

router = APIRouter(prefix="/courses/{course_id}/retrieval")


def get_retrieval_service(db: Session = Depends(get_db_session)) -> RetrievalService:
    embedding = SentenceTransformerEmbeddingProvider()
    return RetrievalService(db, embedding, ChromaVectorStore(embedding.model_id, embedding.dimension))


@router.post("/search", response_model=RetrievalResultRead)
def search_course_content(
    course_id: str,
    payload: RetrievalSearchRequest,
    actor_id: str = Depends(get_actor_id),
    policy: CourseAccessPolicy = Depends(get_course_access_policy),
    service: RetrievalService = Depends(get_retrieval_service),
) -> RetrievalResultRead:
    _require_read(policy, actor_id, course_id)
    try:
        return RetrievalResultRead.model_validate(
            service.search(
                RetrievalQuery(
                    course_id=course_id, text=payload.query, purpose=RetrievalPurpose.SEARCH,
                    module_id=payload.module_id, top_k=payload.top_k, min_relevance=payload.minimum_relevance,
                )
            )
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail={"code": "invalid_query", "message": str(error)}) from error
