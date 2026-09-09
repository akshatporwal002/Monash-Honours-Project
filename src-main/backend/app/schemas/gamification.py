from pydantic import BaseModel, ConfigDict, Field


class GamificationPreferenceRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
    enabled: bool
    revision: int


class GamificationPreferenceWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    enabled: bool
    expected_revision: int = Field(ge=0)
    idempotency_key: str = Field(min_length=1, max_length=128)
