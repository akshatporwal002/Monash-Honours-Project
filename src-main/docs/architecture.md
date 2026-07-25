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

Passwords are hashed and verified with Argon2id in `app.core.security`. Authentication
rules live in `app.services.authentication`, separately from the future HTTP routes.
Authentication returns the same failure result for unknown users, incorrect passwords,
and inactive accounts so callers do not expose account state.

Feature-specific folders will be added only when those features are implemented. Secrets
must be supplied through environment variables and must not be committed.
