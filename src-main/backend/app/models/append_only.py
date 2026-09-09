"""History guards for records whose corrections must be separate records."""

from sqlalchemy import DDL, event


def protect_history(model, *, unique_keys=()):
    table = model.__table__

    def reject_change(*_):
        raise ValueError(f"{table.name} history is immutable")

    event.listen(model, "before_update", reject_change)
    event.listen(model, "before_delete", reject_change)
    predicates = ["id = NEW.id"]
    predicates.extend(" AND ".join(f"{key} = NEW.{key}" for key in keys) for keys in unique_keys)
    statements = [
        f"CREATE TRIGGER IF NOT EXISTS {table.name}_no_{operation.lower()} "
        f"BEFORE {operation} ON {table.name} BEGIN "
        f"SELECT RAISE(ABORT, '{table.name} history is immutable'); END"
        for operation in ("UPDATE", "DELETE")
    ]
    statements.append(
        f"CREATE TRIGGER IF NOT EXISTS {table.name}_no_replace BEFORE INSERT ON {table.name} "
        f"WHEN EXISTS (SELECT 1 FROM {table.name} WHERE "
        + " OR ".join(f"({clause})" for clause in predicates)
        + f") BEGIN SELECT RAISE(ABORT, '{table.name} history is immutable'); END"
    )
    for statement in statements:
        event.listen(table, "after_create", DDL(statement).execute_if(dialect="sqlite"))
