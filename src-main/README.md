# QuantumLearn

QuantumLearn is a role-based learning management system for introductory quantum computing. The
MVP covers the complete learning loop: educators configure a course and generate grounded tasks,
students complete scaffolded activities and receive validated feedback, and administrators manage
accounts, courses, and runtime settings.

## What is included

- Student, educator, and administrator authentication with server-enforced role and course access.
- A React interface with role-specific workspaces:
  - students see their pathway, locked/in-progress/completed tasks, drafts, feedback, progress,
    recommendations, reminders, points, levels, and achievements;
  - educators get a dashboard, four-step course editor, student monitoring, bulk reminders, and
    analytics;
  - administrators manage users, courses, and system settings.
- Six task types: multiple choice, multiple answer, short answer, code explanation, code
  completion, and quantum circuit.
- Qiskit Aer circuit simulation, immutable submission attempts, grounded feedback generation,
  quality judging, one regeneration, and a safe fallback.
- Persistent SQLite models for the LMS, learning events, audit records, feedback workflows, and
  research measurements.

## Project structure

```text
backend/     FastAPI API, SQLAlchemy services, Alembic migrations, and tests
frontend/    React, TypeScript, and Vite application
docs/        Architecture, contracts, operations, and requirements traceability
```

## Prerequisites

- Python 3.11
- [uv](https://docs.astral.sh/uv/)
- Node.js 22
- npm 10 or newer
- Docker Engine with Docker Compose v2 (only for the packaged deployment)

## Run locally

Start the backend:

```powershell
cd backend
uv sync --frozen --all-extras
Copy-Item .env.example .env
uv run --frozen alembic upgrade head
uv run --frozen uvicorn app.main:app --reload --no-access-log
```

In another terminal, start the frontend:

```powershell
cd frontend
npm ci
Copy-Item .env.example .env
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to `http://127.0.0.1:8000`, so the default
`VITE_API_BASE_URL=/api/v1` works without another setting. Set `VITE_API_BASE_URL` to a different
API base URL when the frontend and API are deployed separately.

The development API documentation is at `http://localhost:8000/docs`. Liveness is
`GET /api/v1/health`; `GET /api/v1/ready` also checks the database, migration head, worker
heartbeat, and production configuration.

## Local demo

On the login page, choose Student, Educator, or Admin and select **Load demo workspace**. This
explicitly calls `POST /api/v1/admin/bootstrap-demo`, which is available only in non-production
environments and only from the loopback host. It creates an idempotent sample course and these
accounts:

| Role | Email | Password |
| --- | --- | --- |
| Student | `student@quantumlearn.demo` | `quantumlearn-demo` |
| Educator | `educator@quantumlearn.demo` | `quantumlearn-demo` |
| Administrator | `admin@quantumlearn.demo` | `quantumlearn-demo` |

There is no read endpoint that implicitly seeds demo data.

## AI and material configuration

The runnable local MVP is offline-first. If an external model and credentials are not configured,
task generation, feedback generation, and judging use deterministic local adapters. To use a
structured-output-compatible external service, configure the server-side `LLM_API_KEY`,
`LLM_MODEL`, `LLM_PROVIDER`, and `LLM_API_BASE_URL`; optional input/output cost rates are also
available. Administrators can change the active provider and model through the settings workspace.
Never put provider credentials in a `VITE_*` variable.

Educators can upload PDF, DOCX, and PPTX files, or fetch those formats from a public HTTPS link,
up to the configured 20 MB limit. Sources are stored locally, extracted, heading-aware chunked,
and indexed with the offline lexical index used by the MVP. Access to material content remains
authenticated and course-scoped. This runtime path needs no model download or separate vector
server.

## Background worker

The interactive MVP executes newly requested feedback in process. Run the serial database worker
for restart recovery and durable continuation jobs. Its built-in offline adapters recover feedback
without external services:

```powershell
cd backend
uv run --frozen quantumlearn-worker
```

The worker fails closed when its adapters are absent or invalid and uses a durable singleton lease,
so only one live worker owns the SQLite queues. Research baselines or external integrations can
replace the built-in factory through `WORKER_ADAPTER_FACTORY`. See
[Worker operations](docs/worker-operations.md) for that extension contract.

## Docker deployment

The committed Compose package runs the frontend, API, and recovery worker behind one nginx origin
with a persistent data volume. It includes separate local and hosted configurations, hardened
container defaults, production readiness checks, a hidden-prompt first-administrator command, and
a host-side smoke check. Follow [Deployment](docs/deployment.md); hosted TLS and DNS remain
host responsibilities.

## Verification

```powershell
cd backend
uv sync --frozen --all-extras
uv run --frozen pytest --cov=app.services --cov-report=term-missing --cov-fail-under=80
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen python scripts/export_openapi.py --check
uv run --frozen python scripts/generate_frontend_contracts.py --check

cd ..\frontend
npm ci
npm run lint
npm test
npm run build
npx playwright install chrome msedge firefox webkit
npm run test:e2e
npm audit --audit-level=high
npm audit --omit=dev --audit-level=high
```

## Documentation

- [Architecture](docs/architecture.md)
- [API contract](docs/api-contract.md)
- [Learning-event schema](docs/learning-event-schema.md)
- [Audit schema and privacy controls](docs/audit-schema.md)
- [Research methodology](docs/research-methodology.md)
- [Research export schema](docs/research-export-schema.md)
- [Task-type extension](docs/task-type-extension.md)
- [Worker operations](docs/worker-operations.md)
- [Deployment](docs/deployment.md)
- [Requirements traceability](docs/requirements-traceability.md)

Apply every Alembic migration before starting the API or worker. The committed OpenAPI and generated
frontend contracts are checked for drift in CI.
