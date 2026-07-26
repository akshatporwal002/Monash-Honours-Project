# API contract

The committed machine-readable contract is [`contracts/openapi.json`](../contracts/openapi.json).
It is generated from the FastAPI application and checked for exact drift in CI:

```powershell
cd backend
uv run --frozen python scripts/export_openapi.py
uv run --frozen python scripts/export_openapi.py --check
uv run --frozen python scripts/generate_frontend_contracts.py
uv run --frozen python scripts/generate_frontend_contracts.py --check
```

The second generator produces `frontend/src/api/generated.ts`. Frontend feature contracts import
those generated component types and may narrow them only after runtime validation.

The default prefix is `/api/v1`. Every non-liveness response receives a validated or generated
UUID `X-Correlation-ID`, `Cache-Control: no-store` where private data may be returned, and the
configured security headers. Error responses are sanitized and do not include prompts, answers,
feedback/report content, direct identity, source chunks, credentials, or raw provider exceptions.

## Implemented routes

| Method and route | Purpose | Important behavior |
| --- | --- | --- |
| `GET /health` | Process liveness | Does not contact the database or an LLM. |
| `POST /submissions/{submission_id}/feedback` | Claim or replay feedback generation | `202` while processing, `200` for a durable terminal replay; returns `Location` and `Retry-After` when applicable. |
| `GET /submissions/{submission_id}/feedback` | Read authorized released feedback | Returns processing, validated, fallback, or sanitized retryable failure state; never judge internals or rejected attempts. |
| `POST /feedback/{feedback_uuid}/report` | Create or exactly replay a report | `201` for create, `200` for exact replay, `409` for conflicting reuse. |
| `POST /learning-events` | Record browser-originated task view/draft save | Authentication and course/task scope are server-derived; `201` for create and `200` for exact replay. |

Research export and analytics routes are enabled only with authorization-scoped repositories and
required production adapters. Their locked routes are:

- `GET /research/exports?format=csv|json`
- `GET /analytics/learning`
- `GET /analytics/research`
- `GET /analytics/filter-options`
- `GET /analytics/inactive-learners`

Analytics authorization scopes and filter-option arrays are bounded to 1,000 values. The inactive
learner endpoint is separately paginated with a maximum page size of 100 and returns the same
version/filter/generated-time/metric/missingness envelope as other analytics results.

## Authorization and mutation policy

Authentication, submission ownership, course authorization, CSRF validation, and per-actor rate
limits are injected policies. Missing production policies fail closed. Browser payloads never
choose actor/course identity or event time. Course filters are intersected with the caller's
authorized courses. Mutating routes accept bounded identifiers and payloads only.

The feedback `Location` header is generated from configured routing, not a hard-coded host.
Clients must honor `Retry-After`, cap polling, abort stale requests, and treat offline, timeout,
and abort states distinctly.
