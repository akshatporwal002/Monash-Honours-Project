from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
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
        description="Complete your first learning activity.",
        icon="✦",
    ),
    AchievementDefinition(
        id="00000000-0000-4000-9000-000000000102",
        code="circuit-maker",
        name="Circuit Maker",
        description="Complete a circuit activity.",
        icon="⌁",
    ),
    AchievementDefinition(
        id="00000000-0000-4000-9000-000000000103",
        code="perfect-score",
        name="Quantum Ace",
        description="Earn a perfect task score.",
        icon="★",
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

        earned_codes = set(
            self.session.scalars(
                select(Achievement.code)
                .join(StudentAchievement)
                .where(StudentAchievement.student_id == profile.id)
            ).all()
        )
        wanted = {"first-step"}
        if task.task_type in {TaskType.QUANTUM_CIRCUIT, TaskType.CIRCUIT}:
            wanted.add("circuit-maker")
        if attempt.score == 100:
            wanted.add("perfect-score")
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
        return GamificationResult(
            points_awarded=points_awarded,
            total_points=profile.points,
            achievement_codes=tuple(sorted(new_codes)),
        )
