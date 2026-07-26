"""Task-type extension boundary for deterministic LMS scaffolding and marking."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol

from app.models import TaskType
from app.services.quantum import (
    CircuitOperation,
    QuantumSimulationError,
    simulate_circuit,
)


class TaskForMarking(Protocol):
    expected_answer: str | None
    marking_criteria: dict[str, Any] | list[Any] | None


class SubmissionForMarking(Protocol):
    answer: str
    code: str | None
    circuit: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class TaskScaffold:
    expected_answer: str | None
    marking_criteria: dict[str, Any]
    starter_code: str | None = None


class TaskTypeHandler(Protocol):
    """The two operations a task type contributes to the LMS."""

    def scaffold(self, outcome_statement: str) -> TaskScaffold: ...

    def is_correct(
        self,
        task: TaskForMarking,
        submission: SubmissionForMarking,
    ) -> bool: ...


class TaskTypeRegistryError(ValueError):
    """Base error raised at the task-type extension boundary."""


class UnsupportedTaskTypeError(TaskTypeRegistryError):
    pass


class InvalidTaskSubmissionError(TaskTypeRegistryError):
    pass


TaskTypeIdentifier = str | Enum


class TaskTypeRegistry:
    """Maps stable task-type identifiers to independent implementations."""

    def __init__(self) -> None:
        self._handlers: dict[str, TaskTypeHandler] = {}

    def register(
        self,
        identifier: TaskTypeIdentifier,
        handler: TaskTypeHandler,
        *,
        aliases: tuple[TaskTypeIdentifier, ...] = (),
    ) -> None:
        keys = tuple(self._key(value) for value in (identifier, *aliases))
        duplicate = next((key for key in keys if key in self._handlers), None)
        if duplicate is not None:
            raise TaskTypeRegistryError(f"Task type is already registered: {duplicate}")
        for key in keys:
            self._handlers[key] = handler

    def resolve(self, identifier: TaskTypeIdentifier) -> TaskTypeHandler:
        key = self._key(identifier)
        try:
            return self._handlers[key]
        except KeyError as error:
            raise UnsupportedTaskTypeError(f"Unsupported task type: {key}") from error

    def scaffold(
        self,
        identifier: TaskTypeIdentifier,
        outcome_statement: str,
    ) -> TaskScaffold:
        return self.resolve(identifier).scaffold(outcome_statement)

    def is_correct(
        self,
        identifier: TaskTypeIdentifier,
        task: TaskForMarking,
        submission: SubmissionForMarking,
    ) -> bool:
        return self.resolve(identifier).is_correct(task, submission)

    @staticmethod
    def _key(identifier: TaskTypeIdentifier) -> str:
        raw = identifier.value if isinstance(identifier, Enum) else identifier
        key = str(raw).strip().casefold()
        if not key:
            raise TaskTypeRegistryError("Task type identifier cannot be empty")
        return key


def _criteria(task: TaskForMarking) -> dict[str, Any]:
    return task.marking_criteria if isinstance(task.marking_criteria, dict) else {}


def _answer_set(answer: str) -> set[str]:
    try:
        decoded = json.loads(answer)
    except (json.JSONDecodeError, TypeError):
        decoded = answer.replace(";", ",").split(",")
    if not isinstance(decoded, list):
        decoded = [decoded]
    return {str(value).strip().casefold() for value in decoded if str(value).strip()}


class MultipleChoiceHandler:
    def scaffold(self, outcome_statement: str) -> TaskScaffold:
        return TaskScaffold(
            expected_answer="b",
            marking_criteria={
                "choices": [
                    {"id": "a", "text": "A classical deterministic state only"},
                    {"id": "b", "text": outcome_statement},
                    {"id": "c", "text": "A circuit with no measurement"},
                ]
            },
        )

    def is_correct(
        self,
        task: TaskForMarking,
        submission: SubmissionForMarking,
    ) -> bool:
        return (submission.answer or "").strip().casefold() == (
            task.expected_answer or ""
        ).strip().casefold()


class MultipleAnswerHandler:
    def scaffold(self, outcome_statement: str) -> TaskScaffold:
        del outcome_statement
        return TaskScaffold(
            expected_answer='["a","c"]',
            marking_criteria={
                "choices": [
                    {"id": "a", "text": "Measurement produces a classical result."},
                    {"id": "b", "text": "Measurement preserves every amplitude."},
                    {"id": "c", "text": "Repeated shots estimate a distribution."},
                    {"id": "d", "text": "A qubit can never be measured."},
                ],
                "correct_answers": ["a", "c"],
            },
        )

    def is_correct(
        self,
        task: TaskForMarking,
        submission: SubmissionForMarking,
    ) -> bool:
        expected = {
            str(value).strip().casefold() for value in _criteria(task).get("correct_answers", [])
        }
        return bool(expected) and _answer_set(submission.answer) == expected


class ShortAnswerHandler:
    def scaffold(self, outcome_statement: str) -> TaskScaffold:
        del outcome_statement
        return TaskScaffold(
            expected_answer="hadamard",
            marking_criteria={"required_keywords": ["hadamard", "superposition"]},
        )

    def is_correct(
        self,
        task: TaskForMarking,
        submission: SubmissionForMarking,
    ) -> bool:
        content = (submission.answer or "").casefold()
        keywords = [str(value).casefold() for value in _criteria(task).get("required_keywords", [])]
        return (bool(keywords) and all(keyword in content for keyword in keywords)) or (
            bool(task.expected_answer) and task.expected_answer.casefold() in content
        )


class CodeExplanationHandler:
    def scaffold(self, outcome_statement: str) -> TaskScaffold:
        del outcome_statement
        return TaskScaffold(
            expected_answer="measurement",
            starter_code=(
                "from qiskit import QuantumCircuit\n\n"
                "circuit = QuantumCircuit(1, 1)\n"
                "circuit.h(0)\n"
                "circuit.measure(0, 0)\n"
            ),
            marking_criteria={"required_terms": ["measurement", "superposition"]},
        )

    def is_correct(
        self,
        task: TaskForMarking,
        submission: SubmissionForMarking,
    ) -> bool:
        content = (submission.answer or "").casefold()
        terms = [str(value).casefold() for value in _criteria(task).get("required_terms", [])]
        return bool(terms) and all(term in content for term in terms)


class CodeCompletionHandler:
    def scaffold(self, outcome_statement: str) -> TaskScaffold:
        del outcome_statement
        return TaskScaffold(
            expected_answer="circuit.h",
            starter_code=(
                "from qiskit import QuantumCircuit\n\n"
                "circuit = QuantumCircuit(1, 1)\n"
                "# Add the required gates here\n"
                "circuit.measure(0, 0)\n"
            ),
            marking_criteria={"required_code_fragments": ["circuit.h"]},
        )

    def is_correct(
        self,
        task: TaskForMarking,
        submission: SubmissionForMarking,
    ) -> bool:
        content = (submission.code or "").casefold()
        fragments = [
            str(value).casefold() for value in _criteria(task).get("required_code_fragments", [])
        ]
        if not fragments and task.expected_answer:
            fragments = [task.expected_answer.casefold()]
        return bool(fragments) and all(fragment in content for fragment in fragments)


class QuantumCircuitHandler:
    def scaffold(self, outcome_statement: str) -> TaskScaffold:
        del outcome_statement
        return TaskScaffold(
            expected_answer=None,
            marking_criteria={
                "required_gates": ["h"],
                "starter_circuit": {"qubits": 1, "operations": []},
            },
        )

    def is_correct(
        self,
        task: TaskForMarking,
        submission: SubmissionForMarking,
    ) -> bool:
        circuit = submission.circuit or {}
        operations = circuit.get("operations", [])
        if not isinstance(operations, list):
            raise InvalidTaskSubmissionError("The circuit payload is invalid.")
        try:
            typed_operations = [
                CircuitOperation(
                    gate=str(operation["gate"]),
                    targets=tuple(int(target) for target in operation["targets"]),
                )
                for operation in operations
                if isinstance(operation, dict)
            ]
            if len(typed_operations) != len(operations):
                raise ValueError
            simulate_circuit(
                qubits=int(circuit.get("qubits", 0)),
                operations=typed_operations,
                shots=int(circuit.get("shots", 1024)),
            )
        except (KeyError, TypeError, ValueError, QuantumSimulationError) as error:
            message = (
                str(error)
                if isinstance(error, QuantumSimulationError)
                else "The circuit payload is invalid."
            )
            raise InvalidTaskSubmissionError(message) from error
        gates = {
            str(operation.get("gate", "")).casefold()
            for operation in operations
            if isinstance(operation, dict)
        }
        required = {str(gate).casefold() for gate in _criteria(task).get("required_gates", [])}
        return bool(required) and required <= gates


def build_default_task_type_registry() -> TaskTypeRegistry:
    registry = TaskTypeRegistry()
    registry.register(
        TaskType.MULTIPLE_CHOICE,
        MultipleChoiceHandler(),
        aliases=(TaskType.QUIZ,),
    )
    registry.register(TaskType.MULTIPLE_ANSWER, MultipleAnswerHandler())
    registry.register(TaskType.SHORT_ANSWER, ShortAnswerHandler())
    registry.register(TaskType.CODE_EXPLANATION, CodeExplanationHandler())
    registry.register(
        TaskType.CODE_COMPLETION,
        CodeCompletionHandler(),
        aliases=(TaskType.CODE,),
    )
    registry.register(
        TaskType.QUANTUM_CIRCUIT,
        QuantumCircuitHandler(),
        aliases=(TaskType.CIRCUIT,),
    )
    return registry


DEFAULT_TASK_TYPE_REGISTRY = build_default_task_type_registry()
