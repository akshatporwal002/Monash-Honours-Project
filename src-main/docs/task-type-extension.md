# Task-type extension interface

`backend/app/services/task_types.py` is the single extension boundary for deterministic LMS task
scaffolding and marking. Each implementation satisfies `TaskTypeHandler`:

```python
class TaskTypeHandler(Protocol):
    def scaffold(self, outcome_statement: str) -> TaskScaffold: ...

    def is_correct(
        self,
        task: TaskForMarking,
        submission: SubmissionForMarking,
    ) -> bool: ...
```

The registry owns dispatch. `LmsService` asks the registry to scaffold and mark a task; it does
not branch on individual task types. Consequently, adding a handler does not require changes to
the six existing handler implementations.

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
3. Add the new identifier to the API/persistence allow-list and add its UI renderer.
4. Add an independent test for a correct response, an incorrect response, and malformed input.

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
effort target. Full model/adaptation integration and independent verification remain open.
