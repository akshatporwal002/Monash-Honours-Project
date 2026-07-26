from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.api.dependencies.authentication import get_current_user
from app.models.user import User, UserRole


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    allowed = frozenset(roles)

    def dependency(
        user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account is not authorised for this operation",
            )
        return user

    return dependency


require_student = require_roles(UserRole.STUDENT)
require_educator = require_roles(UserRole.EDUCATOR)
require_administrator = require_roles(UserRole.ADMINISTRATOR)
require_educator_or_administrator = require_roles(
    UserRole.EDUCATOR,
    UserRole.ADMINISTRATOR,
)

CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentStudent = Annotated[User, Depends(require_student)]
CurrentEducator = Annotated[User, Depends(require_educator)]
CurrentAdministrator = Annotated[User, Depends(require_administrator)]
