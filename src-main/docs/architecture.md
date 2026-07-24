# Architecture notes

QuantumLearn starts as two independently runnable applications:

- `frontend`: the React user interface.
- `backend`: the FastAPI application programming interface (API).

The backend uses SQLAlchemy for database access. Request handlers receive a short-lived
session from `app.db.session.get_db`; models share the declarative base in
`app.db.base`. SQLite is the default MVP data store, while the database URL remains
configurable through the environment.

Schema changes are managed through Alembic migrations in `backend/migrations`. The
initial schema stores user accounts with student, educator, and administrator roles.
Only password hashes are persisted; plain-text passwords must never be stored.

Feature-specific folders will be added only when those features are implemented. Secrets
must be supplied through environment variables and must not be committed.
