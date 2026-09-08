# Task 19: Learner corrections and scoped model history

## Outcome

Learners can now inspect their scoped evidence/model history and append a
protected annotation to one immutable evidence record or estimate. The course
educator can inspect the same scoped history and append an ordered,
append-only `ACCEPTED`, `REJECTED`, or `NEEDS_REVIEW` outcome. Neither command
can change evidence, prior estimates, or formal assessment history.

Accepted reviews are consumed only by a later controlled learner-model update.
That successor retains the original evidence relations, has a deterministic
identity that includes the accepted review set, links the review to the new
snapshot, and marks every affected dimension `NEEDS_REVIEW`. An evidence-target
review affects every current-head dimension linked to that evidence; an
estimate-target review affects its estimate's dimension. Pending and rejected
reviews remain visible but do not change a model snapshot.

The mounted API provides learner and educator timeline/read/write routes, all
with `Cache-Control: no-store`. The student and educator workspace components
render observations, estimates, annotations, reviews, and snapshot transitions
as separate semantic entries. Generated OpenAPI and frontend client contracts
are current.

## Verification

Completed on 2026-09-08:

- Backend focused corrections/evidence/model suite: `56 passed`.
- Migration and deployment suite: `38 passed`; `alembic heads` reports the
  sole head `20260908_0032`.
- Contract export and frontend-contract generation checks: passed.
- Backend Ruff check and format check: passed.
- Frontend Vitest: `66` files and `236` tests passed; lint and production build
  passed.
- Browser harness: `npm run test:e2e` completed successfully after allowing its
  local loopback server; it ran 72 Playwright checks. The first sandboxed run
  was `NOT RUN` because the sandbox prevents binding `127.0.0.1:4173`.
- Dedicated Task 19 browser journeys: learner history/annotation and educator
  stale-review draft retention passed in Chrome (`2 passed`).

The API exposes an opaque cursor whose page contains only the matching ordered
observation, inference, annotation, and review projections. The frontend uses
the generated timeline contract and supports loading subsequent pages. Educator
student rows link directly to a preselected learner-model review scope.

## Recovery boundary

Migration `20260908_0032` is additive from `20260907_0031`. It preserves
existing evidence, model snapshots, and assessment history. SQLite triggers
protect the three correction tables as append-only. Downgrade refuses while any
annotation, review, or review-to-snapshot link exists; production recovery is a
forward fix or a verified restore, not deletion of correction history.
