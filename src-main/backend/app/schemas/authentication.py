from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import ScopedRole, UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class ActiveScopedRoleAssignmentResponse(BaseModel):
    id: str
    course_id: str
    role: ScopedRole
    version: int
    valid_from: datetime
    valid_until: datetime | None

    model_config = ConfigDict(from_attributes=True)


class AuthenticatedUserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    scoped_assignments: list[ActiveScopedRoleAssignmentResponse]

    model_config = ConfigDict(from_attributes=True)
