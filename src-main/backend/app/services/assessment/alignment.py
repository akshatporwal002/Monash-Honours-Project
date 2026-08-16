"""Validation for assessor-authored assessment definition drafts."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.domain.assessment import BloomProcess
from app.models.assessment import CriterionVersion, TaskFormVersion


class AssessmentAlignmentError(ValueError):
    """A definition draft does not preserve the intended assessment construct."""


def validate_definition_alignment(
    *,
    claim: str,
    supporting_evidence: Any,
    contradicting_evidence: Any,
    insufficient_evidence: Any,
    task_conditions: Any,
    next_action_contract: Any,
    permitted_tools: Any,
    instructional_support: Any,
    access_conditions: Any,
    transfer_rule: Any,
    evidence_sufficiency: Any,
    bloom_process: BloomProcess,
    criteria: Iterable[CriterionVersion],
    task_forms: Iterable[TaskFormVersion],
) -> None:
    """Require a complete, construct-preserving, Bloom-aligned definition.

    The stored JSON remains deliberately extensible.  The keys checked here are
    the minimum declarations needed before an assessor can approve a formal
    assessment.  A task form must declare the processes it elicits, and each
    approved access mode must state that it preserves the construct.
    """

    _require_text(claim, "claim")
    _require_nonempty_structure(supporting_evidence, "supporting_evidence")
    _require_nonempty_structure(contradicting_evidence, "contradicting_evidence")
    _require_nonempty_structure(insufficient_evidence, "insufficient_evidence")
    _require_nonempty_structure(task_conditions, "task_conditions")
    _require_nonempty_structure(next_action_contract, "next_action_contract")
    _require_nonempty_structure(permitted_tools, "permitted_tools")
    _require_nonempty_structure(instructional_support, "instructional_support")
    _require_nonempty_structure(transfer_rule, "transfer_rule")
    _require_nonempty_structure(evidence_sufficiency, "evidence_sufficiency")
    _validate_access_modes(access_conditions)

    criterion_rows = list(criteria)
    if not criterion_rows or not any(row.mandatory for row in criterion_rows):
        raise AssessmentAlignmentError("an approved definition requires a mandatory criterion")
    for criterion in criterion_rows:
        _require_text(criterion.learner_description, "criterion learner description")
        _require_text(criterion.evidence_description, "criterion evidence description")
        _require_text(criterion.met_rule, "criterion met rule")
        _require_text(criterion.not_met_rule, "criterion not-met rule")
        _require_text(criterion.not_evaluable_rule, "criterion not-evaluable rule")
        if not _is_nonempty_structure(criterion.evidence_source_types):
            raise AssessmentAlignmentError("criteria require declared evidence source types")

    form_rows = list(task_forms)
    if not form_rows:
        raise AssessmentAlignmentError("an approved definition requires an approved task form")
    for form in form_rows:
        declared_processes = _declared_processes(form.constraints)
        if bloom_process.value not in declared_processes:
            raise AssessmentAlignmentError(
                "task form does not declare evidence for the target Bloom process"
            )


def _validate_access_modes(value: Any) -> None:
    if not isinstance(value, dict):
        raise AssessmentAlignmentError("access_conditions must be an object")
    modes = value.get("modes")
    if not isinstance(modes, list) or not modes:
        raise AssessmentAlignmentError("access_conditions require one or more declared modes")
    names: set[str] = set()
    for mode in modes:
        if not isinstance(mode, dict):
            raise AssessmentAlignmentError("each access mode must be an object")
        name = mode.get("mode")
        if not isinstance(name, str) or not name.strip():
            raise AssessmentAlignmentError("each access mode requires a name")
        if name in names:
            raise AssessmentAlignmentError("access mode names must be unique")
        names.add(name)
        if mode.get("preserves_construct") is not True:
            raise AssessmentAlignmentError(
                "an access mode that changes the intended construct cannot be approved"
            )


def _declared_processes(constraints: Any) -> set[str]:
    if not isinstance(constraints, dict):
        raise AssessmentAlignmentError("task-form constraints must be an object")
    processes = constraints.get("elicited_bloom_processes")
    if not isinstance(processes, list) or not processes:
        raise AssessmentAlignmentError(
            "task forms must declare the Bloom processes their evidence elicits"
        )
    if not all(isinstance(process, str) for process in processes):
        raise AssessmentAlignmentError("declared Bloom processes must be strings")
    return set(processes)


def _require_text(value: Any, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise AssessmentAlignmentError(f"{name} is required")


def _require_nonempty_structure(value: Any, name: str) -> None:
    if not _is_nonempty_structure(value):
        raise AssessmentAlignmentError(f"{name} must be a non-empty object or list")


def _is_nonempty_structure(value: Any) -> bool:
    return isinstance(value, (dict, list)) and bool(value)
