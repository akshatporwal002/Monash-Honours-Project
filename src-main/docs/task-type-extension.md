# Task-type extension interface

`backend/app/services/task_types.py` is the registry boundary for deterministic practice-task
scaffolding and marking. Typed episode capture, generated source binding and formal assessment
criteria have additional contracts; a registry handler alone does not implement those paths.
Each registry implementation satisfies `TaskTypeHandler`:

```python
class TaskTypeHandler(Protocol):
    def scaffold(self, outcome_statement: str) -> TaskScaffold: ...

    def is_correct(
        self,
        task: TaskForMarking,
        submission: SubmissionForMarking,
    ) -> bool: ...
```

The registry owns handler dispatch. Existing handlers need not change when another handler is
registered. `LmsService` also enforces type-specific draft/submission and episode rules. Formal
assessment uses approved criterion evaluators and a versioned pass rule; a practice handler
returning `True` cannot confirm a formal result.

## Demonstration: add `true_false`

Create a handler and register it in the application composition root:

```python
from app.services.task_types import (
    TaskScaffold,
    build_default_task_type_registry,
)


class TrueFalseHandler:
    def scaffold(self, outcome_statement: str) -> TaskScaffold:
        return TaskScaffold(
            expected_answer="true",
            marking_criteria={
                "statement": f"True or false: {outcome_statement}",
            },
        )

    def is_correct(self, task, submission) -> bool:
        return submission.answer.strip().casefold() == (
            task.expected_answer or ""
        ).casefold()


task_types = build_default_task_type_registry()
task_types.register("true_false", TrueFalseHandler())
service = LmsService(session, task_type_registry=task_types)
```

`tests/test_task_type_registry.py` executes this demonstration and verifies that the registered
handler scaffolds and marks its task while the existing short-answer handler remains the same
object.

Identifiers exposed through the HTTP API are deliberately allow-listed by `TaskType`. To ship a
new identifier, add it to that enum and its database check constraint, then add the corresponding
frontend renderer. Those integration changes do not modify any existing task-type handler. A
duplicate identifier is rejected instead of silently replacing production behavior.

## Adding a production handler

1. Implement `TaskTypeHandler` in a new module.
2. Build the default registry, then call `register(identifier, handler)` during application
   composition.
3. Add the identifier to the API/persistence allow-list, typed definition/response validation,
   source-grounded generation and private/public projections, and an accessible UI renderer.
4. Define its assessment evidence contract where applicable; retain human review for semantic
   claims and keep expected answers/private anchors out of learner projections.
5. Cover draft/save/reload/revision, malformed input, source/version freeze, authorisation and
   evaluation. A new formal form requires explicit approval, not just handler registration.

Aliases can be registered with `register(..., aliases=(...))`. The MVP uses aliases only to read
the early `quiz`, `code`, and `circuit` identifiers; new work should use stable, descriptive
identifiers.

## Second-subject content using existing types

The [Task 40 conditional-programming module](../../docs/learnlens/task-40-conditional-programming.md)
demonstrates composition without adding a task identifier. The draft factories in
`backend/app/services/conditional_programming.py` configure existing multiple-choice
handlers and an `explanation` episode for tracing, correction and fresh transfer.
They use the ordinary LMS authoring contracts, episode evidence and proposed human
assessment criteria. No handler, engine, migration or renderer change is required.

`tests/test_conditional_programming.py` checks isolated course creation, marking,
publication controls, frozen episode/revision evidence and assessment reuse.
These synthetic checks do not approve the module's sources or verify the D-11
effort target. The integrated test now traverses both practice tasks, local feedback, durable
continuation, model snapshots, adaptation choices and assessed fresh transfer. Actual approved
module content, independent observation and measured per-contributor effort remain outstanding;
[the current integration receipt](../../docs/learnlens/integration-verification-2026-09-11.md)
identifies the source-specific CI evidence.

## Runtime types and permitted staging

`TaskType` includes matching, sequencing, prediction, reasoning, explanation, revision, reflection,
transfer, multiple choice, multiple answer, short answer, code explanation, code completion and
quantum circuit. Matching/sequencing use canonical structured definitions and responses. Episode
handlers retain typed evidence for criterion review; their refusal to guess correctness is not
an automatic INCOMPLETE result. Legacy code-fragment/keyword/gate-presence practice checks do not
prove program semantics, explanations or quantum state properties.

PD4 explicitly permits staged extension contracts. `state_comparison`, `diagnosis`,
`probability_interpretation`, `part_complete` and standalone `confidence` remain unregistered
runtime types. Their proposed authoring/response/evaluator boundaries are recorded in
[the staging table](../../docs/learnlens/multipart-generation-candidates.md#pd4-staging-and-extension-contracts)
and the current matrix. Related evidence inside an episode does not make those standalone forms
implemented. FR9's required runtime types do not inherit that staging exemption.
