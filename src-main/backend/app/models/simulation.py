"""Append-only circuit inputs, execution requests, and terminal evidence."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    DDL,
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.persistence import utc_now


class CircuitVersion(Base):
    __tablename__ = "circuit_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    task_id: Mapped[str | None] = mapped_column(
        ForeignKey("learning_tasks.id", ondelete="RESTRICT")
    )
    course_id: Mapped[str | None] = mapped_column(ForeignKey("courses.id", ondelete="RESTRICT"))
    content_digest: Mapped[str] = mapped_column(String(64))
    circuit: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SimulationRun(Base):
    __tablename__ = "simulation_runs"
    __table_args__ = (
        UniqueConstraint("owner_id", "request_key", name="uq_simulation_request"),
        CheckConstraint("shots BETWEEN 1 AND 4096", name="simulation_shots"),
        CheckConstraint("seed BETWEEN 0 AND 4294967295", name="simulation_seed"),
        CheckConstraint("purpose IN ('practice', 'task', 'feedback')", name="simulation_purpose"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    request_key: Mapped[str] = mapped_column(String(128))
    circuit_version_id: Mapped[str] = mapped_column(
        ForeignKey("circuit_versions.id", ondelete="RESTRICT")
    )
    submission_id: Mapped[str | None] = mapped_column(
        ForeignKey("submission_attempts.id", ondelete="RESTRICT")
    )
    purpose: Mapped[str] = mapped_column(String(16))
    shots: Mapped[int] = mapped_column(Integer)
    seed: Mapped[int] = mapped_column(BigInteger)
    policy_version: Mapped[str] = mapped_column(String(64))
    engine_versions: Mapped[dict[str, str]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SimulationOutcome(Base):
    __tablename__ = "simulation_outcomes"
    __table_args__ = (
        CheckConstraint(
            "status IN ('completed', 'failed', 'timed_out', 'interrupted')",
            name="simulation_status",
        ),
        CheckConstraint(
            "(status = 'completed' AND result IS NOT NULL AND error_code IS NULL) OR (status != 'completed' AND result IS NULL AND error_code IS NOT NULL)",
            name="simulation_terminal_shape",
        ),
    )

    id: Mapped[str] = mapped_column(
        ForeignKey("simulation_runs.id", ondelete="RESTRICT"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(16))
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


def _immutable(*_: Any) -> None:
    raise ValueError("Simulation evidence is append-only")


for _model in (CircuitVersion, SimulationRun, SimulationOutcome):
    event.listen(_model, "before_update", _immutable)
    event.listen(_model, "before_delete", _immutable)
    event.listen(
        _model.__table__,
        "after_create",
        DDL(
            f"CREATE TRIGGER {_model.__tablename__}_no_replace BEFORE INSERT ON {_model.__tablename__} "
            f"WHEN EXISTS (SELECT 1 FROM {_model.__tablename__} WHERE id = NEW.id) "
            "BEGIN SELECT RAISE(ABORT, 'Simulation evidence is append-only'); END"
        ).execute_if(dialect="sqlite"),
    )
    for _action in ("UPDATE", "DELETE"):
        event.listen(
            _model.__table__,
            "after_create",
            DDL(
                f"CREATE TRIGGER {_model.__tablename__}_no_{_action.lower()} BEFORE {_action} ON {_model.__tablename__} "
                "BEGIN SELECT RAISE(ABORT, 'Simulation evidence is append-only'); END"
            ).execute_if(dialect="sqlite"),
        )

event.listen(
    SimulationRun.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER simulation_runs_no_request_replace BEFORE INSERT ON simulation_runs "
        "WHEN EXISTS (SELECT 1 FROM simulation_runs WHERE owner_id = NEW.owner_id AND request_key = NEW.request_key) "
        "BEGIN SELECT RAISE(ABORT, 'Simulation evidence is append-only'); END"
    ).execute_if(dialect="sqlite"),
)
