"""SQLite guards for the exact task-review references in formal publications."""

from sqlalchemy import DDL, Table, event


def binding_guards() -> list[tuple[str, str, str]]:
    guards = []
    for table, check in (
        (
            "task_form_versions",
            "NEW.task_revision_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM task_revisions r WHERE r.id = NEW.task_revision_id AND r.course_id = NEW.course_id AND r.task_id = NEW.learning_task_id)",
        ),
        (
            "task_approvals",
            "NEW.task_review_event_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM task_review_events e JOIN task_form_versions f ON f.task_revision_id = e.task_revision_id WHERE e.id = NEW.task_review_event_id AND e.state = 'APPROVED' AND e.course_id = NEW.course_id AND f.id = NEW.task_form_version_id AND f.course_id = NEW.course_id AND f.assessment_definition_version_id = NEW.assessment_definition_version_id)",
        ),
    ):
        for action in ("INSERT", "UPDATE"):
            name = f"publication_{table}_scope_{action.lower()}"
            guards.append(
                (
                    table,
                    name,
                    f"CREATE TRIGGER IF NOT EXISTS {name} BEFORE {action} ON {table} WHEN {check} BEGIN SELECT RAISE(ABORT, 'Invalid publication review scope'); END",
                )
            )
    for table, column, condition in (
        (
            "task_form_versions",
            "task_revision_id",
            " AND (OLD.approval_state != 'DRAFT' OR NEW.approval_state != 'DRAFT')",
        ),
        ("task_approvals", "task_review_event_id", ""),
    ):
        name = f"publication_{table}_binding_immutable"
        guards.append(
            (
                table,
                name,
                f"CREATE TRIGGER IF NOT EXISTS {name} BEFORE UPDATE ON {table} WHEN NEW.{column} IS NOT OLD.{column}{condition} BEGIN SELECT RAISE(ABORT, 'Publication review bindings are immutable'); END",
            )
        )
    for table, unique in (
        ("task_form_versions", "task_form_id = NEW.task_form_id AND version = NEW.version"),
        (
            "task_approvals",
            "task_form_version_id = NEW.task_form_version_id AND approval_state = NEW.approval_state",
        ),
    ):
        name = f"publication_{table}_no_replace"
        guards.append(
            (
                table,
                name,
                f"CREATE TRIGGER IF NOT EXISTS {name} BEFORE INSERT ON {table} WHEN EXISTS (SELECT 1 FROM {table} WHERE id = NEW.id OR ({unique})) BEGIN SELECT RAISE(ABORT, 'Publication review bindings are immutable'); END",
            )
        )
    return guards


def install_binding_guards(form_table: Table, approval_table: Table) -> None:
    tables = {form_table.name: form_table, approval_table.name: approval_table}
    for table, _, statement in binding_guards():
        event.listen(tables[table], "after_create", DDL(statement).execute_if(dialect="sqlite"))
