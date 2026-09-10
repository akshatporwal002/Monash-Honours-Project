"""Read frozen responses directly, without recovery writes or current-publication changes."""

from datetime import UTC

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.assessment import (
    AssessmentAttempt,
    AssessmentDefinitionVersion,
    BloomTargetVersion,
    OutcomeVersion,
    PassRuleVersion,
    TaskFormVersion,
)
from app.models.assessment_work import AssessmentWorkStart
from app.models.lms import SubmissionAttempt
from app.schemas.assessment import AssessmentVersionReference, EvidenceReference
from app.schemas.episode import EpisodePayloadV1, FrozenResponseRead, ResponseContent
from app.services.episode_contract import (
    FrozenResponseInvalid,
    FrozenResponseMissing,
    FrozenResponseStale,
)
from app.services.episode_evidence import canonical_response_digest
from app.services.misconception_support import response_teaching


class SqlAlchemyFrozenResponseReader:
    def __init__(self, session: Session):
        self.session = session

    def read(self, *, assessment: AssessmentVersionReference) -> FrozenResponseRead:
        with self.session.no_autoflush:
            return self._read(assessment)

    def _read(self, assessment):
        attempt = self.session.get(AssessmentAttempt, assessment.assessment_attempt_id)
        response = self.session.get(SubmissionAttempt, assessment.response_version_id)
        if attempt is None or response is None:
            raise FrozenResponseMissing("Frozen response or assessment does not exist")
        if (
            attempt.response_version_id,
            attempt.student_id,
            attempt.task_id,
            attempt.course_id,
        ) != (response.id, response.student_id, response.task_id, assessment.course_id):
            raise FrozenResponseStale("Frozen response ownership or assessment link differs")
        form = self.session.get(TaskFormVersion, attempt.task_form_version_id)
        definition = self.session.get(
            AssessmentDefinitionVersion, attempt.assessment_definition_version_id
        )
        bloom = self.session.get(BloomTargetVersion, attempt.bloom_target_version_id)
        rule = self.session.get(PassRuleVersion, attempt.pass_rule_version_id)
        outcome = (
            self.session.get(OutcomeVersion, definition.outcome_version_id) if definition else None
        )
        if any(row is None for row in (form, definition, bloom, rule, outcome)):
            raise FrozenResponseMissing("Frozen assessment versions are missing")
        actual = AssessmentVersionReference(
            course_id=attempt.course_id,
            assessment_definition_id=definition.assessment_definition_id,
            assessment_definition_version=definition.version,
            outcome_id=outcome.learning_outcome_id,
            outcome_version=outcome.version,
            bloom_target_id=bloom.bloom_target_id,
            bloom_target_version=bloom.version,
            criterion_set_id=definition.assessment_definition_id,
            criterion_set_version=definition.version,
            pass_rule_id=rule.pass_rule_id,
            pass_rule_version=rule.version,
            task_id=attempt.task_id,
            task_form_version=form.version,
            assessment_attempt_id=attempt.id,
            response_version_id=response.id,
        )
        if (
            actual != assessment
            or response.task_form_version_id != form.id
            or form.learning_task_id != response.task_id
            or any(
                row.course_id != attempt.course_id
                for row in (form, definition, bloom, rule, outcome)
            )
            or any(
                row.assessment_definition_version_id != definition.id for row in (form, bloom, rule)
            )
        ):
            raise FrozenResponseStale("Frozen version links differ from the requested assessment")
        if response.assessment_work_start_id:
            work = self.session.get(AssessmentWorkStart, response.assessment_work_start_id)
            if work is None or (
                work.student_id,
                work.task_id,
                work.task_form_version_id,
                work.assessment_definition_version_id,
                work.bloom_target_version_id,
                work.pass_rule_version_id,
            ) != (response.student_id, response.task_id, form.id, definition.id, bloom.id, rule.id):
                raise FrozenResponseStale("Frozen work links differ")
        try:
            if response.response_schema_version not in {
                "assessment.response.v1",
                "assessment.response.v2",
            }:
                raise FrozenResponseInvalid(
                    "Frozen assessment requires an assessment response schema"
                )
            content = ResponseContent(
                answer=response.answer, code=response.code, circuit=response.circuit
            )
            episode = (
                EpisodePayloadV1.model_validate(response.episode) if response.episode else None
            )
            digest = canonical_response_digest(
                content=content,
                episode=episode,
                schema_version=response.response_schema_version,
                assessment_work_start_id=response.assessment_work_start_id,
                task_form_version_id=response.task_form_version_id,
                declared_conditions=response.declared_conditions,
            )
            if digest != response.content_digest:
                raise FrozenResponseInvalid("Frozen response digest does not match its content")
            if episode is not None:
                from app.services.episodes import EpisodeService
                from app.services.task_review import TaskReviewError

                try:
                    EpisodeService(self.session).validate_response(
                        work if response.assessment_work_start_id else None,
                        episode,
                        content,
                        student_id=response.student_id,
                        task_id=response.task_id,
                    )
                except TaskReviewError as error:
                    raise FrozenResponseInvalid(str(error)) from error
            return FrozenResponseRead(
                reference=EvidenceReference(
                    assessment=actual,
                    evidence_id=response.id,
                    evidence_type="learner_response",
                    schema_version=response.response_schema_version,
                    record_version=1,
                    content_digest=digest,
                    source_record_id=response.id,
                    source_record_version=1,
                    occurred_at=response.submitted_at.replace(tzinfo=UTC)
                    if response.submitted_at.tzinfo is None
                    else response.submitted_at,
                ),
                assessment_work_start_id=response.assessment_work_start_id,
                task_form_version_id=form.id,
                content=content,
                episode=episode,
                recorded_teaching=response_teaching(self.session, response),
                declared_conditions=response.declared_conditions
                if response.declared_conditions is not None
                else {},
            )
        except (ValidationError, TypeError, ValueError) as error:
            raise FrozenResponseInvalid(str(error)) from error
