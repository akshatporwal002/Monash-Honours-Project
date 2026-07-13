# Architecture notes

QuantumLearn starts as two independently runnable applications:

- `frontend`: the React user interface.
- `backend`: the FastAPI application programming interface (API).

Feature-specific folders will be added only when those features are implemented. SQLite is the intended MVP data store. Secrets must be supplied through environment variables and must not be committed.

## Persistence foundation

The backend uses synchronous SQLAlchemy 2.x sessions and Alembic migrations. SQLite foreign-key
enforcement is enabled for application and migration connections. Application startup does not
create tables automatically; local and deployed databases must run `alembic upgrade head`.

Person 4 owns the `workflow_runs`, `feedback_records`, `judge_evaluations`, `learning_events`, and
`research_evaluations` tables. These records use UUIDv4 strings and UTC timestamps. Relationships
inside this group use restrictive foreign keys so evaluation evidence is not cascade-deleted.

Task, Submission, User, and Course tables are not yet available. Their identifiers are stored as
opaque external references rather than duplicating another feature team's models. A coordinated
future migration may add foreign keys after the canonical shared tables and deletion rules exist.

Learning events contain only pseudonymous user references and allow-listed metadata. They must not
store raw submitted answers, direct identities, prompts, credentials, provider keys, or tokens.
