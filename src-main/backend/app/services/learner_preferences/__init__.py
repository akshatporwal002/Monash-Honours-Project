"""Owned preference history and a small read interface for later consumers."""

from datetime import UTC
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.models.learner_preferences import LearnerPreferenceRevision
from app.models.user import User, UserRole
from app.schemas.learner_preferences import (
    EffectivePreferences,
    PreferenceHistory,
    PreferenceRead,
    PreferenceReset,
    PreferenceRevision,
    PreferenceUpdate,
    PreferenceValues,
)


class PreferenceConflict(ValueError):
    pass


class PreferenceUnavailable(ValueError):
    pass


def effective_preferences(
    saved: PreferenceRead, *, transfer: bool, repeat_allowed: bool
) -> EffectivePreferences:
    values = (
        saved.values.model_copy()
        if saved.values.personalisation_enabled
        else PreferenceValues(personalisation_enabled=False)
    )
    limits = [
        "Preferences change optional presentation only. The approved response form and required feedback stay available."
    ]
    if not saved.values.personalisation_enabled:
        limits.append(
            "Personalisation is off. Baseline presentation is active; your choices are retained."
        )
    if transfer:
        values = values.model_copy(
            update={
                "pace": "self_paced",
                "format": "text",
                "explanation_detail": "brief",
                "support_amount": "standard",
                "repeat_practice": False,
            }
        )
        limits.append(
            "Fresh application is unaided. Optional guidance and repeat practice are unavailable; approved access support remains available."
        )
    if not repeat_allowed:
        values = values.model_copy(update={"repeat_practice": False})
        limits.append(
            "This task does not offer repeat practice. Earlier work remains readable; reassessment needs separate approval."
        )
    return EffectivePreferences(
        version=saved.version,
        values=values,
        requested=saved.values,
        transfer=transfer,
        repeat_allowed=repeat_allowed and not transfer,
        limitations=limits,
    )


class LearnerPreferenceService:
    def __init__(self, session: Session):
        self.session = session

    def _owner(self, actor: User) -> int:
        current = self.session.get(User, actor.id, populate_existing=True)
        if current is None or not current.is_active or current.role is not UserRole.STUDENT:
            raise PermissionError("Only an active learner can manage their preferences")
        return current.id

    @staticmethod
    def _read(row: LearnerPreferenceRevision) -> PreferenceRevision:
        return PreferenceRevision(
            version=row.version,
            values=PreferenceValues(
                **{
                    name: getattr(row, name)
                    for name in PreferenceValues.model_fields
                    if name not in {"pace", "format", "explanation_detail"}
                },
                pace="stepwise" if row.pace == "SLOWER" else "self_paced",
                format="stepwise" if row.format == "STEPWISE" else "text",
                explanation_detail="detailed" if row.explanation_detail == "DETAILED" else "brief",
            ),
            action=row.action,
            created_at=row.created_at.replace(tzinfo=UTC)
            if row.created_at.tzinfo is None
            else row.created_at,
        )

    def read(self, actor: User) -> PreferenceRead:
        owner = self._owner(actor)
        row = self.session.scalar(
            select(LearnerPreferenceRevision)
            .where(LearnerPreferenceRevision.learner_id == owner)
            .order_by(LearnerPreferenceRevision.version.desc())
            .limit(1)
        )
        return (
            PreferenceRead(version=row.version, values=self._read(row).values)
            if row
            else PreferenceRead(version=0, values=PreferenceValues())
        )

    def history(self, actor: User, *, offset: int = 0, limit: int = 20) -> PreferenceHistory:
        if offset < 0 or not 1 <= limit <= 100:
            raise ValueError("Invalid history page")
        owner = self._owner(actor)
        rows = list(
            self.session.scalars(
                select(LearnerPreferenceRevision)
                .where(LearnerPreferenceRevision.learner_id == owner)
                .order_by(LearnerPreferenceRevision.version.desc())
                .offset(offset)
                .limit(limit + 1)
            )
        )
        return PreferenceHistory(
            items=[self._read(row) for row in rows[:limit]],
            next_offset=offset + limit if len(rows) > limit else None,
        )

    def save(self, actor: User, command: PreferenceUpdate | PreferenceReset) -> PreferenceRead:
        action = "save" if isinstance(command, PreferenceUpdate) else "reset"
        values = command.values if isinstance(command, PreferenceUpdate) else PreferenceValues()
        owner = self._owner(actor)
        try:
            prior = self.session.scalar(
                select(LearnerPreferenceRevision).where(
                    LearnerPreferenceRevision.learner_id == owner,
                    LearnerPreferenceRevision.request_key == command.request_key,
                )
            )
            if prior:
                if (
                    prior.version != command.expected_version + 1
                    or prior.action != action
                    or self._read(prior).values != values
                ):
                    raise PreferenceConflict(
                        "This request key was already used for another change."
                    )
                return PreferenceRead(version=prior.version, values=self._read(prior).values)
            if self.read(actor).version != command.expected_version:
                raise PreferenceConflict(
                    "Preferences changed in another session. Refresh the saved version before saving your draft."
                )
            row = LearnerPreferenceRevision(
                learner_id=owner,
                version=command.expected_version + 1,
                request_key=command.request_key,
                action=action,
                **values.model_dump(exclude={"pace", "format", "explanation_detail"}),
                pace="SLOWER" if values.pace == "stepwise" else "DEFAULT",
                format="STEPWISE" if values.format == "stepwise" else "TEXT",
                explanation_detail="DETAILED"
                if values.explanation_detail == "detailed"
                else "BRIEF",
                schema_version="learnlens.learner-preferences.v1",
                actor_reference=str(owner),
                correlation_id=str(uuid4()),
                prior_revision_id=self.session.scalar(
                    select(LearnerPreferenceRevision.id)
                    .where(LearnerPreferenceRevision.learner_id == owner)
                    .order_by(LearnerPreferenceRevision.revision.desc())
                    .limit(1)
                ),
            )
            self.session.add(row)
            self.session.commit()
            return PreferenceRead(version=row.version, values=values)
        except IntegrityError:
            self.session.rollback()
            prior = self.session.scalar(
                select(LearnerPreferenceRevision).where(
                    LearnerPreferenceRevision.learner_id == owner,
                    LearnerPreferenceRevision.request_key == command.request_key,
                )
            )
            if (
                prior
                and prior.version == command.expected_version + 1
                and prior.action == action
                and self._read(prior).values == values
            ):
                return PreferenceRead(version=prior.version, values=self._read(prior).values)
            raise PreferenceConflict(
                "Another save completed first. Refresh the saved version and retry."
            ) from None
        except OperationalError:
            self.session.rollback()
            raise PreferenceUnavailable(
                "Preferences could not be saved. Retry the same change."
            ) from None
        except Exception:
            self.session.rollback()
            raise
