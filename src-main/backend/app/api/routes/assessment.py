"""Assessor-only setup and publication endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

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
from app.models.assessment import AssessmentDefinitionVersion
from app.models.user import RoleAssignment, UserRole
from app.schemas.lms import (
    AssessmentCriterionRead,
    AssessmentDefinitionApproval,
    AssessmentDefinitionDraftCreate,
    AssessmentDefinitionRead,
    AssessmentTaskFormRead,
    ScopedRoleAssignmentCreate,
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
from app.services.assessment.repository import AssessmentDefinitionNotFoundError
from app.services.lms import LmsServiceError

router = APIRouter(prefix="/assessment")

RoleAssignments = Annotated[RoleAssignmentService, Depends(get_role_assignment_service)]
Definitions = Annotated[AssessmentDefinitionService, Depends(get_assessment_definition_service)]
PublicationPolicy = Annotated[
    AssessmentPublicationPolicy, Depends(get_assessment_publication_policy)
]


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
        )
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
            detail="Assessment publication is blocked until the live-pilot policy is approved",
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
            AssessmentCriterionRead(
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
