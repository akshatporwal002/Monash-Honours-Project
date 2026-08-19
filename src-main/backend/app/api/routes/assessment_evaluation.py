"""Learner-triggered, provider-backed provisional assessment evaluation."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.dependencies.roles import CurrentStudent
from app.db.session import get_db
from app.domain.assessment import AssessmentReasonCode, AssessmentResult, ResultState
from app.services.assessment.evaluation import (
    AssessmentEvaluationConflictError,
    AssessmentEvaluationFaultError,
    AssessmentEvaluationNotFoundError,
    AssessmentEvaluationService,
    UnavailableCriterionEvaluationPort,
    UnavailableQualityReviewPort,
)

router = APIRouter(prefix="/assessment")


class AssessmentEvaluationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    evaluation_idempotency_key: str = Field(min_length=1, max_length=255)


class AssessmentEvaluationRead(BaseModel):
    decision_id: str
    result: AssessmentResult
    result_state: ResultState
    reason_code: AssessmentReasonCode
    replayed: bool


def get_assessment_evaluation_service(
    request: Request,
    session: Annotated[Session, Depends(get_db)],
) -> AssessmentEvaluationService:
    return AssessmentEvaluationService(
        session,
        criterion_port=UnavailableCriterionEvaluationPort(),
        quality_port=UnavailableQualityReviewPort(),
        correlation_id=getattr(request.state, "correlation_id", None),
    )


EvaluationService = Annotated[
    AssessmentEvaluationService, Depends(get_assessment_evaluation_service)
]


@router.post(
    "/attempts/{assessment_attempt_id}/evaluate",
    response_model=AssessmentEvaluationRead,
    status_code=status.HTTP_201_CREATED,
)
def evaluate_assessment_attempt(
    assessment_attempt_id: str,
    payload: AssessmentEvaluationCreate,
    student: CurrentStudent,
    service: EvaluationService,
) -> AssessmentEvaluationRead:
    try:
        result = service.evaluate(
            assessment_attempt_id=assessment_attempt_id,
            evaluation_idempotency_key=payload.evaluation_idempotency_key,
            actor_user_id=student.id,
        )
    except AssessmentEvaluationNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assessment attempt not found"
        ) from error
    except AssessmentEvaluationConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except AssessmentEvaluationFaultError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from error
    return AssessmentEvaluationRead(**result.__dict__)
