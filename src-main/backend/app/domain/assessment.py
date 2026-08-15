"""Canonical assessment language shared across persistence and API contracts."""

from enum import StrEnum


class AssessmentResult(StrEnum):
    PASS = "PASS"
    INCOMPLETE = "INCOMPLETE"


class ResultState(StrEnum):
    NOT_ASSESSED = "NOT_ASSESSED"
    PROVISIONAL = "PROVISIONAL"
    CONFIRMED = "CONFIRMED"
    OVERRIDDEN = "OVERRIDDEN"
    VOID = "VOID"


class SubmissionState(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    RETURNED = "RETURNED"
    COMPLETED = "COMPLETED"


class AssessmentPurpose(StrEnum):
    DIAGNOSTIC = "DIAGNOSTIC"
    FORMATIVE = "FORMATIVE"
    AS_LEARNING = "AS_LEARNING"
    SUMMATIVE = "SUMMATIVE"
    RESEARCH = "RESEARCH"


class BloomProcess(StrEnum):
    REMEMBER = "REMEMBER"
    UNDERSTAND = "UNDERSTAND"
    APPLY = "APPLY"
    ANALYSE = "ANALYSE"
    EVALUATE = "EVALUATE"
    CREATE = "CREATE"


class BloomKnowledge(StrEnum):
    FACTUAL = "FACTUAL"
    CONCEPTUAL = "CONCEPTUAL"
    PROCEDURAL = "PROCEDURAL"
    METACOGNITIVE = "METACOGNITIVE"


class CriterionDecision(StrEnum):
    MET = "MET"
    NOT_MET = "NOT_MET"
    NOT_EVALUABLE = "NOT_EVALUABLE"


class QualityReviewDecision(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class MisconceptionState(StrEnum):
    PERSISTED = "PERSISTED"
    WEAKENED = "WEAKENED"
    CORRECTED = "CORRECTED"
    UNCERTAIN = "UNCERTAIN"


__all__ = [
    "AssessmentPurpose",
    "AssessmentResult",
    "BloomKnowledge",
    "BloomProcess",
    "CriterionDecision",
    "MisconceptionState",
    "QualityReviewDecision",
    "ResultState",
    "SubmissionState",
]
