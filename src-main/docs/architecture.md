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

## Feedback service boundary

The feedback pipeline is an async in-process application service. It depends on protocols for
submission lookup, context collection, feedback generation, feedback judging, and persistence.
This keeps external LLM, retrieval, simulation, and shared-domain implementations replaceable.

Block 2 stores a terminal workflow, its first feedback attempt, and its judge evaluation in one
transaction. Context or provider failures leave no partial workflow. Duplicate requests first
return the existing aggregate, while database uniqueness protects against concurrent duplicate
saves. Rejected feedback is retained but is not returned as validated student feedback.

The pipeline is not registered as an HTTP route and does not perform background work. Processing
status endpoints and background execution remain part of the later API integration block.

## Feedback agent

The Block 3 feedback agent builds a versioned `feedback-v1` request and depends on a structured LLM
client protocol rather than a provider SDK. Model output is validated against a strict schema before
it can enter the feedback pipeline. Incorrect feedback must identify the error and include an
improvement action, while citations are limited to retrieved source IDs and the supplied simulation
ID. The application injects the AI-generated notice; the model cannot author or replace it.

Prompts omit direct student, submission, course, workflow, retrieval-request, document, and chunk
identifiers. Student answers and retrieved text are explicitly treated as untrusted data. Client and
validation failures are converted to sanitized errors without logging prompt or output content.

Feedback records preserve provider, model, prompt version, simulation references, token usage, and
estimated cost. This keeps initial results and idempotent replays consistent and prepares the data
boundary needed by later research work. A concrete network-backed client remains a future adapter.
