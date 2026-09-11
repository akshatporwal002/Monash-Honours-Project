"""Import actual AI outputs for released, scoped human review; never write a result."""

import json
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import inspect, select

from app.models.learning_evidence import EvidenceArtifact
from app.models.lms import PlatformAuditEvent
from app.schemas.category_review import CategoryReviewRecord, CategoryReviewRequest, ReviewEvidence
from app.schemas.evaluator_governance import SuggestionImportWrite
from app.services.assessment.evaluation import AssessmentEvaluationConflictError
from app.services.assessment.evaluator_release import (
    EvaluatorReleaseService,
    digest,
    semantic_record,
)
from app.services.assessment.evidence import FrozenEvidenceValidator
from app.services.assessment.moderation import ModerationService, utc
from app.services.assessment.review import (
    AssessmentReviewConflictError,
    AssessmentReviewValidationError,
)
from app.services.category_review import require_approved, review_output, review_prompt
from app.services.episode_contract import FrozenResponseError
from app.services.evidence.assessment_port import AssessmentEvidencePort

SCHEMA = "released-assessor-suggestions.v1"


class AssessorSuggestionService:
    def __init__(self, session, human):
        self.session, self.human = session, human

    def _context(self, actor, attempt_id):
        attempt = self.human._visible(actor, attempt_id)
        release = EvaluatorReleaseService(self.session).require_release(
            attempt.course_id, task_form_version_id=attempt.task_form_version_id
        )
        self.human.assignments.require_assessor_access(actor, attempt.course_id)
        try:
            bundle = self.human._bundle(attempt)
            response = self.human.reader.read(assessment=bundle.reference)
        except (FrozenResponseError, AssessmentEvaluationConflictError, ValueError) as error:
            raise AssessmentReviewConflictError("The frozen response is unavailable") from error
        return attempt, release, bundle, response

    def _prepare(self, actor, attempt_id, command):
        attempt, release, bundle, response = self._context(actor, attempt_id)
        if ModerationService(self.session).withhold_judgements(actor, attempt_id):
            raise AssessmentReviewConflictError(
                "Complete independent moderation before reviewing AI output"
            )
        if (command.release_id, command.expected_fingerprint) != (release.id, release.fingerprint):
            raise AssessmentReviewConflictError(
                "The supplied output does not match the current release"
            )
        if command.response_digest != response.reference.content_digest:
            raise AssessmentReviewConflictError(
                "Output is bound to a different frozen learner response"
            )
        approval = release.evidence["approval"]
        if any(
            getattr(command, name) != approval[name]
            for name in (
                "provider",
                "model",
                "prompt_version",
                "retrieval_version",
            )
        ):
            raise AssessmentReviewValidationError(
                "Output versions differ from the approved release"
            )
        if (
            not max(
                utc(response.reference.occurred_at), datetime.fromisoformat(approval["approved_at"])
            )
            <= command.generated_at
            <= datetime.now(UTC)
        ):
            raise AssessmentReviewValidationError(
                "Output time must follow the response and release approval"
            )
        criteria = {criterion.id: criterion for criterion in bundle.criteria}
        if {item.criterion_version_id for item in command.criteria} != set(criteria) or len(
            command.criteria
        ) != len(criteria):
            raise AssessmentReviewValidationError(
                "Supply exactly one suggestion for each frozen criterion"
            )
        references = {}
        for item in command.criteria:
            references[item.criterion_version_id] = [
                reference.model_dump(mode="json")
                for reference in FrozenEvidenceValidator().resolve_and_validate(
                    AssessmentEvidencePort(self.human.resolver),
                    assessment=bundle.reference,
                    evidence_ids=item.evidence_ids,
                    allowed_types=criteria[item.criterion_version_id].evidence_source_types,
                )
            ]
        return attempt, release, bundle, response, references

    @staticmethod
    def _quality_request(command, attempt, release, bundle, response, references):
        evidence = [
            ReviewEvidence(
                reference=response.reference.evidence_id,
                version=response.reference.content_digest,
                kind="observation",
                content=response.model_dump(mode="json"),
            )
        ]
        for standard in (
            bundle.form,
            bundle.definition,
            bundle.bloom,
            bundle.rule,
            *bundle.criteria,
        ):
            values = semantic_record(
                {
                    column.key: getattr(standard, column.key)
                    for column in inspect(standard).mapper.column_attrs
                }
            )
            evidence.append(
                ReviewEvidence(
                    reference=standard.id,
                    version=str(standard.version),
                    kind="approved_content",
                    approval_reference=f"{standard.id}:approved-by:{standard.approved_by_user_id}",
                    content=json.loads(json.dumps(values, default=str)),
                )
            )
        evidence.append(
            ReviewEvidence(
                reference="resolved-criterion-evidence",
                version=release.fingerprint,
                kind="observation",
                content=references,
            )
        )
        return CategoryReviewRequest(
            category="provisional_assessment",
            course_id=attempt.course_id,
            subject_id=attempt.id,
            output=command.model_dump(mode="json", exclude={"quality_review"}),
            evidence=tuple(evidence),
            versions={
                "release": release.id,
                "fingerprint": release.fingerprint,
                "response": response.reference.content_digest,
                **{
                    key: getattr(command, key)
                    for key in ("provider", "model", "prompt_version", "retrieval_version")
                },
            },
        )

    def quality_context(self, actor, attempt_id, command):
        context = self._prepare(actor, attempt_id, command)
        return {
            **review_prompt(self._quality_request(command, *context)),
            "reviewer": {
                "kind": "human",
                "reference": f"user:{actor.id}",
                "version": "fr17-complete-review.v1",
            },
        }

    def record(self, actor, attempt_id, command):
        attempt, release, bundle, response, references = self._prepare(actor, attempt_id, command)
        identity = str(uuid5(NAMESPACE_URL, f"{SCHEMA}:{attempt.id}:{command.idempotency_key}"))
        request_digest = digest(command.model_dump(mode="json"))
        existing = self.session.get(EvidenceArtifact, identity)
        if existing:
            prior = json.loads(existing.content)
            if prior["request_digest"] != request_digest or prior["recorded_by"] != actor.id:
                raise AssessmentReviewConflictError(
                    "This suggestion key already has different content"
                )
            return {
                "suggestion_id": existing.id,
                "replayed": True,
                "quality_decision": prior["quality"]["decision"],
            }
        quality_request = self._quality_request(
            command, attempt, release, bundle, response, references
        )

        def authenticated_review(_):
            assessment = command.quality_review
            if assessment is None or assessment.reviewer.model_dump(exclude_none=True) != {
                "kind": "human",
                "reference": f"user:{actor.id}",
                "version": "fr17-complete-review.v1",
            }:
                raise ValueError("A complete review by the authenticated assessor is required")
            return assessment

        quality = review_output(quality_request, authenticated_review)
        data = {
            "output": command.model_dump(mode="json", exclude={"quality_review"}),
            "quality": quality.model_dump(mode="json"),
            "request_digest": request_digest,
            "recorded_by": actor.id,
            "versions": bundle.reference.model_dump(mode="json"),
            "evidence": references,
            "advisory": True,
        }
        content = json.dumps(data, sort_keys=True, separators=(",", ":"))
        self.session.add(
            EvidenceArtifact(
                id=identity,
                course_id=attempt.course_id,
                learner_id=attempt.student_id,
                content=content,
                content_digest="sha256:" + digest(data),
                content_format="application.json",
                schema_version=SCHEMA,
                record_version=1,
                actor_reference=str(actor.id),
                agent_reference=SCHEMA,
                correlation_id=attempt.id,
                occurred_at=command.generated_at,
            )
        )
        self.session.add(
            PlatformAuditEvent(
                actor_id=actor.id,
                action="assessment_suggestion.imported",
                resource_type="evidence_artifact",
                resource_id=identity,
                correlation_id=self.human.correlation_id,
                details={
                    "assessment_attempt_id": attempt.id,
                    "release_id": release.id,
                    "output_reference": command.output_reference,
                    "request_digest": request_digest,
                    "quality_decision": quality.decision.value,
                    "quality_request_digest": quality.request_digest,
                },
            )
        )
        self.session.flush()
        return {
            "suggestion_id": identity,
            "replayed": False,
            "quality_decision": quality.decision.value,
        }

    def read(self, actor, attempt_id):
        attempt = self.human._visible(actor, attempt_id)
        if ModerationService(self.session).withhold_judgements(actor, attempt_id):
            return {
                "status": "WITHHELD",
                "reason": "Independent second review must be completed first",
                "records": [],
            }
        try:
            _, release, bundle, response = self._context(actor, attempt_id)
        except AssessmentReviewConflictError as error:
            return {"status": "PENDING", "reason": str(error), "records": []}
        records = []
        for artifact in self.session.scalars(
            select(EvidenceArtifact)
            .where(
                EvidenceArtifact.course_id == attempt.course_id,
                EvidenceArtifact.learner_id == attempt.student_id,
                EvidenceArtifact.correlation_id == attempt.id,
                EvidenceArtifact.schema_version == SCHEMA,
            )
            .order_by(EvidenceArtifact.created_at, EvidenceArtifact.id)
        ):
            data = json.loads(artifact.content)
            if (
                data["output"]["release_id"] == release.id
                and data["output"]["response_digest"] == response.reference.content_digest
                and data["versions"] == bundle.reference.model_dump(mode="json")
            ):
                try:
                    quality = CategoryReviewRecord.model_validate(data.get("quality"))
                    command = SuggestionImportWrite.model_validate(data["output"])
                    require_approved(
                        quality,
                        self._quality_request(
                            command, attempt, release, bundle, response, data["evidence"]
                        ),
                    )
                    if quality.assessment.reviewer.reference != f"user:{data['recorded_by']}":
                        continue
                except ValueError:
                    continue
                records.append({"id": artifact.id, **data})
        return {
            "status": "RELEASED",
            "release_expires_at": utc(release.expires_at).isoformat(),
            "reason": "Advisory outputs only; record your own criterion decisions",
            "records": records,
        }
