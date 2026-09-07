"""Database guards for immutable learner work and its response bindings."""

from sqlalchemy import DDL, MetaData, event


def work_guards() -> list[tuple[str, str, str]]:
    guards = []
    table = "assessment_work_starts"
    scope = """NOT EXISTS (
        SELECT 1 FROM task_form_versions f
        JOIN assessment_definition_versions d ON d.id = f.assessment_definition_version_id
        JOIN bloom_target_versions b ON b.assessment_definition_version_id = d.id
        JOIN pass_rule_versions r ON r.assessment_definition_version_id = d.id
        JOIN task_approvals a ON a.task_form_version_id = f.id
        WHERE f.id = NEW.task_form_version_id AND f.learning_task_id = NEW.task_id
        AND f.course_id = NEW.course_id AND d.id = NEW.assessment_definition_version_id
        AND b.id = NEW.bloom_target_version_id AND r.id = NEW.pass_rule_version_id
        AND a.id = NEW.task_approval_id AND a.assessment_definition_version_id = d.id
        AND f.approval_state = 'APPROVED' AND d.approval_state = 'APPROVED'
        AND a.approval_state = 'APPROVED' AND f.task_revision_id IS NOT NULL
        AND a.task_review_event_id IS NOT NULL)"""
    clauses = [
        (table, "scope", "INSERT", scope),
        (table, "no_update", "UPDATE", "1"),
        (table, "no_delete", "DELETE", "1"),
        (
            table,
            "no_replace",
            "INSERT",
            "EXISTS (SELECT 1 FROM assessment_work_starts WHERE id = NEW.id OR (student_id = NEW.student_id AND task_id = NEW.task_id))",
        ),
    ]
    for target in ("submission_drafts", "submission_attempts"):
        for action in ("INSERT", "UPDATE"):
            clauses.append(
                (
                    target,
                    "work_scope_" + action.lower(),
                    action,
                    "NEW.assessment_work_start_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM assessment_work_starts w WHERE w.id = NEW.assessment_work_start_id AND w.student_id = NEW.student_id AND w.task_id = NEW.task_id"
                    + (
                        " AND w.task_form_version_id = NEW.task_form_version_id AND EXISTS (SELECT 1 FROM submission_drafts d WHERE d.id = NEW.draft_id AND d.assessment_work_start_id = w.id)"
                        if target == "submission_attempts"
                        else ""
                    )
                    + ")",
                )
            )
        clauses.append(
            (
                target,
                "work_binding",
                "UPDATE",
                "OLD.assessment_work_start_id IS NOT NULL AND NEW.assessment_work_start_id IS NOT OLD.assessment_work_start_id",
            )
        )
        clauses.append(
            (
                target,
                "work_replace",
                "INSERT",
                f"EXISTS (SELECT 1 FROM {target} WHERE (id = NEW.id"
                + (
                    " OR (student_id = NEW.student_id AND task_id = NEW.task_id)"
                    if target == "submission_drafts"
                    else ""
                )
                + ") AND assessment_work_start_id IS NOT NULL)",
            )
        )
    for target, suffix, action, condition in clauses:
        name = f"{target}_{suffix}"
        guards.append(
            (
                target,
                name,
                f"CREATE TRIGGER IF NOT EXISTS {name} BEFORE {action} ON {target} WHEN {condition} BEGIN SELECT RAISE(ABORT, 'Assessment work history or scope is protected'); END",
            )
        )
    return guards


def install_work_guards(metadata: MetaData) -> None:
    for _, _, statement in work_guards():
        event.listen(metadata, "after_create", DDL(statement).execute_if(dialect="sqlite"))
