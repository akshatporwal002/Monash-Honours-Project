"""References to real authoring inputs; never accepts invented response content."""

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GenerationContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    variant_task_id: str | None = Field(default=None, min_length=1, max_length=100)
    variant_revision_id: str | None = Field(default=None, min_length=1, max_length=100)
    response_version_id: str | None = Field(default=None, min_length=1, max_length=100)
    feedback_id: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def paired_references(self):
        if bool(self.variant_task_id) != bool(self.variant_revision_id):
            raise ValueError("A variant needs its task and exact revision")
        if bool(self.response_version_id) != bool(self.feedback_id):
            raise ValueError("Feedback conditioning needs an actual response and feedback pair")
        if self.variant_task_id and self.response_version_id:
            raise ValueError("Choose either a task variant or feedback-conditioned generation")
        return self


class GenerationOption(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(min_length=1, max_length=500)
    context: GenerationContext
