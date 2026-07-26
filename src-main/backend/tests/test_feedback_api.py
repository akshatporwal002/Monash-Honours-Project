from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.api.analytics_dependencies import get_analytics_pseudonymizer
from app.api.audit_dependencies import get_student_audit_tracker
from app.api.feedback_dependencies import (
    get_authenticated_actor,
    get_feedback_access_policy,
    get_feedback_application,
    get_feedback_executor,
)
from app.api.learning_event_dependencies import get_feedback_view_tracker
from app.main import app
from app.models import (
    FeedbackReportCategory,
    JudgeDecision,
    JudgeEvaluationStatus,
    WorkflowStage,
)
from app.schemas.feedback import (
    FeedbackPipelineResult,
    FeedbackPipelineStatus,
    FeedbackSourceAttribution,
    GeneratedFeedback,
    JudgeEvaluationOutcome,
    JudgeResult,
    SafeFallbackFeedback,
    TokenUsage,
)
from app.schemas.feedback_api import AuthenticatedActor
from app.services.feedback.contracts import (
    FeedbackReportWriteResult,
    WorkflowClaim,
)
from app.services.feedback.errors import FeedbackReportConflictError, PipelinePersistenceError
from app.services.learning_events import HmacSha256Pseudonymizer

WORKFLOW_ID = "00000000-0000-4000-8000-000000000101"
FEEDBACK_ID = "00000000-0000-4000-8000-000000000102"
PSEUDONYMIZER = HmacSha256Pseudonymizer("feedback-api-test-secret-at-least-32-bytes")


class AllowPolicy:
    def __init__(self, allowed: bool = True) -> None:
        self.allowed = allowed

    async def can_access_submission(
        self,
        actor: AuthenticatedActor,
        submission_id: str,
    ) -> bool:
        return self.allowed


class RecordingExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str | None, str | None]] = []

    async def execute(
        self,
        workflow_run_id: str,
        submission_id: str,
        execution_token: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        self.calls.append((workflow_run_id, submission_id, execution_token, correlation_id))


class RecordingFeedbackViewTracker:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def record_terminal_view(self, **values: str) -> None:
        self.calls.append(values)


class RecordingStudentAuditTracker:
    def __init__(self) -> None:
        self.view_calls: list[dict[str, str]] = []
        self.report_calls: list[dict[str, str]] = []

    def record_feedback_view(self, **values: str) -> None:
        self.view_calls.append(values)

    def record_feedback_report(self, **values: str) -> None:
        self.report_calls.append(values)


class FakeApplication:
    def __init__(self, claim: WorkflowClaim | None) -> None:
        self.claim = claim
        self.report_result = FeedbackReportWriteResult(
            report_id="00000000-0000-4000-8000-000000000103",
            created=True,
        )
        self.released_submission = "submission-1"
        self.reports: list[object] = []
        self.report_error: Exception | None = None

    def start(
        self,
        submission_id: str,
        *,
        correlation_id: str | None = None,
    ) -> WorkflowClaim:
        del submission_id, correlation_id
        assert self.claim is not None
        return self.claim

    def get(self, submission_id: str) -> WorkflowClaim | None:
        return self.claim

    def released_submission_id(self, feedback_id: str) -> str | None:
        return self.released_submission

    def report(self, report: object) -> FeedbackReportWriteResult:
        self.reports.append(report)
        if self.report_error is not None:
            raise self.report_error
        return self.report_result


def processing_claim(*, should_start: bool = True) -> WorkflowClaim:
    return WorkflowClaim(
        workflow_run_id=WORKFLOW_ID,
        submission_id="submission-1",
        stage=WorkflowStage.GENERATING,
        should_start=should_start,
    )


def validated_claim() -> WorkflowClaim:
    generated = GeneratedFeedback(
        feedback_content={
            "response_classification": "partially_correct",
            "summary": "The answer identifies superposition.",
            "identified_error": None,
            "explanation": "Measurement still needs to be explained.",
            "improvement_actions": ["Explain measurement."],
            "recommended_next_step": "Review measurement.",
            "ai_generated_notice": "untrusted model-authored notice",
        },
        provider="private-provider",
        model="private-model",
        prompt_version="feedback-v2",
        source_references=["source-1"],
        source_attributions=[FeedbackSourceAttribution(source_id="source-1", label="Course notes")],
        simulation_references=["simulation-1"],
        token_usage=TokenUsage(input_tokens=10, output_tokens=5, total_tokens=15),
        estimated_cost=Decimal("0.5"),
    )
    judge_result = JudgeResult(
        decision=JudgeDecision.PASS,
        correctness_score=90,
        relevance_score=90,
        grounding_score=90,
        actionability_score=90,
        safety_score=100,
        reason="Policy approved.",
    )
    judge_evaluation = JudgeEvaluationOutcome(
        evaluation_status=JudgeEvaluationStatus.VALID,
        reported_decision=JudgeDecision.PASS,
        judge_result=judge_result,
        reason="Policy approved.",
        provider="private-provider",
        model="private-judge-model",
        prompt_version="quality-judge-v1",
    )
    result = FeedbackPipelineResult(
        workflow_run_id=WORKFLOW_ID,
        feedback_id=FEEDBACK_ID,
        submission_id="submission-1",
        status=FeedbackPipelineStatus.VALIDATED,
        validated_feedback=generated,
        judge_result=judge_result,
        judge_evaluations=[judge_evaluation],
        regeneration_count=0,
        latency_ms=10,
        token_usage=generated.token_usage,
        estimated_cost=generated.estimated_cost,
        source_references=["source-1"],
    )
    return WorkflowClaim(
        workflow_run_id=WORKFLOW_ID,
        submission_id="submission-1",
        stage=WorkflowStage.COMPLETED,
        should_start=False,
        course_id="course-1",
        task_id="task-1",
        terminal_result=result,
    )


def fallback_claim() -> WorkflowClaim:
    fallback = SafeFallbackFeedback(
        feedback_content={
            "summary": "Personalized feedback is temporarily unavailable.",
            "explanation": "No feedback passed validation.",
            "recommended_next_step": "Review course material or ask an educator.",
        }
    )
    result = FeedbackPipelineResult(
        workflow_run_id=WORKFLOW_ID,
        feedback_id=FEEDBACK_ID,
        submission_id="submission-1",
        status=FeedbackPipelineStatus.FALLBACK,
        validated_feedback=None,
        safe_fallback=fallback,
        fallback_used=True,
        latency_ms=10,
        token_usage=TokenUsage(),
        estimated_cost=Decimal("0"),
    )
    return WorkflowClaim(
        workflow_run_id=WORKFLOW_ID,
        submission_id="submission-1",
        stage=WorkflowStage.COMPLETED,
        should_start=False,
        terminal_result=result,
    )


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> None:
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def configure(
    application: FakeApplication,
    *,
    allowed: bool = True,
    actor: AuthenticatedActor | None = AuthenticatedActor(
        actor_reference="student-1",
        role="student",
    ),
) -> RecordingExecutor:
    executor = RecordingExecutor()
    app.dependency_overrides[get_authenticated_actor] = lambda: actor
    app.dependency_overrides[get_feedback_access_policy] = lambda: AllowPolicy(allowed)
    app.dependency_overrides[get_feedback_application] = lambda: application
    app.dependency_overrides[get_feedback_executor] = lambda: executor
    app.dependency_overrides[get_analytics_pseudonymizer] = lambda: PSEUDONYMIZER
    return executor


def test_start_feedback_returns_processing_and_schedules_only_winning_claim() -> None:
    application = FakeApplication(processing_claim())
    executor = configure(application)

    response = TestClient(app).post("/api/v1/submissions/submission-1/feedback")

    assert response.status_code == 202
    assert response.headers["location"] == "/api/v1/submissions/submission-1/feedback"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["retry-after"] == "2"
    UUID(response.headers["x-correlation-id"])
    assert response.json() == {
        "workflow_run_id": WORKFLOW_ID,
        "submission_id": "submission-1",
        "status": "processing",
        "processing_stage": "generating",
        "feedback": None,
        "error": None,
    }
    expected_call = (
        WORKFLOW_ID,
        "submission-1",
        None,
        response.headers["x-correlation-id"],
    )
    assert executor.calls == [expected_call]

    application.claim = processing_claim(should_start=False)
    second = TestClient(app).post("/api/v1/submissions/submission-1/feedback")
    assert second.status_code == 202
    assert executor.calls == [expected_call]


def test_terminal_api_exposes_only_student_safe_validated_fields() -> None:
    configure(FakeApplication(validated_claim()))
    tracker = RecordingFeedbackViewTracker()
    audit_tracker = RecordingStudentAuditTracker()
    app.dependency_overrides[get_feedback_view_tracker] = lambda: tracker
    app.dependency_overrides[get_student_audit_tracker] = lambda: audit_tracker

    response = TestClient(app).get("/api/v1/submissions/submission-1/feedback")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "validated"
    assert body["feedback"]["kind"] == "validated"
    assert body["feedback"]["sources"] == [{"source_id": "source-1", "label": "Course notes"}]
    assert body["feedback"]["ai_generated_notice"].startswith("AI-generated feedback")
    serialized = str(body)
    assert "private-provider" not in serialized
    assert "private-model" not in serialized
    assert "estimated_cost" not in serialized
    assert "judge" not in serialized
    assert "untrusted model-authored notice" not in serialized
    assert tracker.calls == [
        {
            "actor_reference": "student-1",
            "course_id": "course-1",
            "task_id": "task-1",
            "workflow_run_id": WORKFLOW_ID,
            "correlation_id": response.headers["x-correlation-id"],
            "feedback_status": "validated",
        }
    ]
    assert audit_tracker.view_calls == [
        {
            "actor_reference": "student-1",
            "feedback_id": FEEDBACK_ID,
            "correlation_id": response.headers["x-correlation-id"],
        }
    ]


def test_existing_terminal_post_returns_200_without_scheduling() -> None:
    executor = configure(FakeApplication(validated_claim()))

    response = TestClient(app).post("/api/v1/submissions/submission-1/feedback")

    assert response.status_code == 200
    assert response.json()["status"] == "validated"
    assert executor.calls == []


def test_fallback_response_has_no_assessment_or_references() -> None:
    configure(FakeApplication(fallback_claim()))

    response = TestClient(app).get("/api/v1/submissions/submission-1/feedback")

    assert response.status_code == 200
    feedback = response.json()["feedback"]
    assert feedback["kind"] == "safe_fallback"
    assert feedback["sources"] == []
    assert feedback["simulation_references"] == []
    assert "response_classification" not in feedback
    assert "ai_generated_notice" not in feedback


def test_authentication_and_ownership_fail_closed_without_resource_leaks() -> None:
    default_response = TestClient(app).get("/api/v1/submissions/submission-1/feedback")
    assert default_response.status_code == 401
    assert default_response.json()["detail"] == "Authentication required"

    configure(FakeApplication(processing_claim()), actor=None)
    unauthenticated = TestClient(app).get("/api/v1/submissions/submission-1/feedback")
    assert unauthenticated.status_code == 401

    configure(FakeApplication(processing_claim()), allowed=False)
    forbidden = TestClient(app).get("/api/v1/submissions/submission-1/feedback")
    assert forbidden.status_code == 404
    assert forbidden.json()["error"]["code"] == "feedback_not_found"


def test_missing_workflow_is_a_private_not_found_response() -> None:
    configure(FakeApplication(None))

    response = TestClient(app).get("/api/v1/submissions/submission-1/feedback")

    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "feedback_not_found", "message": "Feedback was not found."}
    }


def test_persistence_failures_use_the_sanitized_feature_envelope() -> None:
    class FailingApplication(FakeApplication):
        def start(
            self,
            submission_id: str,
            *,
            correlation_id: str | None = None,
        ) -> WorkflowClaim:
            del correlation_id
            raise PipelinePersistenceError("private-submission-reference")

    configure(FailingApplication(processing_claim()))

    response = TestClient(app).post("/api/v1/submissions/submission-1/feedback")

    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "error": {
            "code": "feedback_service_unavailable",
            "message": "The feedback service is temporarily unavailable.",
        }
    }
    assert "private-submission-reference" not in response.text


def test_feedback_path_identifiers_are_bounded() -> None:
    configure(FakeApplication(processing_claim()))

    response = TestClient(app).get(f"/api/v1/submissions/{'a' * 256}/feedback")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_feedback_request"
    assert response.headers["cache-control"] == "no-store"


def test_feedback_report_is_trimmed_persisted_and_exact_replay_returns_200() -> None:
    application = FakeApplication(validated_claim())
    configure(application)
    audit_tracker = RecordingStudentAuditTracker()
    app.dependency_overrides[get_student_audit_tracker] = lambda: audit_tracker
    client = TestClient(app)

    first = client.post(
        f"/api/v1/feedback/{FEEDBACK_ID}/report",
        json={"category": "citation_issue", "note": "  Wrong source label.  "},
    )
    application.report_result = FeedbackReportWriteResult(
        report_id="00000000-0000-4000-8000-000000000103",
        created=False,
    )
    second = client.post(
        f"/api/v1/feedback/{FEEDBACK_ID}/report",
        json={"category": "citation_issue", "note": "Wrong source label."},
    )

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json() == second.json()
    report = application.reports[0]
    assert report.category is FeedbackReportCategory.CITATION_ISSUE
    assert report.note == "Wrong source label."
    assert report.reporter_reference == PSEUDONYMIZER.pseudonymize(
        "feedback-report-actor",
        "student-1",
    )
    assert "student-1" not in report.reporter_reference
    assert [call["report_id"] for call in audit_tracker.report_calls] == [
        "00000000-0000-4000-8000-000000000103",
        "00000000-0000-4000-8000-000000000103",
    ]


def test_unreleased_feedback_cannot_be_reported() -> None:
    application = FakeApplication(validated_claim())
    application.released_submission = None
    configure(application)

    response = TestClient(app).post(
        f"/api/v1/feedback/{FEEDBACK_ID}/report",
        json={"category": "other"},
    )

    assert response.status_code == 404
    assert application.reports == []


def test_conflicting_report_returns_a_sanitized_conflict() -> None:
    application = FakeApplication(validated_claim())
    application.report_error = FeedbackReportConflictError()
    configure(application)

    response = TestClient(app).post(
        f"/api/v1/feedback/{FEEDBACK_ID}/report",
        json={"category": "unsafe", "note": "private report details"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "feedback_report_conflict"
    assert "private report details" not in response.text


def test_invalid_report_uses_the_feature_error_envelope_without_echoing_note() -> None:
    private_note = "private" * 500
    application = FakeApplication(validated_claim())
    configure(application)

    response = TestClient(app).post(
        f"/api/v1/feedback/{FEEDBACK_ID}/report",
        json={"category": "unknown", "note": private_note},
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "invalid_feedback_request",
            "message": "The feedback request is invalid.",
        }
    }
    assert private_note not in response.text
