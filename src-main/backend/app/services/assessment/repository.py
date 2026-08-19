"""Course-scoped persistence helpers for assessment definition versions."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assessment import AssessmentDefinition, AssessmentDefinitionVersion
from app.models.lms import CourseModule, LearningOutcome


class AssessmentDefinitionNotFoundError(LookupError):
    """The definition is missing or does not belong to the requested course."""


class AssessmentDefinitionRepository:
    """Read and write assessment definitions without crossing a course boundary."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_identity(
        self,
        *,
        course_id: str,
        learning_outcome_id: str,
        created_by_user_id: int,
    ) -> AssessmentDefinition:
        outcome_id = self.session.scalar(
            select(LearningOutcome.id)
            .join(CourseModule, CourseModule.id == LearningOutcome.module_id)
            .where(
                LearningOutcome.id == learning_outcome_id,
                CourseModule.course_id == course_id,
            )
        )
        if outcome_id is None:
            raise AssessmentDefinitionNotFoundError("learning outcome not found in this course")
        identity = AssessmentDefinition(
            course_id=course_id,
            learning_outcome_id=learning_outcome_id,
            created_by_user_id=created_by_user_id,
        )
        self.session.add(identity)
        self.session.flush()
        return identity

    def get_version(
        self,
        *,
        course_id: str,
        assessment_definition_id: str,
        version: int,
        for_update: bool = False,
    ) -> AssessmentDefinitionVersion:
        statement = select(AssessmentDefinitionVersion).where(
            AssessmentDefinitionVersion.course_id == course_id,
            AssessmentDefinitionVersion.assessment_definition_id == assessment_definition_id,
            AssessmentDefinitionVersion.version == version,
        )
        if for_update:
            statement = statement.with_for_update()
        row = self.session.scalar(statement)
        if row is None:
            raise AssessmentDefinitionNotFoundError("assessment definition version not found")
        return row

    def list_versions(
        self,
        *,
        course_id: str,
        assessment_definition_id: str,
    ) -> list[AssessmentDefinitionVersion]:
        return list(
            self.session.scalars(
                select(AssessmentDefinitionVersion)
                .where(
                    AssessmentDefinitionVersion.course_id == course_id,
                    AssessmentDefinitionVersion.assessment_definition_id
                    == assessment_definition_id,
                )
                .order_by(AssessmentDefinitionVersion.version)
            ).all()
        )
