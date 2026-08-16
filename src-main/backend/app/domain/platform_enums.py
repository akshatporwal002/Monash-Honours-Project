"""Person B platform language kept separate from formal assessment enums."""

from enum import IntEnum, StrEnum


class EvidenceType(StrEnum):
    PREDICTION = "PREDICTION"
    EXPLANATION = "EXPLANATION"
    REASONING = "REASONING"
    RESPONSE = "RESPONSE"
    REVISION = "REVISION"
    CONFIDENCE = "CONFIDENCE"
    HINT = "HINT"
    SCAFFOLD = "SCAFFOLD"
    FEEDBACK_INTERACTION = "FEEDBACK_INTERACTION"
    REFLECTION = "REFLECTION"
    SIMULATION = "SIMULATION"
    MISCONCEPTION_CHECK = "MISCONCEPTION_CHECK"
    TRANSFER = "TRANSFER"
    DIAGNOSTIC = "DIAGNOSTIC"
    SYSTEM_FAULT = "SYSTEM_FAULT"


class EvidenceProvenance(StrEnum):
    LEARNER = "LEARNER"
    EDUCATOR = "EDUCATOR"
    SYSTEM = "SYSTEM"
    SIMULATOR = "SIMULATOR"


class InstructionalSupportLevel(IntEnum):
    INDEPENDENT = 0
    GOAL_REMINDER = 1
    CONCEPT_CUE = 2
    NARROWING_HINT = 3
    PARTIAL_WORKED_STEP = 4
    DIRECT_ANSWER = 5


class AccessSupportState(StrEnum):
    NOT_DECLARED = "NOT_DECLARED"
    APPROVED = "APPROVED"
    PROVIDED = "PROVIDED"


class ObservationType(StrEnum):
    DIRECT = "DIRECT"
    SELF_REPORTED = "SELF_REPORTED"
    SYSTEM_CAPTURED = "SYSTEM_CAPTURED"
    EDUCATOR_RECORDED = "EDUCATOR_RECORDED"


class InferenceStatus(StrEnum):
    UNCERTAIN = "UNCERTAIN"
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class CorrectionAction(StrEnum):
    ANNOTATED = "ANNOTATED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class ModelSource(StrEnum):
    RULE_BASED = "RULE_BASED"
    ADVISORY_MODEL = "ADVISORY_MODEL"
    EDUCATOR = "EDUCATOR"
    LEARNER = "LEARNER"


class EvidenceLinkRelation(StrEnum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    DERIVES_FROM = "DERIVES_FROM"


__all__ = [
    "AccessSupportState",
    "CorrectionAction",
    "EvidenceLinkRelation",
    "EvidenceProvenance",
    "EvidenceType",
    "InferenceStatus",
    "InstructionalSupportLevel",
    "ModelSource",
    "ObservationType",
]
