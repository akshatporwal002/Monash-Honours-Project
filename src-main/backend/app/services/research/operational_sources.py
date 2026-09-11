"""Read-only NFR25 adapters with exact operational lineage and bounded projections."""

import json
import re
from dataclasses import dataclass
from functools import cached_property
from types import SimpleNamespace

from sqlalchemy import MetaData, Table, inspect, select

from app.models.activity_continuation import ActivityChoice, ActivityProgress, ActivitySuggestion
from app.models.assessment import AssessmentAttempt, AssessmentDecision, AssessorReview
from app.models.human_assessment import HumanAssessmentAction
from app.models.learner_model import LearnerModelSnapshot
from app.models.learning_evidence import LearningEvidence
from app.models.lms import SubmissionAttempt
from app.models.persistence import FeedbackRecord, JudgeEvaluation, WorkflowRun
from app.models.simulation import CircuitVersion, SimulationOutcome, SimulationRun
from app.schemas.research_instruments import LearningStageLinks
from app.services.research.governance import GovernanceDenied, utc
from app.services.research.instruments import digest

VERSION = "learnlens.operational-sources.v1"
RAW_FIELDS = {
    "operational.response_text",
    "operational.code",
    "operational.ai_output",
    "operational.episode",
    "operational.adaptation_reasons",
    "operational.override_reasons",
}


@dataclass(frozen=True)
class SourceValue:
    value: object
    references: list[str]
    missing: str | None = None
    version: str = VERSION

    @property
    def content_digest(self):
        return digest([self.value, self.references, self.missing, self.version])


def code(value):
    """Metadata tokens cannot contain URL queries, credentials, paths or free prose."""
    value = getattr(value, "value", value)
    if value is None:
        return None
    value = str(value)
    return (
        value
        if re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.:/-]{0,127}", value)
        and not any(
            s in value.lower()
            for s in ("://", ":/", "secret", "token=", "password", "bearer", "sk-", "ghp_", "akia")
        )
        else None
    )


class OperationalSources:
    def __init__(self, service, study, course, allocation, record):
        self.service, self.session = service, service.session
        self.study, self.course, self.allocation, self.record = study, course, allocation, record
        self.subject = allocation.subject_user_id
        _, self.consent = service.policy.participant(
            study,
            course,
            self.subject,
            fields=(),
            purposes={"study_instruments", "study_operational_evidence"},
        )
        service.instruments._validate_links(
            SimpleNamespace(
                links=LearningStageLinks.model_validate(record.links),
                subject_user_id=self.subject,
                stage=record.stage,
                kind=record.kind,
            ),
            course,
            self.consent.recorded_at,
        )

    def ref(self, kind, identity):
        return self.service.instruments._pseudonym(self.study, "operational:" + kind, identity)

    def rows(self, statement):
        rows = self.session.scalars(
            statement.limit(501).execution_options(populate_existing=True)
        ).all()
        if len(rows) > 500:
            raise GovernanceDenied("operational_record_limit")
        for row in rows:
            timestamp = getattr(row, "occurred_at", getattr(row, "created_at", None))
            if timestamp is not None and utc(timestamp) < utc(self.consent.recorded_at):
                raise GovernanceDenied("historical_use_not_approved")
        return rows

    @cached_property
    def response(self):
        identity = self.record.links.get("response_id")
        return (
            self.session.get(SubmissionAttempt, identity, populate_existing=True)
            if identity
            else None
        )

    @cached_property
    def workflow(self):
        if self.response is None:
            return None
        row = self.session.scalar(
            select(WorkflowRun)
            .where(WorkflowRun.submission_id == self.response.id)
            .execution_options(populate_existing=True)
        )
        if row is not None and (row.course_id, row.task_id) != (self.course, self.response.task_id):
            raise GovernanceDenied("operational_workflow_lineage_denied")
        return row

    @cached_property
    def feedback(self):
        if self.workflow is None:
            return []
        return self.rows(
            select(FeedbackRecord)
            .where(
                FeedbackRecord.workflow_run_id == self.workflow.id,
                FeedbackRecord.submission_id == self.response.id,
            )
            .order_by(FeedbackRecord.created_at, FeedbackRecord.id)
        )

    @cached_property
    def judges(self):
        return (
            self.rows(
                select(JudgeEvaluation)
                .where(JudgeEvaluation.feedback_id.in_([r.id for r in self.feedback]))
                .order_by(JudgeEvaluation.created_at, JudgeEvaluation.id)
            )
            if self.feedback
            else []
        )

    @cached_property
    def evidence(self):
        if self.response is None:
            return []
        return self.rows(
            select(LearningEvidence)
            .where(
                LearningEvidence.response_version_id == self.response.id,
                LearningEvidence.learner_id == self.subject,
                LearningEvidence.course_id == self.course,
                LearningEvidence.task_id == self.response.task_id,
            )
            .order_by(LearningEvidence.occurred_at, LearningEvidence.id)
        )

    @cached_property
    def attempts(self):
        return (
            self.rows(
                select(AssessmentAttempt).where(
                    AssessmentAttempt.response_version_id == self.response.id,
                    AssessmentAttempt.student_id == self.subject,
                    AssessmentAttempt.course_id == self.course,
                )
            )
            if self.response
            else []
        )

    @cached_property
    def provider_usage(self):
        """Optional v1 transport ledger; never match on course alone or sum currencies."""
        if self.response is None:
            return [], "not_recorded"
        inspector = inspect(self.session.get_bind())
        if not inspector.has_table("provider_usage"):
            return [], "adapter_unavailable"
        table = Table("provider_usage", MetaData(), autoload_with=self.session.get_bind())
        required = {
            "id",
            "state",
            "provenance",
            "input_tokens",
            "output_tokens",
            "estimated_micros",
            "actual_micros",
            "reserved_micros",
            "exposure_micros",
            "created_at",
        }
        if not required <= set(table.c.keys()):
            return [], "adapter_unavailable"
        context = table.c.provenance["context"]
        rows = (
            self.session.execute(
                select(table)
                .where(
                    context["submission_id"].as_string() == self.response.id,
                    context["course_id"].as_string() == self.course,
                    context["task_id"].as_string() == self.response.task_id,
                )
                .order_by(table.c.id)
                .limit(501)
            )
            .mappings()
            .all()
        )
        if len(rows) > 500:
            raise GovernanceDenied("operational_record_limit")
        for row in rows:
            if utc(row["created_at"]) < utc(self.consent.recorded_at):
                raise GovernanceDenied("historical_use_not_approved")
        return rows, None if rows else "not_recorded"

    def missing(self, reason="not_recorded", version=VERSION):
        return SourceValue(None, [], reason, version)

    def value(self, field):
        name = field.removeprefix("operational.")
        if name == "episode":
            value = self.response.episode if self.response else None
            return (
                SourceValue(
                    json.dumps(value, ensure_ascii=False, indent=2),
                    ["response:" + self.response.id],
                )
                if value is not None
                else self.missing()
            )
        if name in {"response_text", "code"}:
            value = getattr(self.response, "answer" if name == "response_text" else "code", None)
            return (
                SourceValue(value, ["response:" + self.response.id])
                if value is not None and self.response
                else self.missing()
            )
        if name == "evidence":
            return (
                SourceValue(
                    [
                        {
                            "reference": self.ref("evidence", e.id),
                            "type": code(e.evidence_type),
                            "provenance": code(e.provenance),
                            "observation_type": code(e.observation_type),
                            "instructional_support_level": e.instructional_support_level,
                            "source_version": code(e.source_version),
                            "schema_version": code(e.schema_version),
                            "occurred_at": utc(e.occurred_at).isoformat(),
                        }
                        for e in self.evidence
                    ],
                    ["evidence:" + e.id for e in self.evidence],
                )
                if self.evidence
                else self.missing()
            )
        if name == "ai_output":
            released = [f for f in self.feedback if code(f.status) in {"accepted", "safe_fallback"}]
            return (
                SourceValue(
                    json.dumps(
                        [f.feedback_content for f in released], ensure_ascii=False, indent=2
                    ),
                    ["feedback:" + f.id for f in released],
                )
                if released
                else self.missing()
            )
        if name == "model_references":
            values = [
                {
                    "reference": self.ref("feedback", f.id),
                    "role": "feedback",
                    "provider": code(f.provider),
                    "model": code(f.model),
                    "prompt_version": code(f.prompt_version),
                }
                for f in self.feedback
            ]
            values += [
                {
                    "reference": self.ref("judge", j.id),
                    "role": "quality_judge",
                    "provider": code(j.provider),
                    "model": code(j.model),
                    "prompt_version": code(j.prompt_version),
                    "policy_version": code(j.quality_policy_version),
                }
                for j in self.judges
            ]
            usage, _ = self.provider_usage
            values += [
                {
                    "reference": self.ref("provider_attempt", r["id"]),
                    "role": "provider_transport",
                    "state": code(r["state"]),
                    "provider": code(r["provenance"].get("provider")),
                    "model": code(r["provenance"].get("model")),
                    "prompt_version": code(r["provenance"].get("prompt_version")),
                    "pricing_version": code(r["provenance"].get("pricing_version")),
                    "budget_policy_version": code(r["provenance"].get("budget_policy_version")),
                    "adapter_version": "learnlens.provider-usage.v1",
                }
                for r in usage
            ]
            progress = (
                self.session.get(ActivityProgress, self.workflow.id) if self.workflow else None
            )
            if progress and (progress.learner_id, progress.course_id) != (
                self.subject,
                self.course,
            ):
                raise GovernanceDenied("operational_progress_lineage_denied")
            snapshot = (
                self.session.get(LearnerModelSnapshot, progress.snapshot_id)
                if progress and progress.snapshot_id
                else None
            )
            if snapshot:
                if (snapshot.learner_id, snapshot.course_id, snapshot.outcome_id) != (
                    self.subject,
                    self.course,
                    progress.outcome_id,
                ):
                    raise GovernanceDenied("operational_model_lineage_denied")
                values.append(
                    {
                        "reference": self.ref("learner_model", snapshot.id),
                        "role": "learner_model",
                        "model_version": code(snapshot.model_version),
                        "rule_version": code(snapshot.rule_version),
                        "schema_version": code(snapshot.schema_version),
                    }
                )
            return (
                SourceValue(values, [v["reference"] for v in values]) if values else self.missing()
            )
        if name == "source_references":
            values = [
                {
                    "feedback_reference": self.ref("feedback", f.id),
                    "sources": [self.ref("source", source) for source in f.source_references],
                }
                for f in self.feedback
            ]
            return (
                SourceValue(values, ["feedback:" + f.id for f in self.feedback])
                if values
                else self.missing()
            )
        if name == "judge_result":
            values = [
                {
                    "reference": self.ref("judge", j.id),
                    "status": code(j.evaluation_status),
                    "decision": code(j.decision),
                    "quality_policy_version": code(j.quality_policy_version),
                    "technical_quality": {
                        key: getattr(j, key)
                        for key in (
                            "correctness_score",
                            "relevance_score",
                            "grounding_score",
                            "actionability_score",
                            "safety_score",
                        )
                    },
                }
                for j in self.judges
            ]
            return (
                SourceValue(values, ["judge:" + j.id for j in self.judges])
                if values
                else self.missing()
            )
        if name == "latency_ms":
            return (
                SourceValue(
                    self.workflow.latency_ms,
                    ["workflow:" + self.workflow.id],
                    None if self.workflow.latency_ms is not None else "not_recorded",
                )
                if self.workflow
                else self.missing()
            )
        if name in {
            "input_tokens",
            "output_tokens",
            "estimated_cost",
            "actual_cost",
            "reserved_cost",
            "exposure_cost",
        }:
            rows, absent = self.provider_usage
            if rows:
                column = {
                    "estimated_cost": "estimated_micros",
                    "actual_cost": "actual_micros",
                    "reserved_cost": "reserved_micros",
                    "exposure_cost": "exposure_micros",
                }.get(name, name)
                values = [
                    {
                        "reference": self.ref("provider_attempt", r["id"]),
                        "value": r.get(column),
                        "missing_reason": "not_recorded" if r.get(column) is None else None,
                        **(
                            {
                                "currency": code(r["provenance"].get("currency")),
                                "unit": "millionth_of_currency",
                            }
                            if "cost" in name
                            else {}
                        ),
                    }
                    for r in rows
                ]
                return SourceValue(
                    values,
                    ["provider_attempt:" + r["id"] for r in rows],
                    version="learnlens.provider-usage.v1",
                )
            if name in {"actual_cost", "reserved_cost", "exposure_cost"}:
                return self.missing(absent, "learnlens.provider-usage.v1")
            values = [
                {
                    "reference": self.ref("feedback", f.id),
                    "value": str(f.estimated_cost)
                    if name == "estimated_cost" and f.usage_complete
                    else getattr(f, name)
                    if name != "estimated_cost" and f.usage_complete
                    else None,
                    "missing_reason": None if f.usage_complete else "usage_incomplete",
                    **(
                        {"currency": None, "unit": "legacy_estimate_currency_unrecorded"}
                        if name == "estimated_cost"
                        else {}
                    ),
                }
                for f in self.feedback
            ]
            values += [
                {
                    "reference": self.ref("judge", j.id),
                    "value": str(j.estimated_cost)
                    if name == "estimated_cost" and j.usage_complete
                    else getattr(j, name)
                    if name != "estimated_cost" and j.usage_complete
                    else None,
                    "missing_reason": None if j.usage_complete else "usage_incomplete",
                    **(
                        {"currency": None, "unit": "legacy_estimate_currency_unrecorded"}
                        if name == "estimated_cost"
                        else {}
                    ),
                }
                for j in self.judges
            ]
            return (
                SourceValue(
                    values,
                    [v["reference"] for v in values],
                    version="learnlens.legacy-feedback-usage.v1",
                )
                if values
                else self.missing()
            )
        if name in {"adaptations", "adaptation_reasons"}:
            progress = (
                self.session.get(ActivityProgress, self.workflow.id) if self.workflow else None
            )
            if progress is None:
                return self.missing()
            if (progress.learner_id, progress.course_id) != (self.subject, self.course):
                raise GovernanceDenied("operational_progress_lineage_denied")
            suggestion = self.session.get(ActivitySuggestion, progress.workflow_id)
            if suggestion is None:
                return self.missing()
            if name == "adaptation_reasons":
                return SourceValue(
                    str(suggestion.decision.get("reason", "")),
                    ["suggestion:" + suggestion.workflow_id],
                )
            values = [
                {
                    "reference": self.ref("suggestion", suggestion.workflow_id),
                    "selected_task": self.ref("task", suggestion.task_id)
                    if suggestion.task_id
                    else None,
                    "decision": {
                        k: code(suggestion.decision.get(k))
                        for k in ("state", "reason_code", "decision", "rule_version")
                    },
                }
            ]
            choices = self.rows(
                select(ActivityChoice)
                .where(ActivityChoice.workflow_id == self.workflow.id)
                .order_by(ActivityChoice.version)
            )
            values += [
                {
                    "reference": self.ref("choice", c.id),
                    "version": c.version,
                    "choice": {
                        k: code(c.payload.get(k)) for k in ("action", "choice", "reason_code")
                    },
                    "selected_task": self.ref("task", c.payload["selected_task_id"])
                    if c.payload.get("selected_task_id")
                    else None,
                }
                for c in choices
            ]
            return SourceValue(
                values,
                ["suggestion:" + suggestion.workflow_id, *["choice:" + c.id for c in choices]],
            )
        if name in {"outcome", "overrides", "override_reasons"}:
            decisions = (
                self.rows(
                    select(AssessmentDecision)
                    .where(
                        AssessmentDecision.assessment_attempt_id.in_([a.id for a in self.attempts])
                    )
                    .order_by(AssessmentDecision.created_at)
                )
                if self.attempts
                else []
            )
            if name == "outcome":
                values = [
                    {
                        "reference": self.ref("assessment_decision", d.id),
                        "result": code(d.result),
                        "result_state": code(d.result_state),
                        "bloom_version": self.ref("bloom", d.bloom_target_version_id),
                        "pass_rule_version": self.ref("pass_rule", d.pass_rule_version_id),
                    }
                    for d in decisions
                ]
            else:
                reviews = (
                    self.rows(
                        select(AssessorReview)
                        .where(AssessorReview.assessment_decision_id.in_([d.id for d in decisions]))
                        .order_by(AssessorReview.reviewed_at)
                    )
                    if decisions
                    else []
                )
                actions = (
                    self.rows(
                        select(HumanAssessmentAction)
                        .where(
                            HumanAssessmentAction.assessment_attempt_id.in_(
                                [a.id for a in self.attempts]
                            )
                        )
                        .order_by(HumanAssessmentAction.created_at)
                    )
                    if self.attempts
                    else []
                )
                if name == "override_reasons":
                    reasons = [
                        {"reference": self.ref("assessor_review", r.id), "reason": r.reason}
                        for r in reviews
                    ]
                    reasons += [
                        {"reference": self.ref("human_action", r.id), "reason": r.reason}
                        for r in actions
                    ]
                    return (
                        SourceValue(
                            json.dumps(reasons, ensure_ascii=False, indent=2),
                            [v["reference"] for v in reasons],
                        )
                        if reasons
                        else self.missing()
                    )
                values = [
                    {
                        "reference": self.ref("assessor_review", r.id),
                        "action": code(r.action),
                        "prior_result": code(r.prior_result),
                        "new_result": code(r.new_result),
                        "revision": r.review_revision,
                    }
                    for r in reviews
                ]
                values += [
                    {
                        "reference": self.ref("human_action", r.id),
                        "result": code(r.result),
                        "state": code(r.result_state),
                        "revision": r.revision,
                    }
                    for r in actions
                ]
            return (
                SourceValue(values, [v["reference"] for v in values]) if values else self.missing()
            )
        if name == "simulation":
            runs = (
                self.rows(
                    select(SimulationRun)
                    .where(
                        SimulationRun.submission_id == self.response.id,
                        SimulationRun.owner_id == self.subject,
                    )
                    .order_by(SimulationRun.created_at)
                )
                if self.response
                else []
            )
            values = []
            for run in runs:
                circuit = self.session.get(CircuitVersion, run.circuit_version_id)
                if circuit is None or (circuit.owner_id, circuit.course_id, circuit.task_id) != (
                    self.subject,
                    self.course,
                    self.response.task_id,
                ):
                    raise GovernanceDenied("operational_simulation_lineage_denied")
                outcome = self.session.get(SimulationOutcome, run.id)
                # Only the typed numerical evidence enters this projection, never arbitrary result prose.
                result = outcome.result if outcome and isinstance(outcome.result, dict) else {}
                counts = result.get("counts", {})
                safe_counts = (
                    {
                        k: v
                        for k, v in counts.items()
                        if re.fullmatch(r"[01 ]{1,64}", k) and type(v) is int and v >= 0
                    }
                    if isinstance(counts, dict)
                    else {}
                )
                values.append(
                    {
                        "reference": self.ref("simulation", run.id),
                        "circuit_version": self.ref("circuit", circuit.id),
                        "shots": run.shots,
                        "policy_version": code(run.policy_version),
                        "engine_versions": {
                            code(k): code(v) for k, v in run.engine_versions.items() if code(k)
                        },
                        "status": code(outcome.status) if outcome else None,
                        "counts": safe_counts or None,
                        "missing_reason": None if outcome else "not_recorded",
                    }
                )
            return (
                SourceValue(values, ["simulation:" + r.id for r in runs])
                if values
                else self.missing()
            )
        if name == "moderation":
            inspector = inspect(self.session.get_bind())
            if not inspector.has_table("assessment_moderation_reviews") or not inspector.has_table(
                "assessment_moderation_selections"
            ):
                return self.missing("adapter_unavailable", "learnlens.assessment-moderation.v1")
            table = Table(
                "assessment_moderation_reviews", MetaData(), autoload_with=self.session.get_bind()
            )
            required = {"id", "attempt_id", "stage", "result", "created_at"}
            if not required <= set(table.c.keys()):
                return self.missing("adapter_unavailable", "learnlens.assessment-moderation.v1")
            rows = (
                self.session.execute(
                    select(table)
                    .where(table.c.attempt_id.in_([a.id for a in self.attempts]))
                    .order_by(table.c.id)
                    .limit(501)
                )
                .mappings()
                .all()
            )
            if len(rows) > 500:
                raise GovernanceDenied("operational_record_limit")
            values = [
                {
                    "reference": self.ref("moderation", r["id"]),
                    "attempt_reference": self.ref("attempt", r["attempt_id"]),
                    "stage": code(r["stage"]),
                    "cycle": r.get("cycle"),
                    "result": code(r["result"]),
                }
                for r in rows
            ]
            return SourceValue(
                values,
                ["moderation:" + r["id"] for r in rows],
                None if rows else "not_recorded",
                "learnlens.assessment-moderation.v1",
            )
        raise GovernanceDenied("operational_field_denied")
