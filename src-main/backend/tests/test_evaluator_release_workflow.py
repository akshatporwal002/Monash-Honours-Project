"""Synthetic signed records exercise D-07 tooling without approving a real evaluator."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from test_live_assessment_moderation import context, evidence, policy, record, reviewer
from test_moderation_review_followups import client_for
from test_task15_migrated_review import migrated  # noqa: F401

from app.core.config import settings
from app.models.assessment import AssessmentDecision
from app.models.assessment_moderation import EvaluatorValidationEvent
from app.models.learning_evidence import EvidenceArtifact
from app.models.user import UserRole
from app.schemas.category_review import CategoryAssessment, ReviewDimension
from app.schemas.evaluator_governance import (
    AssessmentGateEvidence,
    EvaluatorReleaseWrite,
    EvaluatorRevokeWrite,
    SuggestionImportWrite,
)
from app.services.assessment.evaluator_release import EvaluatorReleaseService
from app.services.assessment.review import (
    AssessmentReviewConflictError,
    AssessmentReviewValidationError,
)
from app.services.assessment.suggestions import AssessorSuggestionService

pytestmark = pytest.mark.usefixtures("synthetic_material_scanning")


@pytest.fixture(autouse=True)
def configured_fixture_model(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "local")
    monkeypatch.setattr(settings, "llm_model", "synthetic-recorded-model")


def gate_evidence():
    refs = {
        name: "SYNTHETIC signed evidence reference"
        for name in (
            "approved_population_reference",
            "approved_statistic_reference",
            "uncertainty_reference",
            "task_type_coverage_reference",
            "alternate_form_reference",
            "concise_style_reference",
            "unusual_method_reference",
            "relevant_group_reference",
            "review_triggers_reference",
            "adjudication_reference",
        )
    }
    return {
        **refs,
        "provenance": "EXPERT_RECORDED",
        "experts": [
            {
                "name": f"Synthetic expert {name}",
                "appointment_reference": "fixture appointment",
                "expertise_reference": "fixture expertise",
                "training_reference": "fixture training",
            }
            for name in ("A", "B")
        ],
        "baseline_statistic": "binary agreement",
        "baseline_value": 0.9,
        "approved_minimum_baseline": 0.8,
        "case_count": 120,
        "approved_minimum_case_count": 100,
    }


def setup(session, *, complete=True):
    attempt, response, criterion, owner, human, _ = context(session)
    admin = reviewer(session, owner, attempt.course_id, "release-admin", UserRole.ADMINISTRATOR)
    service = EvaluatorReleaseService(session)
    approved = evidence()
    if complete:
        approved["assessment_gate"] = gate_evidence()
    validation = service.validate(
        admin,
        attempt.course_id,
        expected_fingerprint=service.status(attempt.course_id)["fingerprint"],
        evidence=approved,
        expires_at=datetime.now(UTC) + timedelta(days=2),
    )
    session.commit()
    command = EvaluatorReleaseWrite(
        idempotency_key="release-one",
        validation_id=validation.id,
        expected_fingerprint=validation.fingerprint,
        authority_name="Synthetic authority",
        authority_role="Fixture release authority",
        approval_reference="Fixture signed release",
        approved_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=1),
        task_form_version_ids=[attempt.task_form_version_id],
        provider=settings.llm_provider,
        model=settings.llm_model,
        prompt_version="fixture-prompt-v1",
        retrieval_version="fixture-retrieval-v1",
    )
    return attempt, response, criterion, owner, human, admin, service, command


def output(release, response, criterion):
    return SuggestionImportWrite(
        idempotency_key="output-one",
        release_id=release.id,
        expected_fingerprint=release.fingerprint,
        response_digest=response.content_digest,
        **{
            name: release.evidence["approval"][name]
            for name in ("provider", "model", "prompt_version", "retrieval_version")
        },
        output_reference="Fixture actual output record",
        generated_at=datetime.now(UTC),
        criteria=[
            {
                "criterion_version_id": criterion.id,
                "decision": "MET",
                "reason": "Fixture suggestion",
                "evidence_ids": [response.id],
            }
        ],
    )


def reviewed(suggestions, actor, attempt, command):
    context = suggestions.quality_context(actor, attempt.id, command)
    assessment = CategoryAssessment.model_validate(
        {
            "request_digest": context["request_digest"],
            "reviewer": context["reviewer"],
            "findings": [
                {
                    "dimension": dimension,
                    "outcome": "SATISFIED",
                    "basis": "human",
                    "reason": "Synthetic explicit quality review",
                    "evidence_references": [context["request"]["evidence"][0]["reference"]],
                }
                for dimension in ReviewDimension
            ],
        }
    )
    return command.model_copy(update={"quality_review": assessment})


def test_validation_does_not_release_and_incomplete_gate_cannot_activate(db_session):
    attempt, _, _, _, _, admin, service, command = setup(db_session, complete=False)
    assert service.status(attempt.course_id)["ai_activation"] == "PENDING"
    with pytest.raises(AssessmentReviewValidationError, match="Complete the independent"):
        service.release(admin, attempt.course_id, command)
    assert db_session.scalar(select(AssessmentDecision)) is None


def test_release_import_read_revoke_preserves_human_authority(db_session):
    attempt, response, criterion, owner, human, admin, service, command = setup(db_session)
    release = service.release(admin, attempt.course_id, command)
    db_session.commit()
    assert service.release(admin, attempt.course_id, command).id == release.id
    assert service.status(attempt.course_id)["ai_activation"] == "RELEASED"
    suggestions = AssessorSuggestionService(db_session, human)
    submitted = reviewed(suggestions, owner, attempt, output(release, response, criterion))
    receipt = suggestions.record(owner, attempt.id, submitted)
    db_session.commit()
    assert suggestions.record(owner, attempt.id, submitted)["replayed"]
    shown = suggestions.read(owner, attempt.id)
    assert shown["records"][0]["output"]["criteria"][0]["decision"] == "MET"
    assert shown["records"][0]["advisory"]
    assert db_session.scalar(select(AssessmentDecision)) is None
    assert human.detail(owner, assessment_attempt_id=attempt.id)["criteria"][0]["decision"] is None
    revoke = EvaluatorRevokeWrite(
        idempotency_key="revoke-one",
        expected_validation_id=release.id,
        reason="Fixture authority withdrew permission",
        authority_reference="Fixture withdrawal",
    )
    revoked = service.revoke(admin, attempt.course_id, revoke)
    db_session.commit()
    assert service.revoke(admin, attempt.course_id, revoke).id == revoked.id
    assert suggestions.read(owner, attempt.id)["records"] == []
    assert service.status(attempt.course_id)["ai_activation"] == "PENDING"
    assert db_session.get(EvidenceArtifact, receipt["suggestion_id"]) is not None
    assert len(service.history(admin, attempt.course_id)["history"]) == 3
    assert db_session.scalar(select(AssessmentDecision)) is None


def test_scope_versions_and_independent_review_are_enforced(db_session):
    attempt, response, criterion, owner, human, admin, service, command = setup(db_session)
    with pytest.raises(AssessmentReviewValidationError):
        service.release(owner, attempt.course_id, command)
    with pytest.raises(AssessmentReviewValidationError, match="approved task forms"):
        service.release(
            admin,
            attempt.course_id,
            command.model_copy(update={"task_form_version_ids": ["unknown"]}),
        )
    release = service.release(admin, attempt.course_id, command)
    db_session.commit()
    suggestions = AssessorSuggestionService(db_session, human)
    submitted = output(release, response, criterion)
    with pytest.raises(AssessmentReviewConflictError, match="different frozen"):
        suggestions.record(
            owner,
            attempt.id,
            submitted.model_copy(update={"response_digest": "sha256:" + "0" * 64}),
        )
    with pytest.raises(AssessmentReviewValidationError, match="Output versions"):
        suggestions.record(owner, attempt.id, submitted.model_copy(update={"model": "unapproved"}))
    suggestions.record(owner, attempt.id, submitted)
    second = reviewer(db_session, owner, attempt.course_id, "independent")
    policy(db_session, owner, attempt)
    record(db_session, human, owner, attempt, response, criterion, "ORIGINAL")
    assert suggestions.read(second, attempt.id)["status"] == "WITHHELD"
    assert db_session.scalar(select(AssessmentDecision)) is None


@pytest.mark.parametrize(
    "change",
    [
        {"case_count": 99},
        {"baseline_value": 0.7},
        {"provenance": "SYNTHETIC"},
        {"uncertainty_reference": ""},
        {"unusual_method_reference": ""},
    ],
)
def test_incomplete_or_failed_expert_gate_is_rejected(change):
    with pytest.raises(ValidationError):
        AssessmentGateEvidence.model_validate({**gate_evidence(), **change})


def test_validation_cannot_forge_release_envelope(db_session):
    attempt, _, _, _, _, admin, service, command = setup(db_session)
    with pytest.raises(AssessmentReviewValidationError, match="separate commands"):
        service.validate(
            admin,
            attempt.course_id,
            expected_fingerprint=command.expected_fingerprint,
            evidence={**evidence(), "record_kind": "RELEASE"},
            expires_at=command.expires_at,
        )
    assert len(list(db_session.scalars(select(EvaluatorValidationEvent)))) == 1


@pytest.mark.parametrize("change", ["model", "expiry"])
def test_released_outputs_close_on_change_or_expiry(db_session, monkeypatch, change):
    import app.services.assessment.evaluator_release as module

    attempt, response, criterion, owner, human, admin, service, command = setup(db_session)
    release = service.release(admin, attempt.course_id, command)
    suggestions = AssessorSuggestionService(db_session, human)
    submitted = reviewed(suggestions, owner, attempt, output(release, response, criterion))
    receipt = suggestions.record(owner, attempt.id, submitted)
    db_session.commit()
    if change == "model":
        monkeypatch.setattr(settings, "llm_model", "different-model")
    else:

        class Later(datetime):
            @classmethod
            def now(cls, tz=None):
                return command.expires_at + timedelta(seconds=1)

        monkeypatch.setattr(module, "datetime", Later)
    assert suggestions.read(owner, attempt.id)["status"] == "PENDING"
    db_session.commit()
    assert service.latest(attempt.course_id).state == "INVALIDATED"
    assert db_session.get(EvidenceArtifact, receipt["suggestion_id"]) is not None
    assert db_session.get(EvaluatorValidationEvent, release.id).state == "VALIDATED"
    assert db_session.scalar(select(AssessmentDecision)) is None


def test_governance_api_requires_admin_and_suggestions_require_course_assessor(db_session):
    attempt, _, _, owner, human, admin, service, command = setup(db_session)
    actors = [owner]
    client = client_for(db_session, actors, human)
    base = f"/assessment/courses/{attempt.course_id}"
    assert client.get(base + "/evaluator-governance").status_code == 403
    assert (
        client.post(base + "/evaluator-release", json=command.model_dump(mode="json")).status_code
        == 403
    )
    actors[0] = admin
    assert (
        client.get(base + "/evaluator-governance").json()["forms"][0]["id"]
        == attempt.task_form_version_id
    )
    result = client.post(base + "/evaluator-release", json=command.model_dump(mode="json"))
    assert result.status_code == 200 and result.json()["status"]["ai_activation"] == "RELEASED"
    actors[0] = db_session.get(type(owner), attempt.student_id)
    assert client.get(f"/assessment/attempts/{attempt.id}/ai-suggestions").status_code == 403
    assert service.latest(attempt.course_id).id == result.json()["record_id"]


def test_validation_idempotency_rejects_changed_content(db_session):
    attempt, _, _, _, _, admin, service, command = setup(db_session)
    args = dict(
        expected_fingerprint=command.expected_fingerprint,
        evidence=evidence(),
        expires_at=command.expires_at,
        idempotency_key="same-validation",
    )
    saved = service.validate(admin, attempt.course_id, **args)
    db_session.commit()
    assert service.validate(admin, attempt.course_id, **args).id == saved.id
    with pytest.raises(AssessmentReviewConflictError, match="different content"):
        service.validate(
            admin,
            attempt.course_id,
            **{**args, "evidence": {**evidence(), "expert_review": "changed"}},
        )


def test_frozen_response_failure_closes_suggestions(db_session, monkeypatch):
    from app.services.episode_contract import FrozenResponseMissing

    attempt, _, _, owner, human, admin, service, command = setup(db_session)
    service.release(admin, attempt.course_id, command)
    db_session.commit()

    def unavailable(**_):
        raise FrozenResponseMissing("Fixture response unavailable")

    monkeypatch.setattr(human.reader, "read", unavailable)
    assert (
        AssessorSuggestionService(db_session, human).read(owner, attempt.id)["status"] == "PENDING"
    )


def test_migrated_release_and_suggestion_history_are_immutable(request):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError
    from test_task15_migrated_review import setup_human

    session, _ = request.getfixturevalue("migrated")
    human, owner, attempt, _ = setup_human(session)
    admin = reviewer(
        session, owner, attempt.course_id, "migrated-release-admin", UserRole.ADMINISTRATOR
    )
    service = EvaluatorReleaseService(session)
    validation = service.validate(
        admin,
        attempt.course_id,
        expected_fingerprint=service.status(attempt.course_id)["fingerprint"],
        evidence={**evidence(), "assessment_gate": gate_evidence()},
        expires_at=datetime.now(UTC) + timedelta(days=2),
    )
    session.commit()
    command = EvaluatorReleaseWrite(
        idempotency_key="migrated-release",
        validation_id=validation.id,
        expected_fingerprint=validation.fingerprint,
        authority_name="Fixture authority",
        authority_role="Fixture",
        approval_reference="Fixture signed release",
        approved_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=1),
        task_form_version_ids=[attempt.task_form_version_id],
        provider=settings.llm_provider,
        model=settings.llm_model,
        prompt_version="fixture-v1",
        retrieval_version="fixture-v1",
    )
    release = service.release(admin, attempt.course_id, command)
    bundle = human._bundle(attempt)
    response = human.reader.read(assessment=bundle.reference)
    submitted = SuggestionImportWrite(
        **{
            name: getattr(command, name)
            for name in (
                "expected_fingerprint",
                "provider",
                "model",
                "prompt_version",
                "retrieval_version",
            )
        },
        idempotency_key="migrated-output",
        release_id=release.id,
        response_digest=response.reference.content_digest,
        output_reference="Fixture retained output",
        generated_at=datetime.now(UTC),
        criteria=[
            {
                "criterion_version_id": c.id,
                "decision": "NOT_MET",
                "reason": "Fixture suggestion",
                "evidence_ids": [response.reference.evidence_id],
            }
            for c in bundle.criteria
        ],
    )
    suggestions = AssessorSuggestionService(session, human)
    submitted = reviewed(suggestions, owner, attempt, submitted)
    receipt = suggestions.record(owner, attempt.id, submitted)
    session.commit()
    assert AssessorSuggestionService(session, human).read(owner, attempt.id)["records"]
    for table, identity in (
        ("evaluator_validation_events", release.id),
        ("evidence_artifacts", receipt["suggestion_id"]),
    ):
        with pytest.raises(DBAPIError):
            session.execute(text(f"DELETE FROM {table} WHERE id = :id"), {"id": identity})
        session.rollback()
    assert session.scalar(select(AssessmentDecision)) is None


@pytest.mark.parametrize("failure", ["missing", "unverified", "spoofed", "changed"])
def test_quality_rejection_retains_audit_without_display_or_grading(db_session, failure):
    attempt, response, criterion, owner, human, admin, service, command = setup(db_session)
    release = service.release(admin, attempt.course_id, command)
    suggestions = AssessorSuggestionService(db_session, human)
    submitted = reviewed(suggestions, owner, attempt, output(release, response, criterion))
    raw = submitted.model_dump(mode="json")
    if failure == "missing":
        raw["quality_review"] = None
    elif failure == "unverified":
        raw["quality_review"]["findings"][0]["outcome"] = "UNVERIFIED"
    elif failure == "spoofed":
        raw["quality_review"]["reviewer"]["reference"] = "user:another-assessor"
    else:
        raw["criteria"][0]["reason"] = "Changed after quality review"
    receipt = suggestions.record(owner, attempt.id, SuggestionImportWrite.model_validate(raw))
    db_session.commit()
    assert receipt["quality_decision"] == "REJECTED"
    assert db_session.get(EvidenceArtifact, receipt["suggestion_id"]) is not None
    assert suggestions.read(owner, attempt.id)["records"] == []
    assert db_session.scalar(select(AssessmentDecision)) is None


def test_suggestion_read_rechecks_blinding_after_waiting_for_course_lock(db_session, monkeypatch):
    from app.services.assessment.moderation import ModerationService

    attempt, response, criterion, owner, human, admin, service, command = setup(db_session)
    second = reviewer(db_session, owner, attempt.course_id, "waiting-second")
    release = service.release(admin, attempt.course_id, command)
    suggestions = AssessorSuggestionService(db_session, human)
    submitted = reviewed(suggestions, owner, attempt, output(release, response, criterion))
    suggestions.record(owner, attempt.id, submitted)
    db_session.commit()
    policy(db_session, owner, attempt)
    assert not ModerationService(db_session).withhold_judgements(second, attempt.id)
    original_lock = ModerationService.lock
    arrived = False

    def competing_original_then_lock(moderation, course_id):
        nonlocal arrived
        if not arrived:
            arrived = True
            # Deterministic READ COMMITTED interleaving: another ORIGINAL becomes
            # visible after the initial attempt lookup, before this lock returns.
            record(db_session, human, owner, attempt, response, criterion, "ORIGINAL")
        original_lock(moderation, course_id)

    monkeypatch.setattr(ModerationService, "lock", competing_original_then_lock)
    result = suggestions.read(second, attempt.id)
    assert arrived
    assert result["status"] == "WITHHELD"
    assert result["records"] == []


def test_selected_attempt_withholds_suggestions_until_independent_reviews_are_recorded(db_session):
    from app.models.assessment_moderation import ModerationSelection

    attempt, response, criterion, owner, human, admin, service, command = setup(db_session)
    second = reviewer(db_session, owner, attempt.course_id, "prospective-second")
    release = service.release(admin, attempt.course_id, command)
    suggestions = AssessorSuggestionService(db_session, human)
    submitted = reviewed(suggestions, owner, attempt, output(release, response, criterion))
    receipt = suggestions.record(owner, attempt.id, submitted)
    db_session.commit()
    # The ordinary, unselected assessor path retains D-07 suggestion access.
    assert suggestions.read(owner, attempt.id)["records"][0]["id"] == receipt["suggestion_id"]
    policy(db_session, owner, attempt)
    assert db_session.get(ModerationSelection, attempt.id) is None
    for actor in (owner, second):
        result = suggestions.read(actor, attempt.id)
        assert result["status"] == "WITHHELD"
        assert result["records"] == []
        with pytest.raises(AssessmentReviewConflictError, match="independent moderation"):
            suggestions.quality_context(actor, attempt.id, submitted)
    assert db_session.get(ModerationSelection, attempt.id).selected
    record(db_session, human, owner, attempt, response, criterion, "ORIGINAL")
    assert suggestions.read(owner, attempt.id)["records"][0]["id"] == receipt["suggestion_id"]
    assert suggestions.read(second, attempt.id)["status"] == "WITHHELD"
    record(db_session, human, second, attempt, response, criterion, "SECOND")
    assert suggestions.read(second, attempt.id)["records"][0]["id"] == receipt["suggestion_id"]
    assert db_session.scalar(select(AssessmentDecision)) is None
