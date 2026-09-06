"""SQLite repository for course-scoped material lifecycle operations."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LearningMaterial
from app.services.rag.errors import MaterialNotFoundError


class MaterialRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def find_by_course_hash(self, course_id: str, content_hash: str) -> LearningMaterial | None:
        return self.session.scalar(
            select(LearningMaterial).where(
                LearningMaterial.course_id == course_id,
                LearningMaterial.content_hash == content_hash,
            )
        )

    def get(
        self, course_id: str, material_id: str, *, include_retired: bool = False
    ) -> LearningMaterial:
        material = self.session.scalar(
            select(LearningMaterial).where(
                LearningMaterial.course_id == course_id,
                LearningMaterial.id == material_id,
            )
        )
        if material is None or (material.retired_at is not None and not include_retired):
            raise MaterialNotFoundError()
        return material

    def list(
        self, course_id: str, module_id: str | None = None, indexing_status: str | None = None
    ) -> list[LearningMaterial]:
        statement = select(LearningMaterial).where(
            LearningMaterial.course_id == course_id, LearningMaterial.retired_at.is_(None)
        )
        if module_id is not None:
            statement = statement.where(LearningMaterial.module_id == module_id)
        if indexing_status is not None:
            statement = statement.where(LearningMaterial.indexing_status == indexing_status)
        return list(
            self.session.scalars(statement.order_by(LearningMaterial.created_at.desc())).all()
        )
