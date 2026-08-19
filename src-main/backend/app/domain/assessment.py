"""Canonical assessment language shared across persistence and API contracts."""

from enum import StrEnum


class AssessmentResult(StrEnum):
    PASS = "PASS"
    INCOMPLETE = "INCOMPLETE"


class AssessmentReasonCode(StrEnum):
    TARGET_EVIDENCE_MET = "TARGET_EVIDENCE_MET"
    MISSING_REQUIRED_EVIDENCE = "MISSING_REQUIRED_EVIDENCE"
    CRITERIA_NOT_MET = "CRITERIA_NOT_MET"
    TARGET_BLOOM_ACTION_NOT_SHOWN = "TARGET_BLOOM_ACTION_NOT_SHOWN"
    CRITICAL_CONCEPT_GAP = "CRITICAL_CONCEPT_GAP"
    INDEPENDENT_EVIDENCE_NOT_SHOWN = "INDEPENDENT_EVIDENCE_NOT_SHOWN"
    TRANSFER_EVIDENCE_NOT_SHOWN = "TRANSFER_EVIDENCE_NOT_SHOWN"
    UNRESOLVED_EVIDENCE_CONFLICT = "UNRESOLVED_EVIDENCE_CONFLICT"
    TASK_UNDER_HUMAN_REVIEW = "TASK_UNDER_HUMAN_REVIEW"


def public_assessment_reason_code(value: str | AssessmentReasonCode) -> AssessmentReasonCode:
    """Map stored pre-contract codes without exposing a new public reason."""

    legacy = {
        "CONFLICTING_CRITERION_EVIDENCE": AssessmentReasonCode.UNRESOLVED_EVIDENCE_CONFLICT,
        "REQUIRED_CRITERION_EVIDENCE_MISSING": (AssessmentReasonCode.MISSING_REQUIRED_EVIDENCE),
        "CRITERION_NOT_EVALUABLE": AssessmentReasonCode.MISSING_REQUIRED_EVIDENCE,
        "CRITERION_EVIDENCE_NOT_MET": AssessmentReasonCode.CRITERIA_NOT_MET,
        "PASS_RULE_NOT_MET": AssessmentReasonCode.CRITERIA_NOT_MET,
    }
    try:
        return AssessmentReasonCode(value)
    except ValueError:
        mapped = legacy.get(str(value))
        if mapped is None:
            raise ValueError("unknown assessment reason code") from None
        return mapped


class ResultState(StrEnum):
    NOT_ASSESSED = "NOT_ASSESSED"
    PROVISIONAL = "PROVISIONAL"
    CONFIRMED = "CONFIRMED"
    OVERRIDDEN = "OVERRIDDEN"
    VOID = "VOID"


class AssessmentAttemptState(StrEnum):
    PENDING = "PENDING"
    EVALUATED = "EVALUATED"
    FAULTED = "FAULTED"
    VOID = "VOID"


class AssessorReviewAction(StrEnum):
    CONFIRM = "CONFIRM"
    OVERRIDE = "OVERRIDE"
    WITHHOLD = "WITHHOLD"
    VOID = "VOID"
    RETURN = "RETURN"


class AppealOrCorrectionState(StrEnum):
    PENDING = "PENDING"
    RESOLVED = "RESOLVED"
    WITHDRAWN = "WITHDRAWN"


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
    "AssessmentAttemptState",
    "AssessmentReasonCode",
    "AssessmentResult",
    "AppealOrCorrectionState",
    "AssessorReviewAction",
    "BloomKnowledge",
    "BloomProcess",
    "CriterionDecision",
    "MisconceptionState",
    "QualityReviewDecision",
    "ResultState",
    "SubmissionState",
    "public_assessment_reason_code",
]
