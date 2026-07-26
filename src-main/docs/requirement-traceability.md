# Requirement traceability

This matrix maps the Person 4 brief to implementation surfaces and release evidence. A row is
release-complete only when its referenced automated checks pass in the locked CI environment.

| Requirements | Capability | Primary implementation/evidence |
| --- | --- | --- |
| FR15, FR28, NFR9 | Idempotent feedback orchestration and persistence | `app/services/feedback`, workflow repository, pipeline/application/API tests |
| FR16, NFR12, NFR13, NFR21 | Structured generation, retrieval/simulation grounding, sanitized failures | feedback agent/context contracts and tests |
| FR17, FR18, NFR14, NFR23 | Versioned quality policy, one regeneration, safe fallback | quality judge/pipeline tests and aggregate constraints |
| FR15–FR18, NFR7, NFR21 | Authorized feedback states, reports, accessible route-ready UI | feedback API and frontend feature tests |
| FR20, NFR16, NFR20 | Privacy-safe learning events and metrics | learning-event schemas/services/API tests, metrics tests |
| FR20, NFR12–NFR14, NFR22, NFR25 | Paired research pipeline and cost/latency measurement | research case/baseline repository/worker tests |
| NFR16, NFR25, AC10 | Auditability, privacy, secure export | audit, privacy/security, export tests |
| NFR16, NFR20, NFR21 | Aggregate learning/research analytics | metrics/API tests and route-ready analytics UI |
| FR28, AC4, AC6, AC8, AC10 | End-to-end continuation and release integration | deterministic adapter E2E harness and browser checks |

## Required E2E scenarios

| # | Scenario | Release evidence |
| --- | --- | --- |
| 1 | Correct multiple-choice answer | First-pass validated feedback and continuation assertions |
| 2 | Incorrect short answer | Grounded improvement action and learning events |
| 3 | Code explanation with retrieved documentation | Source attribution and no chunk leakage |
| 4 | Quantum circuit response with simulation | Simulation reference/status and scoped prompt |
| 5 | Judge rejection then successful regeneration | Two attempts, one release, fenced terminal state |
| 6 | Two judge failures then fallback | Safe fallback and fallback audit |
| 7 | External LLM timeout | Bounded call, sanitized retry/failure, no raw exception |
| 8 | Missing retrieval | Typed not-configured/empty result handling |
| 9 | Simulation failure | Typed failure, safe response, no raw error |
| 10 | Export after completion | Eligible pair, authorization, fail-closed audit, privacy sentinels |

The integration harness must additionally cover authorization denial, reporting, one feedback-view
event, baseline isolation, dashboards, worker restart, stale-token fencing, progress idempotency,
next-task handoff, and database/log/API/export privacy sentinels. Real provider access is forbidden
in all automated tests.
