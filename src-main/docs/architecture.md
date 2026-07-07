# Architecture notes

QuantumLearn starts as two independently runnable applications:

- `frontend`: the React user interface.
- `backend`: the FastAPI application programming interface (API).

Feature-specific folders will be added only when those features are implemented. SQLite is the intended MVP data store. Secrets must be supplied through environment variables and must not be committed.
