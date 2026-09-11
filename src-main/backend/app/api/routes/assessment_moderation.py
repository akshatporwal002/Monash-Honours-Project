"""Assessor moderation and administrator-recorded evaluator validation evidence."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.api.dependencies.roles import CurrentAdministrator, CurrentUser
from app.api.routes.assessment import HumanAssessmentWrite, get_human_assessment_service
from app.db.session import get_db
from app.schemas.assessment_moderation import (
    EvaluatorValidationReceipt,
    EvaluatorValidationStatusRead,
    ModerationAction,
    ModerationPolicyReceipt,
    ModerationQueueRead,
    ModerationReviewReceipt,
)
from app.services.assessment.access import RoleAssignmentService, ScopedRoleAccessDeniedError
from app.services.assessment.evaluator_release import EvaluatorReleaseService
from app.services.assessment.evidence import EvidenceValidationError
from app.services.assessment.human_review import (
    HumanAssessmentRequest,
    HumanAssessmentService,
    HumanCriterionInput,
)
from app.services.assessment.moderation import ModerationService
from app.services.assessment.review import (
    AssessmentReviewConflictError,
    AssessmentReviewNotFoundError,
    AssessmentReviewValidationError,
)

router = APIRouter(prefix="/assessment", tags=["assessment moderation"])
Database = Annotated[Session, Depends(get_db)]
Human = Annotated[HumanAssessmentService, Depends(get_human_assessment_service)]


class ModerationPolicyWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    initial_count: int = Field(ge=0, le=100000)
    later_percent: int = Field(ge=0, le=100)
    drift_interval: int = Field(gt=0, le=100000)
    approval_reference: str = Field(min_length=1, max_length=2000)
    training_reference: str = Field(min_length=1, max_length=2000)
    expires_at: datetime


class EvaluatorValidationWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_fingerprint: str = Field(min_length=64, max_length=64)
    evidence: dict[str, Any]
    expires_at: datetime


def execute(session, operation):
    try:
        result = operation()
        session.commit()
        return result
    except ScopedRoleAccessDeniedError as error:
        session.rollback()
        raise HTTPException(403, "Assessor access required") from error
    except AssessmentReviewNotFoundError as error:
        session.rollback()
        raise HTTPException(404, "Assessment not found") from error
    except AssessmentReviewValidationError as error:
        session.rollback()
        raise HTTPException(422, str(error)) from error
    except EvidenceValidationError as error:
        session.rollback()
        raise HTTPException(
            409, "Frozen criterion evidence is unavailable or not approved"
        ) from error
    except (AssessmentReviewConflictError, IntegrityError, OperationalError) as error:
        session.rollback()
        raise HTTPException(
            409,
            str(error)
            if isinstance(error, AssessmentReviewConflictError)
            else "Review changed. Reload before retrying.",
        ) from error


@router.get("/courses/{course_id}/moderation", response_model=ModerationQueueRead)
def moderation_queue(
    course_id: str, actor: CurrentUser, session: Database, request: Request
) -> ModerationQueueRead:
    return execute(
        session,
        lambda: ModerationService(
            session, correlation_id=getattr(request.state, "correlation_id", None)
        ).queue(actor, course_id),
    )


@router.post("/courses/{course_id}/moderation-policy", response_model=ModerationPolicyReceipt)
def record_policy(
    course_id: str,
    payload: ModerationPolicyWrite,
    actor: CurrentUser,
    session: Database,
    request: Request,
) -> ModerationPolicyReceipt:
    def operation():
        row = ModerationService(
            session, correlation_id=getattr(request.state, "correlation_id", None)
        ).configure(actor, course_id, **payload.model_dump())
        return {"policy_id": row.id, "version": row.version}

    return execute(session, operation)


@router.post("/attempts/{attempt_id}/moderation/{stage}", response_model=ModerationReviewReceipt)
def record_review(
    attempt_id: str,
    stage: ModerationAction,
    payload: HumanAssessmentWrite,
    actor: CurrentUser,
    session: Database,
    human: Human,
    http_request: Request,
) -> ModerationReviewReceipt:
    def operation():
        attempt = human._visible(actor, attempt_id)
        request = HumanAssessmentRequest(
            idempotency_key=payload.idempotency_key,
            expected_token=payload.expected_token,
            reason=payload.reason,
            criteria=tuple(
                HumanCriterionInput(
                    criterion_version_id=entry.criterion_version_id,
                    decision=entry.decision,
                    reason=entry.reason,
                    evidence_ids=tuple(entry.evidence_ids),
                )
                for entry in payload.criteria
            ),
        )
        row = ModerationService(
            session, correlation_id=getattr(http_request.state, "correlation_id", None)
        ).record(actor, attempt, stage, request, human)
        return {"review_id": row.id, "stage": row.stage, "result": row.result}

    return execute(session, operation)


@router.get(
    "/courses/{course_id}/evaluator-validation", response_model=EvaluatorValidationStatusRead
)
def evaluator_status(
    course_id: str, actor: CurrentUser, session: Database, request: Request
) -> EvaluatorValidationStatusRead:
    def operation():
        RoleAssignmentService(session).require_assessor_access(actor, course_id)
        return EvaluatorReleaseService(
            session, correlation_id=getattr(request.state, "correlation_id", None)
        ).status(course_id)

    return execute(session, operation)


@router.post("/courses/{course_id}/evaluator-validation", response_model=EvaluatorValidationReceipt)
def record_validation(
    course_id: str,
    payload: EvaluatorValidationWrite,
    actor: CurrentAdministrator,
    session: Database,
    request: Request,
) -> EvaluatorValidationReceipt:
    def operation():
        row = EvaluatorReleaseService(
            session, correlation_id=getattr(request.state, "correlation_id", None)
        ).validate(actor, course_id, **payload.model_dump())
        return {"validation_id": row.id, "state": row.state, "ai_activation": "PENDING"}

    return execute(session, operation)
