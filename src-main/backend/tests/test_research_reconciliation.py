"""Synthetic reconciliation evidence; not approval or participant study results."""

import json

import pytest
from test_research_governance import governed as governed
from test_research_instruments import instruments as instruments
from test_research_study import pipeline
from test_research_study import study as study

from app.models.research_study import ResearchStudyEvent
from app.schemas.research_study import StudyExportRequest, StudySelfResponse
from app.services.research.governance import GovernanceDenied
from app.services.research.reconciliation import reconcile


def test_expected_stages_reconcile_responses_explicit_gaps_and_reviews(study):
    g = study
    result = reconcile(g.workflow, g.educator.id, g.study, g.course.id)
    assert [row.status for row in result.rows] == ["unrecorded", "unrecorded"]
    response, packet, rating, outcome = pipeline(g)
    gap = g.workflow.submit_researcher(
        g.educator.id,
        g.study,
        g.course.id,
        StudySelfResponse(
            allocation_id=g.allocation.id,
            record=g.command.model_copy(
                update=dict(
                    request_key="gap",
                    stage="T2_TRANSFER",
                    kind="missingness",
                    answers=[],
                    reason_code="synthetic_fault",
                    missing_reason="technical_failure",
                )
            ),
        ),
    )
    result = reconcile(g.workflow, g.educator.id, g.study, g.course.id)
    assert [row.status for row in result.rows] == ["response", "explicit_gap"]
    assert result.rows[0].observations[0].record_id == response.id
    assert result.rows[0].packet_ids == [packet.id]
    assert result.rows[0].rating_ids == [rating.id]
    assert result.rows[0].outcome_ids == [outcome.id]
    assert result.rows[1].observations[0].record_id == gap.id
    assert result.rows[1].observations[0].missing_reason == "technical_failure"
    data = result.model_dump_json()
    assert "subject_user_id" not in data and "Synthetic private answer" not in data
    for format in ("csv", "json"):
        export = g.workflow.export(
            g.educator.id,
            g.study,
            g.course.id,
            StudyExportRequest(
                format=format,
                fields=[
                    "study.stage",
                    "study.sequence_id",
                    "study.record_kind",
                    "instrument.missing_reason",
                ],
                stages=["T0_BASELINE", "T2_TRANSFER"],
            ),
        )
        body = b"".join(export.body).decode()
        assert "T2_TRANSFER" in body and "technical_failure" in body


@pytest.mark.parametrize("amendment", ["plan", "consent"])
def test_current_reallocation_can_continue_without_reviving_prior_records(study, amendment):
    g = study
    old_response, _, _, _ = pipeline(g)
    if amendment == "plan":
        g.plan = g.write("plan", **{**g.plan_data, "expected_revision": 1})
    else:
        g.record(g.consent, g.student.id)
    assert g.workflow.participant_forms(g.student.id, g.study, g.course.id) == []
    previous = g.session.get(ResearchStudyEvent, g.allocation.id)
    replacement = g.write(
        "allocation",
        subject_user_id=g.student.id,
        plan_id=g.plan.id,
        sequence_key="synthetic-sequence",
        condition="condition_a",
        allocation_evidence_reference="synthetic-amendment",
    )
    current = g.session.get(ResearchStudyEvent, replacement.id)
    assert current.data["sequence_id"] != previous.data["sequence_id"]
    assert [
        a["allocation_id"] for a in g.workflow.participant_forms(g.student.id, g.study, g.course.id)
    ] == [replacement.id]
    result = reconcile(g.workflow, g.educator.id, g.study, g.course.id)
    assert len(result.rows) == 2 and all(row.status == "unrecorded" for row in result.rows)
    assert old_response.id not in result.model_dump_json()
    with pytest.raises(GovernanceDenied):
        g.workflow.submit_self(
            g.student.id,
            g.study,
            g.course.id,
            StudySelfResponse(allocation_id=g.allocation.id, record=g.command),
        )


def test_reconciliation_flags_duplicates_and_excludes_withdrawal(study):
    g = study
    pipeline(g)
    g.workflow.submit_self(
        g.student.id,
        g.study,
        g.course.id,
        StudySelfResponse(
            allocation_id=g.allocation.id,
            record=g.command.model_copy(update={"request_key": "another-response"}),
        ),
    )
    assert reconcile(g.workflow, g.educator.id, g.study, g.course.id).rows[0].status == "ambiguous"
    g.record(g.consent.model_copy(update={"decision": "withdrawn"}), g.student.id)
    result = reconcile(g.workflow, g.educator.id, g.study, g.course.id)
    assert result.rows == [] and result.excluded_counts["consent_inactive"] == 1
    assert "participant_id" not in json.dumps(result.model_dump())


def test_reconciliation_requires_scoped_research_permission(study):
    g = study
    for actor in (g.student.id, g.admin.id):
        with pytest.raises(GovernanceDenied):
            reconcile(g.workflow, actor, g.study, g.course.id)
