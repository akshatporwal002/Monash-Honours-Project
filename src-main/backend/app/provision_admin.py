"""Interactive, one-time provisioning for the first hosted administrator."""

from __future__ import annotations

import getpass
import sys
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.lms import PlatformAuditEvent
from app.models.user import User, UserRole
from app.schemas.lms import AdminUserCreate
from app.services.authentication import normalize_email


class AdministratorProvisioningError(RuntimeError):
    """The first administrator could not be safely provisioned."""


class AdministratorAlreadyProvisionedError(AdministratorProvisioningError):
    """At least one administrator already exists."""


def provision_first_administrator(
    session: Session,
    payload: AdminUserCreate,
) -> User:
    """Create the first administrator and its audit event in one transaction."""
    if payload.role is not UserRole.ADMINISTRATOR:
        raise AdministratorProvisioningError("the first account must be an administrator")
    if session.in_transaction():
        raise AdministratorProvisioningError("provisioning requires a fresh database session")

    try:
        if session.get_bind().dialect.name == "sqlite":
            # Serialize the empty-set check so two concurrent invocations cannot
            # both become the "first" administrator.
            session.execute(text("BEGIN IMMEDIATE"))
        existing = session.scalar(
            select(User.id).where(User.role == UserRole.ADMINISTRATOR).limit(1)
        )
        if existing is not None:
            raise AdministratorAlreadyProvisionedError(
                "an administrator has already been provisioned"
            )

        email = normalize_email(str(payload.email))
        if session.scalar(select(User.id).where(User.email == email).limit(1)) is not None:
            raise AdministratorProvisioningError("an account with that email already exists")

        administrator = User(
            email=email,
            full_name=payload.full_name,
            password_hash=hash_password(payload.password),
            role=UserRole.ADMINISTRATOR,
        )
        session.add(administrator)
        session.flush()
        session.add(
            PlatformAuditEvent(
                actor_id=administrator.id,
                action="account.first_administrator_provisioned",
                resource_type="user",
                resource_id=str(administrator.id),
                correlation_id=str(uuid4()),
                outcome="success",
                details={"source": "interactive_provisioning"},
            )
        )
        session.commit()
        return administrator
    except AdministratorProvisioningError:
        session.rollback()
        raise
    except (IntegrityError, SQLAlchemyError):
        session.rollback()
        raise AdministratorProvisioningError("the administrator could not be provisioned") from None


def main() -> int:
    if len(sys.argv) != 1:
        print(
            "This command accepts no arguments; enter credentials at its hidden prompts.",
            file=sys.stderr,
        )
        return 2
    if not sys.stdin.isatty():
        print("Administrator provisioning requires an interactive terminal.", file=sys.stderr)
        return 2

    email = input("Administrator email: ").strip()
    full_name = input("Administrator full name: ").strip()
    password = getpass.getpass("Password (minimum 8 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        print("Passwords do not match.", file=sys.stderr)
        return 2

    try:
        payload = AdminUserCreate(
            email=email,
            full_name=full_name,
            password=password,
            role=UserRole.ADMINISTRATOR,
        )
    except ValidationError:
        print("Email, name, or password does not meet the account requirements.", file=sys.stderr)
        return 2

    try:
        with SessionLocal() as session:
            administrator = provision_first_administrator(session, payload)
    except AdministratorProvisioningError as error:
        print(str(error), file=sys.stderr)
        return 2

    print(f"Provisioned administrator {administrator.email}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
