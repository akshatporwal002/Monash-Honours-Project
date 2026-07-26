from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import (
    AnyUrl,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.models.enums import MaterialIndexStatus, TaskType

ExternalId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
ContentHash = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]


class ContentSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True, strict=True)


class LearningMaterialCreate(ContentSchema):
    course_id: ExternalId
    module_id: ExternalId | None = None
    original_filename: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
        | None
    ) = None
    source_url: AnyUrl | None = None
    mime_type: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
    ]
    content_hash: ContentHash
    indexing_status: MaterialIndexStatus = MaterialIndexStatus.PENDING
    extraction_error: str | None = None

    @field_validator("source_url")
    @classmethod
    def require_https(cls, value: AnyUrl | None) -> AnyUrl | None:
        if value is not None and value.scheme != "https":
            raise ValueError("source_url must use HTTPS")
        return value

    @model_validator(mode="after")
    def require_exactly_one_source(self) -> "LearningMaterialCreate":
        if (self.original_filename is None) == (self.source_url is None):
            raise ValueError("exactly one of original_filename or source_url is required")
        return self


class LearningMaterialRead(LearningMaterialCreate):
    id: str
    source_url: str | None = None
    extracted_at: datetime | None = None
    indexed_at: datetime | None = None
    storage_key: str | None = None
    file_size_bytes: Annotated[int, Field(ge=0)] | None = None
    failure_stage: str | None = None
    error_code: str | None = None
    processing_revision: Annotated[int, Field(ge=0)] = 0
    created_at: datetime


class MaterialChunkCreate(ContentSchema):
    material_id: ExternalId
    chunk_index: Annotated[int, Field(ge=0)]
    chunk_text: NonEmptyText
    heading: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
        | None
    ) = None
    location_label: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
        | None
    ) = None
    token_count: Annotated[int, Field(ge=0)] = 0
    chunk_hash: ContentHash | None = None
    embedding_model: ExternalId | None = None
    embedding_version: ExternalId | None = None
    embedding_dimension: Annotated[int, Field(gt=0)] | None = None
    indexed_at: datetime | None = None


class MaterialChunkRead(MaterialChunkCreate):
    id: str
    created_at: datetime


class MaterialProcessingRead(ContentSchema):
    material: LearningMaterialRead
    chunk_count: Annotated[int, Field(ge=0)]
    indexed_chunk_count: Annotated[int, Field(ge=0)]
    processing_revision: Annotated[int, Field(ge=0)]


class RetrievalSearchRequest(ContentSchema):
    query: NonEmptyText
    module_id: ExternalId | None = None
    top_k: Annotated[int, Field(ge=1, le=10)] = 5
    minimum_relevance: Annotated[float, Field(ge=0, le=1)] = 0.45


class RetrievalHitRead(ContentSchema):
    chunk_id: str
    material_id: str
    source_label: NonEmptyText
    chunk_text: NonEmptyText
    relevance_score: Annotated[float, Field(ge=0, le=1)]


class RetrievalResultRead(ContentSchema):
    request_id: str
    found: bool
    hits: list[RetrievalHitRead]
    message: str | None = None
    latency_ms: Annotated[int, Field(ge=0)]
    embedding_model: ExternalId


class LearningMaterialLinkCreate(ContentSchema):
    source_url: AnyUrl
    module_id: ExternalId | None = None

    @field_validator("source_url")
    @classmethod
    def require_https_link(cls, value: AnyUrl) -> AnyUrl:
        if value.scheme != "https":
            raise ValueError("source_url must use HTTPS")
        return value


class GenerateTasksRequest(ContentSchema):
    model_config = ConfigDict(extra="forbid", from_attributes=True, strict=False)
    module_id: ExternalId | None = None
    learning_outcome_id: ExternalId
    learning_outcome_text: NonEmptyText
    task_count: Annotated[int, Field(ge=1, le=10)] = 3
    allowed_task_types: list[TaskType]
    difficulty_levels: list[
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]
    ]


class GeneratedTaskRead(ContentSchema):
    model_config = ConfigDict(extra="forbid", from_attributes=True, strict=False)
    id: str
    title: NonEmptyText
    prompt: NonEmptyText
    instructions: NonEmptyText
    task_type: TaskType
    difficulty: NonEmptyText
    learning_outcome_id: ExternalId
    source_references: list[ExternalId]


class TaskGenerationMetadata(ContentSchema):
    provider: ExternalId
    model: ExternalId
    prompt_version: ExternalId
    input_tokens: Annotated[int, Field(ge=0)]
    output_tokens: Annotated[int, Field(ge=0)]
    total_tokens: Annotated[int, Field(ge=0)]
    estimated_cost: Annotated[Decimal, Field(ge=0)]

    @model_validator(mode="after")
    def validate_token_total(self) -> "TaskGenerationMetadata":
        if self.total_tokens != self.input_tokens + self.output_tokens:
            raise ValueError("total_tokens must equal input_tokens plus output_tokens")
        return self
