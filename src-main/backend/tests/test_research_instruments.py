"""Synthetic instruments and authority records only; no human study approval."""

import json
from types import SimpleNamespace

import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from test_research_governance import governed as governed

from app.core.config import settings
from app.models.research_instruments import (
    ResearchInstrumentBinding,
    ResearchInstrumentForm,
    ResearchInstrumentFreeze,
    ResearchInstrumentRecord,
    RestrictedInstrumentEvidence,
)
from app.schemas.research_governance import INSTRUMENT_FIELDS, PROCESSING_FIELDS
from app.schemas.research_instruments import (
    FormFreeze,
    FormWrite,
    InstrumentAnswer,
    InstrumentDefinition,
    InstrumentExportRequest,
    InstrumentItem,
    InstrumentRecordWrite,
)
from app.services.research import governance
from app.services.research.governance import GovernanceConflict, GovernanceDenied
from app.services.research.governed_export import GovernedResearchExportService
from app.services.research.instruments import EXPORT_FIELDS, ResearchInstrumentService


@pytest.fixture
def instruments(governed, monkeypatch):
    g = governed
    monkeypatch.setattr(
        settings, "learning_event_pseudonym_secret", SecretStr("synthetic-instrument-secret-" * 3)
    )
    g.scope = g.scope.model_copy(
        update={
            "fields": sorted(set(g.scope.fields) | INSTRUMENT_FIELDS),
            "purposes": ["study_instruments"],
            "retention": [
                *g.scope.retention,
                *[
                    g.scope.retention[0].model_copy(update={"record_class": name})
                    for name in (
                        "instrument_definitions",
                        "instrument_records",
                        "restricted_instrument_evidence",
                    )
                ],
            ],
        }
    )
    g.scope_event = g.record(g.scope)
    g.approval = g.approval.model_copy(update={"scope_id": g.scope_event.id})
    g.record(g.approval)
    g.consent = g.consent.model_copy(
        update={
            "scope_id": g.scope_event.id,
            "fields": g.scope.fields,
            "purposes": g.scope.purposes,
        }
    )
    g.consent_event = g.record(g.consent, g.student.id)
    g.eligibility = g.eligibility.model_copy(update={"scope_id": g.scope_event.id})
    g.record(g.eligibility)
    g.grant = g.grant.model_copy(update={"scope_id": g.scope_event.id, "fields": g.scope.fields})
    g.record(g.grant)
    g.instruments = ResearchInstrumentService(g.session, now=lambda: g.now)
    g.definition = InstrumentDefinition(
        title="SYNTHETIC DRAFT — not a validated questionnaire",
        instrument_kind="process",
        stages=["T0_BASELINE", "T1_STUDY_ACTIVITY", "T2_CONCEPTUAL", "T2_TRANSFER"],
        support_manifest_reference="synthetic-support-only",
        event_reason_codes=["synthetic_fault", "synthetic_correction"],
        items=[
            InstrumentItem(
                item_id="synthetic_choice",
                prompt="Synthetic choice prompt",
                response_type="choice",
                choices=["low", "high"],
            ),
            InstrumentItem(
                item_id="synthetic_integer",
                prompt="Synthetic number prompt",
                response_type="integer",
                minimum=0,
                maximum=9,
            ),
            InstrumentItem(
                item_id="synthetic_text",
                prompt="Synthetic explanation prompt",
                response_type="text",
                max_characters=300,
            ),
        ],
    )
    g.form_command = FormWrite(
        request_key="synthetic-form", expected_version=0, definition=g.definition
    )
    g.form = g.instruments.save_form(
        g.educator.id, g.study, g.course.id, "synthetic_form", g.form_command
    )
    g.freeze = FormFreeze(
        request_key="synthetic-freeze",
        content_digest=g.form.content_digest,
        synthetic_review_reference="synthetic-review-not-approval",
    )
    g.instruments.freeze_form(g.educator.id, g.study, g.course.id, g.form.id, g.freeze)
    g.command = InstrumentRecordWrite(
        request_key="synthetic-response",
        subject_user_id=g.student.id,
        form_version_id=g.form.id,
        sequence_key="synthetic-sequence",
        stage="T0_BASELINE",
        kind="response",
        answers=[
            InstrumentAnswer(item_id="synthetic_choice", choice_code="high"),
            InstrumentAnswer(item_id="synthetic_integer", integer_value=4),
            InstrumentAnswer(
                item_id="synthetic_text",
                response_text='Synthetic private answer: student@example.invalid\n=HYPERLINK("private")',
            ),
        ],
    )
    return g


def collect(g, **changes):
    return g.instruments.collect(
        g.educator.id, g.study, g.course.id, g.command.model_copy(update=changes)
    )


def export(g, *, fields=None, format="json"):
    return g.instruments.export(
        g.educator.id,
        g.study,
        g.course.id,
        InstrumentExportRequest(
            fields=fields or sorted(EXPORT_FIELDS), format=format, stages=g.definition.stages
        ),
    )


def test_version_freeze_replay_and_draft_labels(instruments):
    g = instruments
    read = g.instruments.read_form(g.educator.id, g.study, g.course.id, g.form.id)
    assert (
        read.frozen_for_synthetic_validation and read.definition.review_status == "DRAFT_FOR_REVIEW"
    )
    assert read.production_active is False and read.definition.synthetic_only
    assert (
        g.instruments.save_form(
            g.educator.id, g.study, g.course.id, "synthetic_form", g.form_command
        ).id
        == g.form.id
    )
    assert (
        g.instruments.freeze_form(g.educator.id, g.study, g.course.id, g.form.id, g.freeze).id
        == g.form.id
    )
    first = collect(g)
    changed = g.definition.model_copy(update={"title": "Synthetic revision two"})
    second_form = g.instruments.save_form(
        g.educator.id,
        g.study,
        g.course.id,
        "synthetic_form",
        FormWrite(request_key="v2", expected_version=1, definition=changed),
    )
    assert second_form.version == 2 and not second_form.frozen_for_synthetic_validation
    assert (
        g.instruments.read_form(g.educator.id, g.study, g.course.id, g.form.id).definition
        == g.definition
    )
    assert collect(g).id == first.id
    with pytest.raises(GovernanceDenied, match="not_frozen"):
        collect(g, request_key="v2-response", form_version_id=second_form.id)
    with pytest.raises(GovernanceConflict):
        g.instruments.save_form(
            g.educator.id,
            g.study,
            g.course.id,
            "synthetic_form",
            FormWrite(request_key="stale", expected_version=0, definition=changed),
        )


def test_closed_gate_allows_only_scoped_draft_preparation(instruments, monkeypatch):
    g = instruments
    monkeypatch.setattr(governance, "research_processing_approved", lambda: False)
    assert (
        g.instruments.read_form(g.educator.id, g.study, g.course.id, g.form.id).production_active
        is False
    )
    for action in (
        lambda: collect(g),
        lambda: export(g),
        lambda: g.instruments.read(
            g.educator.id, g.study, g.course.id, "unknown", ["instrument.record_id"]
        ),
    ):
        with pytest.raises(GovernanceDenied, match="research_governance_pending"):
            action()
    assert g.session.scalar(select(ResearchInstrumentRecord)) is None


def test_full_sequence_statuses_correction_and_safe_deterministic_exports(instruments):
    g = instruments
    original = collect(g)
    assert collect(g).id == original.id
    for stage in g.definition.stages[1:]:
        collect(g, request_key=stage, stage=stage)
    for kind in ("missingness", "attrition", "deviation"):
        collect(
            g,
            request_key=kind,
            kind=kind,
            answers=[],
            reason_code="synthetic_fault",
            missing_reason="technical_failure" if kind == "missingness" else None,
        )
    answers = [
        a.model_copy(update={"integer_value": 5}) if a.item_id == "synthetic_integer" else a
        for a in g.command.answers
    ]
    corrected = collect(
        g,
        request_key="correction",
        answers=answers,
        supersedes_id=original.id,
        correction_reason_code="synthetic_correction",
    )
    assert corrected.revision == 2
    assert (
        g.session.get(ResearchInstrumentRecord, original.id).data["answers"][1]["integer_value"]
        == 4
    )
    with pytest.raises(GovernanceConflict, match="revision_changed"):
        collect(
            g,
            request_key="stale-correction",
            supersedes_id=original.id,
            correction_reason_code="synthetic_correction",
        )
    body = b"".join(export(g).body)
    assert body == b"".join(export(g).body)
    rows = json.loads(body)["records"]
    assert original.id not in {row["instrument.record_id"] for row in rows}
    assert corrected.id in {row["instrument.record_id"] for row in rows}
    assert len({row["instrument.participant_id"] for row in rows}) == 1
    assert len({row["instrument.sequence_id"] for row in rows}) == 1
    for private in (
        g.student.email,
        g.educator.email,
        g.course.id,
        "student@example.invalid",
        "HYPERLINK",
        "response_text",
        "subject_user_id",
    ):
        assert private not in body.decode()
    assert (
        g.session.scalar(select(RestrictedInstrumentEvidence))
        .response_text["synthetic_text"]
        .startswith("Synthetic private")
    )
    csv = b"".join(export(g, format="csv").body)
    assert csv == b"".join(export(g, format="csv").body) and b"HYPERLINK" not in csv
    subset = json.loads(b"".join(export(g, fields=["instrument.stage"]).body))["records"]
    assert all(set(row) == {"instrument.stage"} for row in subset)


@pytest.mark.parametrize(
    "denial",
    ["field", "actor", "study", "course", "user", "withdrawn", "revoked", "eligibility", "scope"],
)
def test_collection_and_read_fail_closed(instruments, denial):
    g = instruments
    receipt = collect(g)
    actor, study, course, subject = g.educator.id, g.study, g.course.id, g.student.id
    if denial == "field":
        g.record(
            g.grant.model_copy(
                update={"fields": [f for f in g.grant.fields if f != "instrument.integer_value"]}
            )
        )
    elif denial == "actor":
        actor = g.admin.id
    elif denial == "study":
        study = "foreign-study"
    elif denial == "course":
        course = "foreign-course"
    elif denial == "user":
        subject = g.educator.id
    elif denial == "withdrawn":
        g.record(
            g.consent.model_copy(update={"decision": "withdrawn", "fields": [], "purposes": []}),
            g.student.id,
        )
    elif denial == "revoked":
        g.record(g.grant.model_copy(update={"revoked": True}))
    elif denial == "eligibility":
        g.record(g.eligibility.model_copy(update={"eligible": False}))
    else:
        g.record(g.scope)
    with pytest.raises(GovernanceDenied):
        g.instruments.collect(
            actor,
            study,
            course,
            g.command.model_copy(update={"request_key": "denied", "subject_user_id": subject}),
        )
    if denial != "user":
        with pytest.raises(GovernanceDenied):
            g.instruments.read(actor, study, course, receipt.id, ["instrument.integer_value"])


def test_withdrawal_before_and_during_stream_and_reconsent(instruments):
    g = instruments
    receipt = collect(g)
    prepared = export(g)
    stream = prepared.body
    next(stream)  # JSON envelope, no participant values.
    next(stream)  # First item only.
    g.record(
        g.consent.model_copy(update={"decision": "withdrawn", "fields": [], "purposes": []}),
        g.student.id,
    )
    with pytest.raises(GovernanceDenied):
        next(stream)
    assert json.loads(b"".join(export(g).body))["records"] == []
    g.record(g.consent, g.student.id)
    with pytest.raises(GovernanceDenied, match="consent_version_changed"):
        g.instruments.read(g.educator.id, g.study, g.course.id, receipt.id, ["instrument.stage"])


@pytest.mark.parametrize(
    "field", ["instrument.response_text", "processing.provider_input", "subject_user_id", "*"]
)
def test_raw_and_foreign_fields_never_export_even_with_no_records(instruments, field):
    g = instruments
    with pytest.raises(GovernanceDenied):
        g.instruments.export(
            g.educator.id,
            g.study,
            g.course.id,
            SimpleNamespace(fields=[field], stages=g.definition.stages, format="json"),
        )


def test_instrument_permissions_do_not_expand_technical_pair_contract(instruments):
    assert PROCESSING_FIELDS.isdisjoint(INSTRUMENT_FIELDS)
    assert len(PROCESSING_FIELDS) == 34
    g = instruments
    technical = GovernedResearchExportService(
        g.session, g.educator.id, g.study, ["instrument.stage"]
    )
    technical.policy.now = lambda: g.now
    with pytest.raises(GovernanceDenied):
        technical._authorize([g.course.id])
    with pytest.raises(ValidationError):
        g.scope.model_validate(
            {
                **g.scope.model_dump(),
                "retention": [
                    r.model_dump()
                    for r in g.scope.retention
                    if r.record_class != "instrument_records"
                ],
            }
        )


@pytest.mark.parametrize(
    "model",
    [
        ResearchInstrumentForm,
        ResearchInstrumentFreeze,
        ResearchInstrumentBinding,
        ResearchInstrumentRecord,
        RestrictedInstrumentEvidence,
    ],
)
def test_history_is_immutable_in_orm_and_sql(instruments, model):
    g = instruments
    collect(g)
    row = g.session.scalar(select(model))
    g.session.delete(row)
    with pytest.raises(ValueError, match="immutable"):
        g.session.flush()
    g.session.rollback()
    with pytest.raises(IntegrityError):
        g.session.execute(text(f"DELETE FROM {model.__tablename__}"))
    g.session.rollback()


@pytest.mark.parametrize(
    "change", ["missing_item", "invalid_choice", "invalid_integer", "wrong_stage", "foreign_link"]
)
def test_definition_bounds_and_learning_link_scope(instruments, change):
    g = instruments
    changes = {"request_key": "invalid"}
    if change == "missing_item":
        changes["answers"] = g.command.answers[:1]
    elif change == "invalid_choice":
        changes["answers"] = [
            g.command.answers[0].model_copy(update={"choice_code": "unknown"}),
            *g.command.answers[1:],
        ]
    elif change == "invalid_integer":
        changes["answers"] = [
            g.command.answers[0],
            g.command.answers[1].model_copy(update={"integer_value": 20}),
            g.command.answers[2],
        ]
    elif change == "wrong_stage":
        changes["stage"] = "T3_TRANSFER"
    else:
        changes["links"] = g.command.links.model_copy(update={"task_id": "foreign-task"})
    with pytest.raises(GovernanceDenied):
        collect(g, **changes)


def test_explicit_missingness_and_cross_participant_correction(instruments):
    g = instruments
    missing = [
        InstrumentAnswer(item_id=a.item_id, missing_reason="participant_skipped")
        for a in g.command.answers
    ]
    original = collect(g, answers=missing)
    rows = g.instruments.read(
        g.educator.id,
        g.study,
        g.course.id,
        original.id,
        ["instrument.integer_value", "instrument.missing_reason"],
    )
    assert all(
        row
        == {"instrument.integer_value": None, "instrument.missing_reason": "participant_skipped"}
        for row in rows
    )
    with pytest.raises(GovernanceDenied):
        collect(
            g,
            request_key="foreign-correction",
            subject_user_id=g.educator.id,
            supersedes_id=original.id,
            correction_reason_code="synthetic_correction",
        )


def test_concurrent_collection_replay_and_correction(instruments):
    from concurrent.futures import ThreadPoolExecutor

    from sqlalchemy.orm import Session

    g = instruments
    engine, actor, study, course, now, command = (
        g.session.get_bind(),
        g.educator.id,
        g.study,
        g.course.id,
        g.now,
        g.command,
    )
    g.session.rollback()

    def run(payload):
        with Session(engine) as session:
            try:
                return (
                    ResearchInstrumentService(session, now=lambda: now)
                    .collect(actor, study, course, payload)
                    .id
                )
            except GovernanceConflict:
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        identities = list(pool.map(run, [command, command]))
    assert identities[0] == identities[1] != "conflict"
    corrections = [
        command.model_copy(
            update={
                "request_key": f"correction-{index}",
                "supersedes_id": identities[0],
                "correction_reason_code": "synthetic_correction",
            }
        )
        for index in range(2)
    ]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, corrections))
    assert results.count("conflict") == 1


@pytest.mark.parametrize("historical", [False, True])
def test_learning_stage_links_are_owned_read_only_and_pseudonymous(instruments, historical):
    from datetime import timedelta

    from app.models.enums import TaskType
    from app.models.lms import (
        AttemptStatus,
        CourseModule,
        LearningOutcome,
        OutcomeKind,
        SubmissionAttempt,
        SubmissionDraft,
    )
    from app.models.persistence import LearningTask

    g = instruments
    module = CourseModule(course_id=g.course.id, title="Synthetic", position=1)
    g.session.add(module)
    g.session.flush()
    outcome = LearningOutcome(
        module_id=module.id,
        title="Synthetic",
        statement="Synthetic outcome",
        kind=OutcomeKind.TOPIC,
        position=1,
    )
    g.session.add(outcome)
    g.session.flush()
    task = LearningTask(
        slug="synthetic-linked",
        title="Synthetic",
        module="Synthetic",
        description="Synthetic",
        instructions="Synthetic instructions",
        task_type=TaskType.SHORT_ANSWER,
        difficulty="introductory",
        points=0,
        position=1,
        course_id=g.course.id,
        module_id=module.id,
        learning_outcome_id=outcome.id,
    )
    g.session.add(task)
    g.session.flush()
    draft = SubmissionDraft(
        student_id=g.student.id, task_id=task.id, answer="Synthetic private operational answer"
    )
    g.session.add(draft)
    g.session.flush()
    response = SubmissionAttempt(
        draft_id=draft.id,
        student_id=g.student.id,
        task_id=task.id,
        attempt_number=1,
        status=AttemptStatus.SUBMITTED,
        answer=draft.answer,
        feedback="Recorded",
        submitted_at=g.now - timedelta(seconds=1) if historical else g.now,
    )
    g.session.add(response)
    g.session.commit()
    links = g.command.links.model_copy(
        update={"outcome_id": outcome.id, "task_id": task.id, "response_id": response.id}
    )
    if historical:
        with pytest.raises(GovernanceDenied, match="historical_use_not_approved"):
            collect(g, links=links)
        return
    record = collect(g, links=links)
    fields = ["instrument.outcome_ref", "instrument.task_ref", "instrument.response_ref"]
    projected = g.instruments.read(g.educator.id, g.study, g.course.id, record.id, fields)
    assert all(value.startswith("v1_") for value in projected[0].values())
    assert all(
        identity not in json.dumps(projected)
        for identity in (outcome.id, task.id, response.id, response.answer)
    )
    assert g.session.get(SubmissionAttempt, response.id).answer == draft.answer
    with pytest.raises(GovernanceDenied, match="formal_observation_reference_required"):
        collect(g, request_key="no-formal-result", links=links, stage="T1_FORMAL_UNAIDED")
