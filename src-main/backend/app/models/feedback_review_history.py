"""Protect receipt-bearing judgements and the exact feedback they reviewed."""

from sqlalchemy import DDL, event


def feedback_review_guards() -> tuple[str, ...]:
    statements = []
    for operation in ("UPDATE", "DELETE"):
        statements.append(
            f"CREATE TRIGGER IF NOT EXISTS feedback_review_judge_no_{operation.lower()} "
            f"BEFORE {operation} ON judge_evaluations WHEN "
            + (
                "OLD.quality_review IS NOT NULL OR NEW.quality_review IS NOT NULL "
                if operation == "UPDATE"
                else "OLD.quality_review IS NOT NULL "
            )
            + "BEGIN SELECT RAISE(ABORT, 'Feedback review history is immutable'); END"
        )
        statements.append(
            f"CREATE TRIGGER IF NOT EXISTS feedback_review_output_no_{operation.lower()} "
            f"BEFORE {operation} ON feedback_records WHEN EXISTS "
            "(SELECT 1 FROM judge_evaluations WHERE feedback_id=OLD.id AND quality_review IS NOT NULL) "
            "BEGIN SELECT RAISE(ABORT, 'Reviewed feedback history is immutable'); END"
        )
    statements.extend(
        (
            "CREATE TRIGGER IF NOT EXISTS feedback_review_judge_no_replace "
            "BEFORE INSERT ON judge_evaluations WHEN EXISTS (SELECT 1 FROM judge_evaluations "
            "WHERE (id=NEW.id OR feedback_id=NEW.feedback_id) AND quality_review IS NOT NULL) "
            "BEGIN SELECT RAISE(ABORT, 'Feedback review history is immutable'); END",
            "CREATE TRIGGER IF NOT EXISTS feedback_review_output_no_replace "
            "BEFORE INSERT ON feedback_records WHEN EXISTS (SELECT 1 FROM feedback_records f "
            "JOIN judge_evaluations j ON j.feedback_id=f.id WHERE j.quality_review IS NOT NULL "
            "AND (f.id=NEW.id OR (f.workflow_run_id=NEW.workflow_run_id AND "
            "(f.generation_attempt=NEW.generation_attempt OR "
            "(f.status IN ('accepted','safe_fallback') AND NEW.status IN ('accepted','safe_fallback')))))) "
            "BEGIN SELECT RAISE(ABORT, 'Reviewed feedback history is immutable'); END",
            "CREATE TRIGGER IF NOT EXISTS feedback_review_subject_scope "
            "BEFORE INSERT ON judge_evaluations WHEN NEW.quality_review IS NOT NULL "
            "AND json_extract(NEW.quality_review,'$.schema_version')='category-review.v1' "
            "AND NOT EXISTS (SELECT 1 FROM feedback_records f WHERE f.id=NEW.feedback_id "
            "AND f.submission_id=json_extract(NEW.quality_review,'$.subject_id')) "
            "BEGIN SELECT RAISE(ABORT, 'Feedback review submission differs'); END",
        )
    )
    return tuple(statements)


def install_feedback_review_guards(table):
    for statement in feedback_review_guards():
        event.listen(table, "after_create", DDL(statement).execute_if(dialect="sqlite"))
