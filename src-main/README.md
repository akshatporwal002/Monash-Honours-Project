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
- Choice, short-answer, code and circuit tasks, matching/sequencing, and typed prediction,
  reasoning, explanation, revision, reflection and fresh-transfer episodes. Five standalone
  PD4 forms remain [staged extensions](docs/task-type-extension.md#runtime-types-and-permitted-staging).
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

## Assessor setup and confirmation

Use an actual teaching account and approved course content. Demo records and generated drafts do
not supply course authority, educational validity or a study/AI release decision.

1. The course lead opens **Approve assessor eligibility**, selects the **Teaching account**, gives
   an **Access change reason** and selects **Approve teaching eligibility**. An administrator then
   opens **Manage assessor grants** for that course and selects **Grant assessor access**. These
   are separate records; eligibility alone is not a grant. Expiry, withdrawal or revocation removes
   access. The granted educator can use **Assessment setup** and **Assessment review** in navigation.
2. In the course editor, approve the actual source revision and inspect **Review saved tasks**.
   Select **Task to review**, inspect the prompt, private expected answer, source passages and
   support/transfer content. Save edits with **Save task revision** before reviewing. Complete
   **Generated content quality review** when required: all ten dimensions need explicit findings,
   reasons and the available evidence. Unverified/unmet dimensions block approval; structural
   validity is not factual accuracy. Give a **Review reason** and select **Approve task** (or
   **Request changes**). A later content change requires a new review.
3. Open **Assessment setup**. Select the assigned course, outcome and reviewed task, then supply
   the claim, Bloom process/knowledge dimension, evidence criteria and evaluator method. Use human
   judgement for reasoning; circuit rules establish only their explicitly approved properties.
   Select **Save assessment draft**. Complete the feedback/adaptation plan in the definition editor
   before approval; a generated assessment proposal opens the same saved-definition workflow.
4. Use **Edit an existing definition** and **Load definition** to reopen a saved definition.
   Inspect **Criteria and pass rule**, each stable criterion key, anchors/critical errors, evidence
   sources, task forms and tool/support/access conditions. Keep pass-rule keys aligned when changing
   criteria. **Save new draft version** preserves previous versions; a published version first needs
   **Create draft from this version**. Review the exact saved version, enter **Version approval
   reason**, tick the review acknowledgement and select **Approve saved version**. This is separate
   from teaching-task and course/pathway publication. Reload after a stale-version conflict; do
   not treat local edits as approved.
5. In **Assessment review**, select **Assigned course**. Under **Unresolved assessment attempts**,
   inspect the learner's frozen response, evidence, standard versions and anchors. Record each
   criterion decision and the required reason/evidence. **Apply frozen pass rule and confirm
   result** records the human decision when the server permits it. Existing review records expose
   **Confirm result**, **Override result**, **Void result**, **Withhold result** and **Return for
   review** subject to state and authority; consequential actions require a reason.
6. When sampling is configured, use **Assessment moderation** for selected attempts. Independent
   second/third reviews or correction resolution must finish before confirmation; reviewers must
   not replace the frozen standard or treat an AI suggestion as confirmation. No activated sampling
   policy leaves ordinary human confirmation available without claiming moderated acceptance.
   Reassessment uses **Authorise reassessment** with an approved fresh equivalent form, a private
   reason and a learner notice; earlier attempts and decisions remain intact.

Private expected answers/anchors belong in authorised authoring and review screens, not learner
content. See [definition editing](../docs/learnlens/assessor-definition-editor.md),
[approval alignment](../docs/learnlens/approval-alignment-contract.md) and
[moderation](../docs/learnlens/live-assessment-moderation.md). Any advisory AI activation requires
its separate validated release; none of these setup steps waive that gate.

## Learner results and requests for review

1. Open an available task from your course/pathway. For assessed work, select **Start assessed
   task** before editing: the application freezes the reviewed form and conditions. A locked task
   needs its prerequisite or educator action; refreshing cannot approve it.
2. Use **Save draft** while working and **Submit activity** when ready. Follow the task's required
   prediction, reasoning, simulation, revision/reflection and fresh-application stages. Approved
   conceptual help is available in supported work; fresh transfer withholds instructional help
   while retaining approved access arrangements. Submission preserves the original attempt.
3. Open the saved response in attempt history and read **Assessment result and review**. Use
   **Refresh result** to check progress. Before human release, the app shows workflow status and
   hides the provisional verdict. Feedback quality, points and activity completion are not a formal
   PASS. A released result is **PASS** or **INCOMPLETE**, with its outcome, Bloom target, criterion
   evidence, reason and next action; Bloom is not a numeric score.
4. Read **Evidence still needed** or **Evidence needs review** and follow the displayed next action.
   Technical faults do not establish that the learning criterion was missed. An authorised fresh
   reassessment is a new attempt under the approved rule; it does not erase the earlier response.
5. Where available, fill in **What would you like your assessor to review?** and select **Request
   assessor review**. A pending request appears as **Review requested** and prevents a duplicate
   open request. Return to see **Review resolved**, the **Assessor response**, and **Decision history**.
   Requesting review does not change the result automatically.

These procedures describe implemented controls. Actual assessor staffing, native assistive-technology
validation, approved content, load acceptance and hosted release evidence remain separate; see the
[current task ledger](../LearnLens_Remaining_Tasks.md).

## AI and material configuration

The runnable local MVP is offline-first. If an external model and credentials are not configured,
task generation, feedback generation, and judging use deterministic local adapters. To use a
structured-output-compatible external service, configure the server-side `LLM_API_KEY`,
`LLM_MODEL`, `LLM_PROVIDER`, and `LLM_API_BASE_URL`; optional input/output cost rates are also
available. Administrators can change the active provider and model through the settings workspace.
Never put provider credentials in a `VITE_*` variable.

Educators can upload PDF, DOCX, and PPTX files, or fetch those formats from a public HTTPS link,
up to the configured 20 MB limit. Sources are stored locally, extracted, heading-aware chunked,
and retrieved by the default offline `local_vector` backend. Its deterministic word-hash vectors
need no model download or separate vector server; optional `lexical` retrieval retains the same
course/source approval and scan gates. Stored material and historical passages remain scoped.
Generation and extraction do not themselves approve a source or teaching task.

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
