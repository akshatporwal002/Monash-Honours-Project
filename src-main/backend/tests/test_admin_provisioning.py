import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models.lms import PlatformAuditEvent
from app.models.user import User, UserRole
from app.provision_admin import (
    AdministratorAlreadyProvisionedError,
    provision_first_administrator,
)
from app.schemas.lms import AdminUserCreate


def _administrator_payload() -> AdminUserCreate:
    return AdminUserCreate(
        email=" First.Admin@Example.edu ",
        full_name="First Administrator",
        password="correct horse battery staple",
        role=UserRole.ADMINISTRATOR,
    )


def test_first_administrator_is_hashed_audited_and_one_time(
    db_session: Session,
) -> None:
    payload = _administrator_payload()

    administrator = provision_first_administrator(db_session, payload)

    assert administrator.email == "first.admin@example.edu"
    assert administrator.role is UserRole.ADMINISTRATOR
    assert administrator.password_hash != payload.password
    assert verify_password(payload.password, administrator.password_hash)
    audit = db_session.scalar(
        select(PlatformAuditEvent).where(
            PlatformAuditEvent.action == "account.first_administrator_provisioned"
        )
    )
    assert audit is not None
    assert audit.actor_id == administrator.id
    assert audit.resource_id == str(administrator.id)
    assert audit.details == {"source": "interactive_provisioning"}
    assert payload.password not in str(audit.details)

    db_session.rollback()
    with pytest.raises(
        AdministratorAlreadyProvisionedError,
        match="already been provisioned",
    ):
        provision_first_administrator(
            db_session,
            AdminUserCreate(
                email="second.admin@example.edu",
                full_name="Second Administrator",
                password="another secure password",
                role=UserRole.ADMINISTRATOR,
            ),
        )

    assert db_session.scalar(select(func.count()).select_from(User)) == 1
