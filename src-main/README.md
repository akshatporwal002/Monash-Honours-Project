# QuantumLearn

QuantumLearn is a web-based learning management system for introductory quantum computing. This
worktree contains the Person 4 feedback, learning-event, research, analytics, export, and audit
modules behind fail-closed integration ports.

## Project structure

```text
backend/     FastAPI API, application services and tests
frontend/    React and TypeScript web application
docs/        Project and architecture notes
```

## Prerequisites

- Python 3.11
- [uv](https://docs.astral.sh/uv/)
- Node.js 22
- npm 10 or newer

## Run the backend

```powershell
cd backend
uv sync --frozen --extra dev
Copy-Item .env.example .env
uv run --frozen alembic upgrade head
uv run --frozen uvicorn app.main:app --reload --no-access-log
```

The API is available at `http://localhost:8000`. Interactive documentation is a development-only
facility and may be disabled by production settings. Keep Uvicorn access logging disabled: the
application emits sanitized request records using route templates, never raw request URLs.

## Run the database worker

In another terminal, configure the team-owned adapter factory and start the one SQLite worker:

```powershell
cd backend
$env:WORKER_ADAPTER_FACTORY="team_integration.worker:create_worker_adapters"
uv run --frozen quantumlearn-worker
```

The factory must return `app.worker.WorkerAdapters`. The command fails closed before claiming work
when the factory is absent or invalid. A durable ownership lease rejects a second live worker.

## Run the frontend

In a second terminal:

```powershell
cd frontend
npm ci
Copy-Item .env.example .env
npm run dev
```

The web application will be available at `http://localhost:5173`.

## Checks

```powershell
cd backend
uv sync --frozen --extra dev
uv run --frozen pytest
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen python scripts/export_openapi.py --check
uv run --frozen python scripts/generate_frontend_contracts.py --check

cd ..\frontend
npm ci
npm run lint
npm test
npm run build
npm run test:e2e
npm audit --audit-level=high
npm audit --omit=dev --audit-level=high
```

## Operations and contracts

- [Architecture](docs/architecture.md)
- [API contract](docs/api-contract.md)
- [Learning-event schema](docs/learning-event-schema.md)
- [Research measurement schema](docs/research-schema.md)
- [Research export schema](docs/research-export-schema.md)
- [Audit schema and privacy controls](docs/audit-schema.md)
- [Research methodology](docs/research-methodology.md)
- [Worker operations](docs/worker-operations.md)
- [Requirement traceability](docs/requirement-traceability.md)
- [Canonical implementation status](docs/person4-implementation-plan.md)

Apply every Alembic migration before starting the API or worker. `/api/v1/health` is liveness;
readiness additionally verifies database/migration/worker/secrets and required production adapters
without invoking an LLM.

## Current scope

The application now includes a responsive student learning experience connected to the FastAPI
backend. The demo student can open quiz, code, and circuit activities; save or submit work; run
quantum-circuit simulations; review feedback and progress; follow personalised recommendations;
and earn points and achievements. Notifications and an educator progress summary are also exposed
through the API.

Open `GET /api/v1/students/demo` in the API documentation to seed and inspect the demo experience.
The React client uses `http://localhost:8000/api/v1` by default; set `VITE_API_URL` to override it.

The application includes the provider-independent feedback pipeline, strict quality gate,
single-regeneration/fallback policy, fenced workflow recovery, learning events, paired research
measurements, metrics, audited exports, analytics APIs, append-only audits, and durable
research/continuation handoff. Attempts, evaluations, provider metadata, explicit usage
completeness, and costs are stored atomically and replayed idempotently. Authorized feedback
endpoints expose processing, validated, fallback, and retryable failure states without returning
rejected attempts or judge internals. Authentication, shared submission/task providers, production
LLM/retrieval/simulation adapters, consent eligibility, roster access, progress persistence, and
the team recommender must still be supplied by their owning workstreams; missing production
adapters fail closed.

The frontend includes isolated, route-ready `features/feedback` and `features/analytics` modules.
They are intentionally not mounted in the placeholder application until the team-owned task page,
router, and authorization shell are available.

Course materials can be uploaded or registered by HTTPS URL, extracted, chunked, embedded in a
local Chroma index, and retrieved with course-scoped source verification. Grounded retrieval is
available to feedback and task-generation services; production generation remains disabled until
a real model provider is configured.

Database schema changes are managed through Alembic. Shared course, task, submission and user
entities remain owned by their respective feature teams and are represented by external references
in the Person 4 tables until their canonical models are available.
