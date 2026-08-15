from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserRole(StrEnum):
    STUDENT = "student"
    EDUCATOR = "educator"
    ADMINISTRATOR = "administrator"


class ScopedRole(StrEnum):
    ASSESSOR = "assessor"
    RESEARCH = "research"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_role",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda roles: [role.value for role in roles],
        )
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    student_profile: Mapped["StudentProfile | None"] = relationship(  # noqa: F821
        back_populates="user",
        uselist=False,
    )


class RoleAssignment(Base):
    __tablename__ = "role_assignments"
    __table_args__ = (
        UniqueConstraint(
            "subject_user_id",
            "course_id",
            "role",
            "version",
            name="uq_role_assignments_subject_course_role_version",
        ),
        CheckConstraint("version > 0", name="role_assignment_version"),
        CheckConstraint(
            "length(trim(reason)) > 0",
            name="role_assignment_reason",
        ),
        CheckConstraint(
            "valid_until IS NULL OR valid_until > valid_from",
            name="role_assignment_valid_window",
        ),
        CheckConstraint(
            "(revoked_at IS NULL AND revoked_by_user_id IS NULL "
            "AND revocation_reason IS NULL) OR "
            "(revoked_at IS NOT NULL AND revoked_by_user_id IS NOT NULL "
            "AND length(trim(revocation_reason)) > 0)",
            name="role_assignment_revocation_shape",
        ),
        Index(
            "ix_role_assignments_subject_course_role_active",
            "subject_user_id",
            "course_id",
            "role",
            "revoked_at",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    subject_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    course_id: Mapped[str] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    role: Mapped[ScopedRole] = mapped_column(
        Enum(
            ScopedRole,
            name="scoped_role",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda roles: [role.value for role in roles],
        ),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    assigned_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    valid_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revoked_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    revocation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    supersedes_assignment_id: Mapped[str | None] = mapped_column(
        ForeignKey("role_assignments.id", ondelete="SET NULL"),
        nullable=True,
    )

    subject: Mapped[User] = relationship(foreign_keys=[subject_user_id])
    assigned_by: Mapped[User] = relationship(foreign_keys=[assigned_by_user_id])
    revoked_by: Mapped[User | None] = relationship(foreign_keys=[revoked_by_user_id])
    supersedes: Mapped["RoleAssignment | None"] = relationship(
        remote_side=[id],
        foreign_keys=[supersedes_assignment_id],
    )
