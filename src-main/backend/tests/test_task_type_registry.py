from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from app.models import TaskType
from app.services.task_types import (
    TaskScaffold,
    TaskTypeHandler,
    TaskTypeRegistry,
    TaskTypeRegistryError,
    build_default_task_type_registry,
)


@dataclass
class TaskStub:
    expected_answer: str | None
    marking_criteria: dict[str, Any] | list[Any] | None


@dataclass
class SubmissionStub:
    answer: str = ""
    code: str | None = None
    circuit: dict[str, Any] | None = None


@pytest.mark.parametrize(
    ("task_type", "submission"),
    [
        (TaskType.MULTIPLE_CHOICE, SubmissionStub(answer="B")),
        (TaskType.MULTIPLE_ANSWER, SubmissionStub(answer='["c", "a"]')),
        (
            TaskType.SHORT_ANSWER,
            SubmissionStub(answer="A Hadamard gate creates a superposition."),
        ),
        (
            TaskType.CODE_EXPLANATION,
            SubmissionStub(answer="Measurement turns the superposition into a classical result."),
        ),
        (TaskType.CODE_COMPLETION, SubmissionStub(code="circuit.h(0)")),
        (
            TaskType.QUANTUM_CIRCUIT,
            SubmissionStub(
                circuit={
                    "qubits": 1,
                    "operations": [{"gate": "h", "targets": [0]}],
                }
            ),
        ),
    ],
)
def test_default_registry_scaffolds_and_marks_each_required_type(
    task_type: TaskType,
    submission: SubmissionStub,
) -> None:
    registry = build_default_task_type_registry()

    scaffold = registry.scaffold(task_type, "Explain quantum superposition.")
    task = TaskStub(
        expected_answer=scaffold.expected_answer,
        marking_criteria=scaffold.marking_criteria,
    )

    assert registry.is_correct(task_type, task, submission) is True


class TrueFalseHandler:
    """A demonstration extension; built-in handler classes remain untouched."""

    def scaffold(self, outcome_statement: str) -> TaskScaffold:
        return TaskScaffold(
            expected_answer="true",
            marking_criteria={
                "statement": f"True or false: {outcome_statement}",
            },
        )

    def is_correct(self, task: TaskStub, submission: SubmissionStub) -> bool:
        return submission.answer.strip().casefold() == (task.expected_answer or "").casefold()


def test_developer_can_register_a_demonstration_type_without_changing_built_ins() -> None:
    registry = build_default_task_type_registry()
    existing_short_answer = registry.resolve(TaskType.SHORT_ANSWER)
    extension: TaskTypeHandler = TrueFalseHandler()

    registry.register("true_false", extension)

    scaffold = registry.scaffold("true_false", "A qubit can be in superposition.")
    task = TaskStub(scaffold.expected_answer, scaffold.marking_criteria)
    assert registry.is_correct("true_false", task, SubmissionStub(answer=" TRUE ")) is True
    assert registry.resolve(TaskType.SHORT_ANSWER) is existing_short_answer


def test_registry_rejects_duplicate_identifiers_without_replacing_a_handler() -> None:
    registry = TaskTypeRegistry()
    handler: TaskTypeHandler = TrueFalseHandler()
    registry.register("true_false", handler)

    with pytest.raises(TaskTypeRegistryError, match="already registered"):
        registry.register("true_false", handler)

    assert registry.resolve("true_false") is handler


def test_legacy_identifiers_delegate_to_the_matching_canonical_handler() -> None:
    registry = build_default_task_type_registry()

    assert registry.resolve(TaskType.QUIZ) is registry.resolve(TaskType.MULTIPLE_CHOICE)
    assert registry.resolve(TaskType.CODE) is registry.resolve(TaskType.CODE_COMPLETION)
    assert registry.resolve(TaskType.CIRCUIT) is registry.resolve(TaskType.QUANTUM_CIRCUIT)
