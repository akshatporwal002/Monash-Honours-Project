"""Synthetic source/history and governance records for one recovery participant."""

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select

from app.domain.assessment import CriterionDecision
from app.models.assessment import AssessmentAttempt
from app.models.persistence import LearningMaterial
from app.models.source_history import SourceRevision
from app.models.user import RoleAssignment, ScopedRole, User, UserRole
from app.schemas.research_governance import (
    ApprovalDecision,
    ConsentDecision,
    EligibilityDecision,
    GovernanceCommand,
    ResearchGrant,
    StudyScope,
)
from app.services.assessment.access import RoleAssignmentService
from app.services.assessment.human_review import (
    HumanAssessmentRequest,
    HumanAssessmentService,
    HumanCriterionInput,
)
from app.services.episode_responses import SqlAlchemyFrozenResponseReader
from app.services.research.governance import ResearchGovernanceService


def stored_source_history(session, course_id, uploads):
    """Supplement the teaching fixture with current and historical stored source bytes."""
    values = {
        "recovery-source/original.txt": b"Synthetic original: H on zero has equal probabilities.",
        "recovery-source/current.txt": b"Synthetic current: two consecutive H gates restore input.",
    }
    hashes = {key: hashlib.sha256(value).hexdigest() for key, value in values.items()}
    for key, value in values.items():
        path = uploads / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
    current = "recovery-source/current.txt"
    material = LearningMaterial(
        course_id=course_id,
        original_filename="synthetic-recovery-source.txt",
        mime_type="text/plain",
        content_hash="sha256:" + hashes[current],
        storage_key=current,
    )
    session.add(material)
    session.flush()
    for version, key in enumerate(values, 1):
        session.add(
            SourceRevision(
                material_id=material.id,
                course_id=course_id,
                version=version,
                source_label="Synthetic recovery source",
                mime_type="text/plain",
                content_hash="sha256:" + hashes[key],
                storage_key=key,
                extracted_blocks=[],
                extraction_version="task37-synthetic-v1",
                provenance="EXTRACTED",
            )
        )
    session.commit()
    return hashes


def governance_record(session, fixture):
    """Supply synthetic evidence without overriding the production research gate."""
    now = datetime.now(UTC)
    admin = User(
        email=f"task37-custodian-{uuid4().hex}@example.invalid",
        full_name="Synthetic recovery custodian",
        password_hash="not-a-login-credential",
        role=UserRole.ADMINISTRATOR,
    )
    session.add(admin)
    session.flush()
    session.add(
        RoleAssignment(
            subject_user_id=fixture["teacher_id"],
            course_id=fixture["course_id"],
            role=ScopedRole.RESEARCH,
            version=1,
            assigned_by_user_id=admin.id,
            reason="Synthetic recovery grant only",
            assigned_at=now,
            valid_from=now - timedelta(days=1),
        )
    )
    session.commit()
    study = "task37-synthetic-recovery"
    policy = ResearchGovernanceService(session)

    def record(decision, actor=None):
        events = policy.events(study)
        return policy.record(
            actor or admin.id,
            study,
            GovernanceCommand(
                request_key=str(uuid4()),
                expected_revision=events[-1].revision if events else 0,
                reason="synthetic-recovery-only",
                decision=decision,
            ),
        )

    scope = StudyScope(
        protocol_version="synthetic-v1",
        data_plan_version="synthetic-v1",
        consent_version="synthetic-v1",
        eligibility_rule_version="synthetic-v1",
        withdrawal_rule_reference="synthetic-only",
        processing_researcher_id=fixture["teacher_id"],
        course_ids=[fixture["course_id"]],
        fields=["case_id"],
        purposes=["technical_pair"],
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=10),
        retention=[
            dict(
                record_class=name,
                authority_reference="synthetic-only",
                authority_version="v1",
                owner_reference="synthetic-owner",
                trigger="synthetic-closure",
                retention_rule="review-only-no-disposal",
                review_at=now + timedelta(days=20),
            )
            for name in ("governance", "identity_mapping", "technical_pairs", "export_audit")
        ],
    )
    scope_id = record(scope).id
    record(
        ApprovalDecision(
            scope_id=scope_id,
            state="approved",
            authority_reference="synthetic-only",
            evidence_reference="synthetic-only",
            valid_from=scope.valid_from,
            valid_until=scope.valid_until,
        )
    )
    consent = ConsentDecision(
        scope_id=scope_id,
        course_id=fixture["course_id"],
        subject_user_id=fixture["student_id"],
        decision="consented",
        consent_version=scope.consent_version,
        fields=scope.fields,
        purposes=scope.purposes,
    )
    record(consent, fixture["student_id"])
    record(
        EligibilityDecision(
            scope_id=scope_id,
            course_id=fixture["course_id"],
            subject_user_id=fixture["student_id"],
            eligible=True,
            rule_version=scope.eligibility_rule_version,
            evidence_reference="synthetic-only",
            valid_until=scope.valid_until,
        )
    )
    grant = ResearchGrant(
        scope_id=scope_id,
        course_id=fixture["course_id"],
        subject_user_id=fixture["teacher_id"],
        fields=scope.fields,
        valid_from=scope.valid_from,
        valid_until=scope.valid_until,
        authority_reference="synthetic-only",
        evidence_reference="synthetic-only",
    )
    record(grant)
    policy.participant(
        study,
        fixture["course_id"],
        fixture["student_id"],
        fields={"case_id"},
        purposes={"technical_pair"},
    )
    policy.grant(study, fixture["course_id"], fixture["teacher_id"], {"case_id"})
    record(consent.model_copy(update={"decision": "withdrawn"}), fixture["student_id"])
    record(grant.model_copy(update={"revoked": True}))
    return study


def synthetic_assessor_decision(session, fixture, response_id):
    """Exercise the authorised human-service path; this is not expert validation."""
    teacher = session.get(User, fixture["teacher_id"])
    attempt = session.scalar(
        select(AssessmentAttempt).where(AssessmentAttempt.response_version_id == response_id)
    )
    service = HumanAssessmentService(
        session,
        assignments=RoleAssignmentService(session),
        reader=SqlAlchemyFrozenResponseReader(session),
    )
    detail = service.detail(teacher, assessment_attempt_id=attempt.id)
    command = HumanAssessmentRequest(
        idempotency_key="task37-synthetic-human-review",
        expected_token=detail["expected_token"],
        reason="Synthetic assessor fixture verifies preserved frozen evidence.",
        criteria=tuple(
            HumanCriterionInput(
                item["criterion_version_id"],
                CriterionDecision.MET,
                "Synthetic reviewer checked this frozen evidence.",
                (response_id,),
            )
            for item in detail["criteria"]
        ),
    )
    result = service.finalise(teacher, assessment_attempt_id=attempt.id, request=command)
    assert service.finalise(teacher, assessment_attempt_id=attempt.id, request=command)["replayed"]
    return result
