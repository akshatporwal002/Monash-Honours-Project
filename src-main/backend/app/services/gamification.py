from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import (
    Achievement,
    LearningTask,
    StudentAchievement,
    StudentProfile,
    SubmissionAttempt,
    TaskPointAward,
    TaskType,
)
from app.models.gamification import GamificationPreference, ParticipationRecognition
from app.models.user import User
from app.schemas.gamification import GamificationPreferenceRead


@dataclass(frozen=True, slots=True)
class GamificationResult:
    points_awarded: int
    total_points: int
    achievement_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AchievementDefinition:
    id: str
    code: str
    name: str
    description: str
    icon: str


DEFAULT_ACHIEVEMENTS: tuple[AchievementDefinition, ...] = (
    AchievementDefinition(
        id="00000000-0000-4000-9000-000000000101",
        code="first-step",
        name="First Step",
        description="Take part in your first learning activity.",
        icon="✦",
    ),
    AchievementDefinition(
        id="00000000-0000-4000-9000-000000000102",
        code="circuit-maker",
        name="Circuit Maker",
        description="Take part in a circuit activity.",
        icon="⌁",
    ),
    AchievementDefinition(
        id="00000000-0000-4000-9000-000000000104",
        code="reflection",
        name="Looking back",
        description="Record a reflection on your learning.",
        icon="✦",
    ),
    AchievementDefinition(
        id="00000000-0000-4000-9000-000000000105",
        code="revision",
        name="Another look",
        description="Record a revision of your earlier work.",
        icon="✦",
    ),
    AchievementDefinition(
        id="00000000-0000-4000-9000-000000000106",
        code="feedback-use",
        name="Feedback considered",
        description="Acknowledge feedback on your work.",
        icon="✦",
    ),
)


def ensure_default_achievements(session: Session) -> None:
    """Insert any missing canonical definitions without demo-data dependencies."""
    existing_codes = set(session.scalars(select(Achievement.code)).all())
    added = False
    for definition in DEFAULT_ACHIEVEMENTS:
        if definition.code in existing_codes:
            continue
        session.add(
            Achievement(
                id=definition.id,
                code=definition.code,
                name=definition.name,
                description=definition.description,
                icon=definition.icon,
            )
        )
        added = True
    if added:
        session.flush()


class GamificationService:
    """Own the independently testable completion-to-reward policy."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def preference(self, student_id: int) -> GamificationPreferenceRead:
        row = self.session.scalar(
            select(GamificationPreference)
            .where(GamificationPreference.student_id == student_id)
            .order_by(GamificationPreference.revision.desc())
            .limit(1)
        )
        return (
            GamificationPreferenceRead.model_validate(row)
            if row
            else GamificationPreferenceRead(enabled=True, revision=0)
        )

    def save_preference(self, student_id, command):
        self.session.execute(
            update(User).where(User.id == student_id).values(id=User.id, updated_at=User.updated_at)
        )
        existing = self.session.scalar(
            select(GamificationPreference).where(
                GamificationPreference.student_id == student_id,
                GamificationPreference.request_key == command.idempotency_key,
            )
        )
        current = self.preference(student_id)
        if existing:
            if (
                existing.enabled != command.enabled
                or existing.revision != command.expected_revision + 1
            ):
                raise ValueError("This preference key already has different details")
            self.session.rollback()
            return current
        if current.revision != command.expected_revision:
            raise ValueError("Gamification preferences changed; reload before saving")
        row = GamificationPreference(
            student_id=student_id,
            revision=current.revision + 1,
            request_key=command.idempotency_key,
            enabled=command.enabled,
        )
        self.session.add(row)
        self.session.commit()
        return GamificationPreferenceRead.model_validate(row)

    def recognise_evidence(self, learner_id, task, kind, evidence_id):
        codes = {
            "REFLECTION": "reflection",
            "REVISION": "revision",
            "FEEDBACK_INTERACTION": "feedback-use",
        }
        if kind not in codes or not self.preference(learner_id).enabled:
            return
        profile = self.session.scalar(
            select(StudentProfile).where(StudentProfile.user_id == learner_id)
        )
        if profile is None or self.session.scalar(
            select(ParticipationRecognition.id).where(
                ParticipationRecognition.student_id == learner_id,
                ParticipationRecognition.task_id == task.id,
                ParticipationRecognition.kind == kind,
            )
        ):
            return
        self.session.add(
            ParticipationRecognition(
                student_id=learner_id, task_id=task.id, kind=kind, evidence_id=evidence_id
            )
        )
        self._award_achievements(profile, {codes[kind]})
        self.session.flush()

    @staticmethod
    def level(total_points: int, points_per_level: int) -> int:
        if points_per_level <= 0:
            raise ValueError("points_per_level must be positive")
        return total_points // points_per_level + 1

    def award_completion(
        self,
        profile: StudentProfile,
        task: LearningTask,
        attempt: SubmissionAttempt,
    ) -> GamificationResult:
        if (
            attempt.task_form_version_id is not None
            or not self.preference(attempt.student_id).enabled
        ):
            return GamificationResult(0, profile.points, ())
        ensure_default_achievements(self.session)
        existing_award = self.session.scalar(
            select(TaskPointAward.id).where(
                TaskPointAward.student_id == attempt.student_id,
                TaskPointAward.task_id == task.id,
            )
        )
        points_awarded = 0
        if existing_award is None:
            points_awarded = task.points
            profile.points += points_awarded
            self.session.add(
                TaskPointAward(
                    student_id=attempt.student_id,
                    task_id=task.id,
                    attempt_id=attempt.id,
                    points=points_awarded,
                )
            )

        wanted = {"first-step"}
        if task.task_type in {TaskType.QUANTUM_CIRCUIT, TaskType.CIRCUIT}:
            wanted.add("circuit-maker")
        new_codes = self._award_achievements(profile, wanted)
        self.session.flush()
        return GamificationResult(points_awarded, profile.points, tuple(sorted(new_codes)))

    def _award_achievements(self, profile, wanted):
        ensure_default_achievements(self.session)
        earned_codes = set(
            self.session.scalars(
                select(Achievement.code)
                .join(StudentAchievement)
                .where(StudentAchievement.student_id == profile.id)
            ).all()
        )
        new_codes: list[str] = []
        for achievement in self.session.scalars(
            select(Achievement).where(Achievement.code.in_(wanted - earned_codes))
        ).all():
            self.session.add(
                StudentAchievement(
                    student_id=profile.id,
                    achievement_id=achievement.id,
                )
            )
            new_codes.append(achievement.code)
        # The application session disables autoflush. Flush here so a repeated
        # award call in the same transaction observes the unique award/achievement.
        self.session.flush()
        return new_codes
