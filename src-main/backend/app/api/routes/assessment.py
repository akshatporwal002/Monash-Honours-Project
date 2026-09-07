"""Assessor-only setup and publication endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import Field
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.api.assessment_dependencies import (
    AssessmentPublicationPolicy,
    get_assessment_definition_service,
    get_assessment_publication_policy,
    get_role_assignment_service,
    raise_assignment_http_error,
    raise_definition_http_error,
)
from app.api.dependencies.roles import CurrentAdministrator, CurrentEducator, CurrentUser
from app.api.routes.lms import Lms
from app.db.session import get_db
from app.domain.assessment import (
    AssessmentReasonCode,
    AssessmentResult,
    AssessorReviewAction,
    CriterionDecision,
    ResultState,
)
from app.models.assessment import (
    AssessmentAttemptState,
    AssessmentDefinitionVersion,
    AssessmentEvaluationFailureCategory,
    AssessmentEvaluationJobState,
    CriterionEvaluatorType,
)
from app.models.lms import Course
from app.models.user import RoleAssignment, UserRole
from app.schemas.assessment_review import (
    FrozenAssessmentContextRead,
    HistoricalResponseEvidenceRead,
)
from app.schemas.episode import FrozenResponseRead
from app.schemas.lms import (
    AssessmentAuthoringTaskRead,
    AssessmentDefinitionApproval,
    AssessmentDefinitionDraftCreate,
    AssessmentDefinitionDraftUpdate,
    AssessmentDefinitionRead,
    AssessmentTaskCriterionRead,
    AssessmentTaskFormRead,
    AssessorCandidateRead,
    AssessorEligibilityRead,
    AssessorEligibilityWrite,
    LmsSchema,
    ScopedRoleAssignmentCreate,
    ScopedRoleAssignmentHistoryRead,
    ScopedRoleAssignmentRead,
    ScopedRoleAssignmentRevoke,
)
from app.services.assessment.access import RoleAssignmentService, ScopedRoleAccessDeniedError
from app.services.assessment.definitions import (
    AssessmentDefinitionDraft,
    AssessmentDefinitionService,
    CriterionDraft,
    TaskFormDraft,
)
from app.services.assessment.eligibility import AssessorEligibilityService
from app.services.assessment.human_review import (
    HumanAssessmentRequest,
    HumanAssessmentService,
    HumanCriterionInput,
)
from app.services.assessment.repository import AssessmentDefinitionNotFoundError
from app.services.assessment.review import (
    AssessmentReviewActionRequest,
    AssessmentReviewConflictError,
    AssessmentReviewDetail,
    AssessmentReviewFilters,
    AssessmentReviewNotFoundError,
    AssessmentReviewService,
    AssessmentReviewValidationError,
)
from app.services.lms import LmsServiceError

router = APIRouter(prefix="/assessment")

RoleAssignments = Annotated[RoleAssignmentService, Depends(get_role_assignment_service)]
Definitions = Annotated[AssessmentDefinitionService, Depends(get_assessment_definition_service)]
PublicationPolicy = Annotated[
    AssessmentPublicationPolicy, Depends(get_assessment_publication_policy)
]


class AssessmentReviewActionCreate(LmsSchema):
    action: AssessorReviewAction
    reason: Annotated[str, Field(min_length=1, max_length=2_000)]
    expected_result_state: ResultState
    expected_review_revision: Annotated[int, Field(ge=0)]
    new_result: AssessmentResult | None = None


class AssessmentReviewCriterionRead(LmsSchema):
    criterion_version_id: str
    criterion_version: int
    decision: CriterionDecision | None
    reason: str
    evidence_references: dict[str, Any] | list[Any]
    evaluator_reference: str
    model_version: str | None
    prompt_version: str | None
    retrieval_version: str | None
    learner_description: str = ""
    evidence_description: str = ""
    mandatory: bool = True
    met_rule: str = ""
    not_met_rule: str = ""
    not_evaluable_rule: str = ""
    approved_anchors: dict[str, Any] | list[Any] | None = None
    evidence_source_types: list[str] | None = None


class AssessmentReviewHistoryRead(LmsSchema):
    id: str
    review_revision: int
    assessor_user_id: int
    action: AssessorReviewAction
    prior_result: AssessmentResult | None
    new_result: AssessmentResult | None
    reason: str
    reviewed_at: datetime


class AssessmentReviewDetailRead(LmsSchema):
    decision_id: str
    course_id: str
    outcome_id: str
    response_text: str
    response_conditions: dict[str, Any] | list[Any]
    response: FrozenResponseRead | None = None
    response_issues: list[str] = Field(default_factory=list)
    response_history: list[FrozenResponseRead] = Field(default_factory=list)
    historical_evidence: list[HistoricalResponseEvidenceRead] = Field(default_factory=list)
    frozen_context: FrozenAssessmentContextRead | None = None
    simulations: list[dict[str, Any]] = Field(default_factory=list)
    result: AssessmentResult | None
    result_state: ResultState
    system_reason: AssessmentReasonCode
    review_revision: int
    quality_review_status: str
    versions: dict[str, str | int]
    criteria: list[AssessmentReviewCriterionRead]
    missing_criterion_version_ids: list[str]
    history: list[AssessmentReviewHistoryRead]
    created_at: datetime


class AssessmentReviewActionRead(LmsSchema):
    decision_id: str
    review_id: str
    result: AssessmentResult | None
    result_state: ResultState
    review_revision: int
    replayed: bool


def get_assessment_review_service(
    request: Request,
    session: Annotated[Session, Depends(get_db)],
    assignments: RoleAssignments,
) -> AssessmentReviewService:
    from app.services.episode_responses import SqlAlchemyFrozenResponseReader

    return AssessmentReviewService(
        session,
        reader=SqlAlchemyFrozenResponseReader(session),
        assignments=assignments,
        correlation_id=getattr(request.state, "correlation_id", None),
    )


ReviewService = Annotated[AssessmentReviewService, Depends(get_assessment_review_service)]


class HumanCriterionWrite(LmsSchema):
    criterion_version_id: str
    decision: CriterionDecision
    reason: Annotated[str, Field(min_length=1, max_length=2000)]
    evidence_ids: Annotated[list[str], Field(min_length=1, max_length=100)]


class HumanAssessmentWrite(LmsSchema):
    idempotency_key: Annotated[str, Field(min_length=1, max_length=128)]
    expected_token: Annotated[str, Field(min_length=64, max_length=64)]
    reason: Annotated[str, Field(min_length=1, max_length=2000)]
    criteria: Annotated[list[HumanCriterionWrite], Field(min_length=1, max_length=100)]


class UnresolvedCriterionRead(LmsSchema):
    criterion_version_id: str
    criterion_version: int
    learner_description: str
    evidence_description: str
    mandatory: bool
    evidence_source_types: list[str]
    met_rule: str
    not_met_rule: str
    not_evaluable_rule: str
    approved_anchors: dict[str, Any] | list[Any]
    critical_error_rules: dict[str, Any] | list[Any]
    evaluator_type: CriterionEvaluatorType
    decision: CriterionDecision | None
    reason: str | None


class HumanCriterionHistoryRead(LmsSchema):
    criterion_version_id: str
    decision: CriterionDecision
    reason: str
    evidence_references: list[dict[str, Any]]
    evaluator_reference: str


class HumanActionHistoryRead(LmsSchema):
    action_id: str
    revision: int
    assessor_user_id: int
    reason: str
    result: AssessmentResult
    result_state: ResultState
    created_at: datetime
    criteria: list[HumanCriterionHistoryRead]


class UnresolvedAssessmentRead(LmsSchema):
    assessment_attempt_id: str
    course_id: str
    state: AssessmentAttemptState
    job_state: AssessmentEvaluationJobState | None
    failure_category: AssessmentEvaluationFailureCategory | None
    expected_token: str
    response: FrozenResponseRead | None
    response_history: list[FrozenResponseRead] = Field(default_factory=list)
    historical_evidence: list[HistoricalResponseEvidenceRead] = Field(default_factory=list)
    frozen_context: FrozenAssessmentContextRead | None = None
    criteria: list[UnresolvedCriterionRead]
    versions: dict[str, Any]
    simulations: list[dict[str, Any]]
    history: list[HumanActionHistoryRead]
    issues: list[str]
    can_finalise: bool
    created_at: datetime


class HumanAssessmentReceipt(LmsSchema):
    action_id: str
    assessment_attempt_id: str
    decision_id: str
    result: AssessmentResult
    result_state: ResultState
    revision: int
    replayed: bool


def get_human_assessment_service(
    request: Request, session: Annotated[Session, Depends(get_db)], assignments: RoleAssignments
) -> HumanAssessmentService:
    from app.services.episode_responses import SqlAlchemyFrozenResponseReader

    return HumanAssessmentService(
        session,
        assignments=assignments,
        reader=SqlAlchemyFrozenResponseReader(session),
        correlation_id=getattr(request.state, "correlation_id", None),
    )


HumanReviewService = Annotated[HumanAssessmentService, Depends(get_human_assessment_service)]


@router.get(
    "/courses/{course_id}/unresolved-attempts", response_model=list[UnresolvedAssessmentRead]
)
def unresolved_assessment_queue(
    course_id: str,
    actor: CurrentUser,
    service: HumanReviewService,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    try:
        return service.queue(actor, course_id=course_id, limit=limit, offset=offset)
    except Exception as error:
        _raise_review_http_error(error)


@router.get(
    "/attempts/{assessment_attempt_id}/human-review", response_model=UnresolvedAssessmentRead
)
def unresolved_assessment_detail(
    assessment_attempt_id: str, actor: CurrentUser, service: HumanReviewService
):
    try:
        return service.detail(actor, assessment_attempt_id=assessment_attempt_id)
    except Exception as error:
        _raise_review_http_error(error)


@router.post(
    "/attempts/{assessment_attempt_id}/human-review", response_model=HumanAssessmentReceipt
)
def finalise_human_assessment(
    assessment_attempt_id: str,
    payload: HumanAssessmentWrite,
    actor: CurrentUser,
    service: HumanReviewService,
):
    try:
        return service.finalise(
            actor,
            assessment_attempt_id=assessment_attempt_id,
            request=HumanAssessmentRequest(
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
            ),
        )
    except Exception as error:
        _raise_review_http_error(error)


@router.get(
    "/courses/{course_id}/authoring-tasks", response_model=list[AssessmentAuthoringTaskRead]
)
def read_assessment_authoring_tasks(
    course_id: str,
    actor: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    from app.services.assessment.publication import authoring_tasks
    from app.services.task_review import TaskReviewError

    try:
        return authoring_tasks(session, actor, course_id, limit=limit, offset=offset)
    except TaskReviewError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.post(
    "/courses/{course_id}/assessor-eligibility",
    response_model=AssessorEligibilityRead,
    status_code=status.HTTP_201_CREATED,
)
def record_assessor_eligibility(
    course_id: str,
    payload: AssessorEligibilityWrite,
    educator: CurrentEducator,
    request: Request,
    session: Annotated[Session, Depends(get_db)],
):
    try:
        return AssessorEligibilityService(
            session, correlation_id=getattr(request.state, "correlation_id", None)
        ).record(educator, course_id=course_id, **payload.model_dump())
    except Exception as error:
        raise_assignment_http_error(error)
        raise


@router.get(
    "/courses/{course_id}/assessor-eligibility", response_model=list[AssessorEligibilityRead]
)
def read_assessor_eligibility(
    course_id: str,
    actor: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    try:
        return AssessorEligibilityService(session).history(
            actor, course_id, limit=limit, offset=offset
        )
    except Exception as error:
        raise_assignment_http_error(error)
        raise


@router.post(
    "/admin/courses/{course_id}/assignments",
    response_model=ScopedRoleAssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
def assign_scoped_role(
    course_id: str,
    payload: ScopedRoleAssignmentCreate,
    administrator: CurrentAdministrator,
    assignments: RoleAssignments,
) -> RoleAssignment:
    try:
        return assignments.assign(
            administrator,
            subject_user_id=payload.subject_user_id,
            course_id=course_id,
            role=payload.role,
            reason=payload.reason,
            valid_from=payload.valid_from,
            valid_until=payload.valid_until,
        )
    except Exception as error:
        raise_assignment_http_error(error)
        raise


@router.get("/courses/{course_id}/assessor-candidates", response_model=list[AssessorCandidateRead])
def read_assessor_candidates(
    course_id: str,
    actor: CurrentUser,
    session: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    try:
        return AssessorEligibilityService(session).candidates(
            actor, course_id, limit=limit, offset=offset
        )
    except Exception as error:
        raise_assignment_http_error(error)
        raise


@router.get(
    "/admin/courses/{course_id}/assignments",
    response_model=list[ScopedRoleAssignmentHistoryRead],
)
def read_scoped_role_history(
    course_id: str,
    administrator: CurrentAdministrator,
    assignments: RoleAssignments,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    try:
        rows = assignments.history(administrator, course_id, limit=limit, offset=offset)
        return [
            {
                **ScopedRoleAssignmentRead.model_validate(row).model_dump(),
                "currently_active": any(
                    active.id == row.id
                    for active in assignments.list_active_assignments(row.subject_user_id)
                ),
                "revocation_reason": row.revocation_reason,
                "revoked_by_user_id": row.revoked_by_user_id,
            }
            for row in rows
        ]
    except Exception as error:
        raise_assignment_http_error(error)
        raise


@router.delete("/admin/assignments/{assignment_id}", response_model=ScopedRoleAssignmentRead)
def revoke_scoped_role(
    assignment_id: str,
    payload: ScopedRoleAssignmentRevoke,
    administrator: CurrentAdministrator,
    assignments: RoleAssignments,
) -> RoleAssignment:
    try:
        return assignments.revoke(administrator, assignment_id, reason=payload.reason)
    except Exception as error:
        raise_assignment_http_error(error)
        raise


@router.post(
    "/courses/{course_id}/outcomes/{outcome_id}/definitions",
    response_model=AssessmentDefinitionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_assessment_definition_draft(
    course_id: str,
    outcome_id: str,
    payload: AssessmentDefinitionDraftCreate,
    educator: CurrentEducator,
    lms: Lms,
    definitions: Definitions,
) -> AssessmentDefinitionRead:
    source_version = lms.create_assessment_outcome_version(educator, course_id, outcome_id)
    try:
        definition = definitions.create_draft(
            course_id=course_id,
            learning_outcome_id=outcome_id,
            actor_user_id=educator.id,
            draft=_definition_draft(payload, source_version.id),
        )
    except Exception as error:
        definitions.session.rollback()
        raise_definition_http_error(error)
        raise
    return _definition_read(definition)


@router.put(
    "/courses/{course_id}/outcomes/{outcome_id}/definitions/{assessment_definition_id}",
    response_model=AssessmentDefinitionRead,
)
def update_assessment_definition_draft(
    course_id: str,
    outcome_id: str,
    assessment_definition_id: str,
    payload: AssessmentDefinitionDraftUpdate,
    educator: CurrentEducator,
    lms: Lms,
    definitions: Definitions,
) -> AssessmentDefinitionRead:
    source_version = lms.create_assessment_outcome_version(educator, course_id, outcome_id)
    try:
        definition = definitions.update_draft(
            course_id=course_id,
            assessment_definition_id=assessment_definition_id,
            expected_version=payload.expected_version,
            actor_user_id=educator.id,
            draft=_definition_draft(payload, source_version.id),
        )
    except Exception as error:
        definitions.session.rollback()
        raise_definition_http_error(error)
        raise
    return _definition_read(definition)


@router.get(
    "/courses/{course_id}/definitions/{assessment_definition_id}/history",
    response_model=list[AssessmentDefinitionRead],
)
def definition_history(
    course_id: str,
    assessment_definition_id: str,
    actor: CurrentUser,
    lms: Lms,
    assignments: RoleAssignments,
    definitions: Definitions,
) -> list[AssessmentDefinitionRead]:
    _require_definition_history_access(actor, course_id, lms, assignments)
    rows = definitions.repository.list_versions(
        course_id=course_id,
        assessment_definition_id=assessment_definition_id,
    )
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assessment definition not found"
        )
    return [_definition_read(row) for row in rows]


@router.post(
    "/courses/{course_id}/definitions/{assessment_definition_id}/publish",
    response_model=AssessmentDefinitionRead,
)
def publish_assessment_definition(
    course_id: str,
    assessment_definition_id: str,
    payload: AssessmentDefinitionApproval,
    actor: CurrentUser,
    assignments: RoleAssignments,
    definitions: Definitions,
    publication_policy: PublicationPolicy,
) -> AssessmentDefinitionRead:
    try:
        definitions.session.execute(
            update(Course)
            .where(Course.id == course_id)
            .values(id=Course.id, updated_at=Course.updated_at)
        )
        assignments.require_assessor_access(actor, course_id)
    except Exception as error:
        raise_assignment_http_error(error)
        raise
    try:
        version = definitions.repository.get_version(
            course_id=course_id,
            assessment_definition_id=assessment_definition_id,
            version=payload.expected_version,
        )
    except AssessmentDefinitionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment definition not found",
        ) from error
    if version.formal_result_eligible is not True:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Formal result eligibility must be declared before publication",
        )
    if not publication_policy(actor, course_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Current course assessor approval is required for publication",
        )
    try:
        approved = definitions.approve(
            course_id=course_id,
            assessment_definition_id=assessment_definition_id,
            expected_version=payload.expected_version,
            actor_user_id=actor.id,
            approval_reason=payload.reason,
        )
    except Exception as error:
        raise_definition_http_error(error)
        raise
    return _definition_read(approved)


@router.get(
    "/courses/{course_id}/review-queue",
    response_model=list[AssessmentReviewDetailRead],
)
def assessment_review_queue(
    course_id: str,
    actor: CurrentUser,
    service: ReviewService,
    outcome_id: str | None = None,
    result: AssessmentResult | None = None,
    result_state: ResultState | None = None,
    review_flag: str | None = None,
    minimum_age_hours: int | None = Query(default=None, ge=0),
) -> list[AssessmentReviewDetailRead]:
    try:
        details = service.list_queue(
            actor,
            filters=AssessmentReviewFilters(
                course_id=course_id,
                outcome_id=outcome_id,
                result=result,
                result_state=result_state,
                review_flag=review_flag,
                minimum_age_hours=minimum_age_hours,
            ),
        )
    except Exception as error:
        _raise_review_http_error(error)
        raise
    return [_review_detail_read(detail) for detail in details]


@router.get("/decisions/{decision_id}/review", response_model=AssessmentReviewDetailRead)
def assessment_review_detail(
    decision_id: str,
    actor: CurrentUser,
    service: ReviewService,
) -> AssessmentReviewDetailRead:
    try:
        detail = service.get_detail(actor, decision_id=decision_id)
    except Exception as error:
        _raise_review_http_error(error)
        raise
    return _review_detail_read(detail)


@router.post(
    "/decisions/{decision_id}/review",
    response_model=AssessmentReviewActionRead,
)
def record_assessment_review_action(
    decision_id: str,
    payload: AssessmentReviewActionCreate,
    actor: CurrentUser,
    service: ReviewService,
) -> AssessmentReviewActionRead:
    try:
        result = service.act(
            actor,
            decision_id=decision_id,
            request=AssessmentReviewActionRequest(**payload.model_dump()),
        )
    except Exception as error:
        _raise_review_http_error(error)
        raise
    return AssessmentReviewActionRead(**result.__dict__)


def _definition_draft(
    payload: AssessmentDefinitionDraftCreate,
    outcome_version_id: str,
) -> AssessmentDefinitionDraft:
    return AssessmentDefinitionDraft(
        outcome_version_id=outcome_version_id,
        claim=payload.claim,
        supporting_evidence=payload.supporting_evidence,
        contradicting_evidence=payload.contradicting_evidence,
        insufficient_evidence=payload.insufficient_evidence,
        task_conditions=payload.task_conditions,
        next_action_contract=payload.next_action_contract,
        purpose=payload.purpose,
        permitted_tools=payload.permitted_tools,
        instructional_support=payload.instructional_support,
        access_conditions=payload.access_conditions,
        transfer_rule=payload.transfer_rule,
        evidence_sufficiency=payload.evidence_sufficiency,
        formal_result_eligible=payload.formal_result_eligible,
        bloom_process=payload.bloom_process,
        knowledge_dimension=payload.knowledge_dimension,
        criteria=[CriterionDraft(**criterion.model_dump()) for criterion in payload.criteria],
        pass_rule_expression=payload.pass_rule_expression,
        task_forms=[TaskFormDraft(**form.model_dump()) for form in payload.task_forms],
    )


def _review_detail_read(detail: AssessmentReviewDetail) -> AssessmentReviewDetailRead:
    return AssessmentReviewDetailRead(
        decision_id=detail.decision_id,
        course_id=detail.course_id,
        outcome_id=detail.outcome_id,
        response_text=detail.response_text,
        response_conditions=detail.response_conditions,
        response=detail.response,
        response_issues=list(detail.response_issues),
        response_history=list(detail.response_history),
        simulations=list(detail.simulations),
        historical_evidence=list(detail.historical_evidence),
        frozen_context=detail.frozen_context,
        result=detail.result,
        result_state=detail.result_state,
        system_reason=detail.system_reason,
        review_revision=detail.review_revision,
        quality_review_status=detail.quality_review_status,
        versions=detail.versions,
        criteria=[AssessmentReviewCriterionRead(**item.__dict__) for item in detail.criteria],
        missing_criterion_version_ids=list(detail.missing_criterion_version_ids),
        history=[AssessmentReviewHistoryRead(**item.__dict__) for item in detail.history],
        created_at=detail.created_at,
    )


def _raise_review_http_error(error: Exception) -> None:
    if isinstance(error, (AssessmentReviewNotFoundError, ScopedRoleAccessDeniedError)):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assessment review not found"
        ) from error
    if isinstance(error, AssessmentReviewConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    if isinstance(error, AssessmentReviewValidationError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error)
        ) from error
    raise error


def _definition_read(version: AssessmentDefinitionVersion) -> AssessmentDefinitionRead:
    bloom = version.bloom_target_versions[0]
    return AssessmentDefinitionRead(
        id=version.id,
        assessment_definition_id=version.assessment_definition_id,
        course_id=version.course_id,
        outcome_version_id=version.outcome_version_id,
        version=version.version,
        approval_state=version.approval_state,
        purpose=version.purpose,
        bloom_process=bloom.bloom_process,
        knowledge_dimension=bloom.knowledge_dimension,
        claim=version.claim,
        supporting_evidence=version.supporting_evidence,
        contradicting_evidence=version.contradicting_evidence,
        insufficient_evidence=version.insufficient_evidence,
        task_conditions=version.task_conditions,
        next_action_contract=version.next_action_contract,
        permitted_tools=version.permitted_tools,
        instructional_support=version.instructional_support,
        access_conditions=version.access_conditions,
        transfer_rule=version.transfer_rule,
        evidence_sufficiency=version.evidence_sufficiency,
        criteria=[
            AssessmentTaskCriterionRead(
                id=criterion.id,
                stable_key=criterion.criterion.stable_key,
                version=criterion.version,
                learner_description=criterion.learner_description,
                evidence_description=criterion.evidence_description,
                mandatory=criterion.mandatory,
                evidence_source_types=criterion.evidence_source_types,
                met_rule=criterion.met_rule,
                not_met_rule=criterion.not_met_rule,
                not_evaluable_rule=criterion.not_evaluable_rule,
                evaluator_type=criterion.evaluator_type,
            )
            for criterion in version.criterion_versions
        ],
        pass_rule_expression=version.pass_rule_versions[0].expression,
        task_forms=[
            AssessmentTaskFormRead(
                id=form.id,
                learning_task_id=form.learning_task_id,
                task_revision_id=form.task_revision_id,
                version=form.version,
                source_version=form.source_version,
                source_digest=form.source_digest,
                task_family=form.task_family,
                context=form.context,
                constraints=form.constraints,
            )
            for form in version.task_form_versions
        ],
        formal_result_eligible=version.formal_result_eligible,
        approved_at=version.approved_at,
        approved_by_user_id=version.approved_by_user_id,
    )


def _require_definition_history_access(
    actor: CurrentUser,
    course_id: str,
    lms: Lms,
    assignments: RoleAssignmentService,
) -> None:
    if actor.role is UserRole.EDUCATOR:
        try:
            lms.get_course_for_actor(actor, course_id)
            return
        except LmsServiceError:
            pass
    try:
        assignments.require_assessor_access(actor, course_id)
    except ScopedRoleAccessDeniedError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Assessment definition not found"
        ) from error
