"""Append-only records of explicit approved support actions, without grading effects."""

from sqlalchemy import select

from app.models.episode import EpisodeHelpUse, EpisodeStageStart
from app.schemas.episode import EpisodeHelpUseRead
from app.services.episodes import EpisodeService
from app.services.misconception_state import active_fresh_check
from app.services.task_review import TaskReviewError


class EpisodeSupportService:
    def __init__(self, session):
        self.session = session

    def record(self, work, payload):
        if work is None or work.id != payload.assessment_work_start_id:
            raise TaskReviewError("Support action does not match this assessment work", 409)
        plan = EpisodeService(self.session).work_plan(work)
        if plan is None:
            raise TaskReviewError("This task has no approved episode support", 422)
        fresh_check = active_fresh_check(self.session, work.student_id, work.task_id)
        stage = self.session.scalar(
            select(EpisodeStageStart).where(EpisodeStageStart.assessment_work_start_id == work.id)
        )
        items = (
            (*plan.supported_hints, *(item.text for item in plan.support_representations))
            if payload.kind == "conceptual_hint"
            else plan.accessibility_support
        )
        representation_index = payload.item_index - len(plan.supported_hints)
        representation = (
            plan.support_representations[representation_index].model_dump(mode="json")
            if payload.kind == "conceptual_hint"
            and 0 <= representation_index < len(plan.support_representations)
            else None
        )
        prior = self.session.scalar(
            select(EpisodeHelpUse).where(
                EpisodeHelpUse.assessment_work_start_id == work.id,
                EpisodeHelpUse.request_key == payload.request_key,
            )
        )
        if prior:
            if (prior.stage_start_id, prior.kind, prior.item_index) != (
                payload.stage_start_id,
                payload.kind,
                payload.item_index,
            ):
                raise TaskReviewError(
                    "Support request key was already used for another action", 409
                )
            return {
                "record": self.read(prior),
                "representation": None if stage or fresh_check else representation,
                "content": None
                if payload.kind == "conceptual_hint" and (stage or fresh_check)
                else items[payload.item_index],
            }
        if payload.stage_start_id != (stage.id if stage else None):
            raise TaskReviewError("Support action does not match the current episode stage", 409)
        if payload.kind == "conceptual_hint" and (stage or fresh_check):
            raise TaskReviewError(
                "Instructional hints are unavailable during fresh application", 422
            )
        if payload.item_index >= len(items):
            raise TaskReviewError("This support item is not in the reviewed plan", 422)
        record = EpisodeHelpUse(
            student_id=work.student_id,
            task_id=work.task_id,
            assessment_work_start_id=work.id,
            task_form_version_id=work.task_form_version_id,
            stage_start_id=stage.id if stage else None,
            part_id=stage.part_id if stage else plan.supported_part_id,
            kind=payload.kind,
            item_index=payload.item_index,
            request_key=payload.request_key,
        )
        self.session.add(record)
        self.session.flush()
        return {
            "record": self.read(record),
            "content": items[payload.item_index],
            "representation": representation,
        }

    @staticmethod
    def read(record):
        return EpisodeHelpUseRead.model_validate(record, from_attributes=True)

    def history(self, student_id, task_id, *, limit=20, offset=0):
        if not 1 <= limit <= 100 or offset < 0:
            raise TaskReviewError("Invalid support history page", 422)
        records = list(
            self.session.scalars(
                select(EpisodeHelpUse)
                .where(
                    EpisodeHelpUse.student_id == student_id,
                    EpisodeHelpUse.task_id == task_id,
                )
                .order_by(EpisodeHelpUse.created_at.desc(), EpisodeHelpUse.id.desc())
                .limit(limit + 1)
                .offset(offset)
            )
        )
        return {
            "items": [self.read(item) for item in records[:limit]],
            "next_offset": offset + limit if len(records) > limit else None,
        }
