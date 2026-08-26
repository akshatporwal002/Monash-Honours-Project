# 008: Extract `CourseScope` from `app/services/lms.py`

Status: proposed

Owner: unassigned

Created: 2026-08-26

Target branch: `arv-person-a-assessment`

Evidence snapshot: commit `96bffc1` (worktree clean at drafting time)

## Outcome

`app/services/lms.py` is 2,451 lines exposing 43 public methods to exactly one caller, with no test
entry point below HTTP. NFR9 requires every Section 8.2 module to have "a documented interface and
an independent test entry point"; the course and task scope rules have neither.

This plan extracts one module - `CourseScope` - and makes four collaborators injectable. It changes
no behaviour: every HTTP status code, audit event, learning event, and attempt-ordering guarantee
stays as it is. Three implementation steps.

The plan is deliberately narrow. An earlier draft also extracted the recommendation planner, the two
dashboard read models, and the submission decision. All three are coupled to numeric scores, and
plan 005 Step 3 (`docs/plans/005-remaining-feature-roadmap.md:119-122`) commits to removing "numeric
score, percentage, average, mastery, `passing_score`, and score-driven completion logic". Extracting
and pinning that logic with new tests before deleting it is wasted work, so it is deferred.

Outside this plan:

- **Recommendations, dashboards, and the submission decision.** Score-coupled at
  `app/services/lms.py:901-909`, `:852`, `:1152-1157`, and `:672-684`. These extractions belong
  inside plan 005 Step 3, as part of rewriting that logic rather than before it.
- **Lifting `_commit()` out to a unit of work.** `submit` acquires a writer lock at
  `app/services/lms.py:2204` and releases it through the terminal `_commit()` at `:2197`. Changing
  module shape and transaction boundary together would make any NFR17 regression unattributable to
  either. Deferred to its own plan.
- **Narrowing `upload_material`'s signature.** `FileStorage` is threaded through the public
  interface (`app/services/lms.py:1359-1366`) rather than the constructor, which is a real design
  flaw, but it has one adapter (`app/services/rag/storage.py:50`), tests already override it
  (`tests/test_lms_core_api.py:50`), and moving it is public-signature churn that buys no velocity.
- **Splitting the ~38 thin CRUD methods** into separate service files. They pass through to one
  query plus a scope check.
- The four behaviour findings in `docs/plans/009-lms-behaviour-findings.md`. This plan preserves
  each of those behaviours exactly and cites them where they touch a step.
- The `QuantumLearn` to `LearnLens` naming gap (CLAUDE.md: do not mass-rename).
- Any frontend change. No route path, request body, response body, or status code changes.

## Source evidence

| Claim or rule | Evidence | Requirement |
| --- | --- | --- |
| Every Section 8.2 module needs a documented interface and an independent test entry point | `docs/01-implementation-requirements.md:904` | NFR9 |
| Section 8.2 names "Courses, material, and outcomes" and "Tasks and activity state" as distinct module boundaries | `docs/01-implementation-requirements.md:733-751` | NFR9 |
| Backend service statement coverage must be at least 80 percent; lint, format, and static checks report zero errors | `docs/01-implementation-requirements.md:906-914` | NFR10 |
| Course scope and least privilege apply; operational logs exclude direct student IDs | `docs/01-implementation-requirements.md:938` | NFR16 |
| Concurrent submissions must create a consistent attempt order | `docs/01-implementation-requirements.md:942` | NFR17 |
| `403` for denied role or course scope; `404` without leaking whether another learner's record exists | `docs/02-pass-incomplete-bloom-assessment-spec.md:597-599` | Doc 02 section 13.3 |
| `LmsService` holds 43 public methods and 43 private helpers in one class | `app/services/lms.py:173-2235` | NFR9 |
| `LmsService` has exactly one production caller | `app/api/routes/lms.py:93`, `app/api/routes/lms.py:703` | NFR9 |
| Routes are 1:1 pass-throughs, so the service interface is the route table | `app/api/routes/lms.py:111-190` | NFR9 |
| No test entry point below HTTP: 3 direct `LmsService(...)` constructions across the suite versus 74 `client.` calls in one API test file | `tests/test_data_integrity.py:40`, `tests/test_data_integrity.py:77`, `tests/test_gamification.py:140`, `tests/test_lms_core_api.py` | NFR9 |
| Collaborators are constructed inside methods rather than accepted | `app/services/lms.py:183`, `:530`, `:638`, `:793`, `:1696`, `:2172-2178` | NFR9 |
| Scope rules distinguish absent (404) from exists-but-not-yours (403) | `app/services/lms.py:1503-1539` | Doc 02 section 13.3 |
| Load-or-404 helper call-site counts: `_get_module` 12, `_get_outcome` 5, `_get_task` 4, `_get_course` 3, `_get_user` 2 | counted over `app/services/lms.py` | - |
| `_require_student_task` depends on `_get_task`; `_require_course_read` depends on `_get_course` | `app/services/lms.py:1581`, `:1504` | - |
| The NFR17 guarantee is proved by one named concurrency test | `tests/test_data_integrity.py::test_concurrent_submissions_receive_one_consistent_attempt_sequence` | NFR17 |
| Baseline at `96bffc1`: `app.services` statement coverage 84.77 percent; `app/services/lms.py` 78 percent, 198 of 896 statements uncovered; 609 tests pass in 172 seconds | `uv run --frozen pytest --cov=app.services --cov-report=term-missing --cov-fail-under=80`, run 2026-08-26, exit code 0 | NFR10 |
| CI backend gate commands | `.github/workflows/quality.yml:52-78` | NFR10 |

The coverage baseline is the load-bearing measurement for this plan: the largest module in the
codebase is the one sitting below the project's own 80 percent gate, carried over the line by the
rest of the package. That is what "no independent test entry point" costs in practice.

## Current-state trace

Permission and scope resolution runs through five private helpers in `app/services/lms.py`:

| Helper | Line | Behaviour |
| --- | --- | --- |
| `_require_course_read` | `:1503` | administrator sees any course; owning educator sees own; enrolled student sees `PUBLISHED` only; otherwise `403` |
| `_require_course_owner` | `:1521` | non-educator or non-owner gets `403` |
| `_educator_courses` | `:1527` | filters to the educator's own courses; for a named id, exists-but-not-yours gives `403`, absent gives `404` |
| `_get_course` | `:1542` | load or `404` |
| `_require_student_task` | `:1580` | task with no `course_id` gives `404`, then delegates to `_require_course_read` |

Role branching is also inlined in `list_courses` (`app/services/lms.py:186-204`), which builds a
different `Select` per role rather than calling the helpers - so the same rule exists in two shapes.

Because all five are private, the 403/404 discipline required by Doc 02 section 13.3 holds only for
code inside this one file, and no test exercises any of them directly. Every proof of these rules
today runs through a `TestClient` fixture.

Collaborators are constructed rather than accepted: `GamificationService` in `__init__` (`:183`),
`AssessmentSubmissionService` inline at three call sites (`:638`, `:793`, `:1696`), the grounded
task-generation service inline (`:530`), and `HmacSha256Pseudonymizer` plus a module-level `settings`
read inline (`:2172-2178`). The last means the pseudonymisation path cannot be exercised without
process-level settings.

Gaps:

- `MISSING` - no test constructs any scope helper directly. NFR9's independent test entry point is
  unmet for the courses and tasks boundaries.
- Behaviour questions found while tracing this path are recorded in
  `docs/plans/009-lms-behaviour-findings.md`. None is addressed here.

## Proposed design

One new module, `app/services/course_scope.py`, holding `CourseScope`. Constructed from a `Session`
alone. Performs no writes, no flush, and no commit.

Interface, seven methods:

| Method | Replaces | Returns |
| --- | --- | --- |
| `visible_courses(actor)` | the role branching in `list_courses` (`:186-204`) | a `Select` |
| `readable_course(actor, course_id)` | `_require_course_read` | `Course` |
| `owned_course(educator, course_id)` | `_require_course_owner` | `Course` |
| `educator_courses(educator, course_id=None)` | `_educator_courses` | `list[Course]` |
| `student_task(student, task_id)` | `_require_student_task` | `LearningTask` |
| `course(course_id)` | `_get_course` | `Course` |
| `task(task_id)` | `_get_task` | `LearningTask` |

`visible_courses` returns a `Select` because `list_courses` already needs to compose ordering onto
it. The rest return loaded objects, mirroring today. No further query-shaped methods are added: a
`Select`-returning interface for the other five would be designed for a caller that does not exist,
and it would break the property that Step 1's tests pass unmodified through Step 2.

`course` and `task` are on the interface so the 404 rule for those two types lives in exactly one
place. `LmsService._get_course` and `_get_task` become one-line delegations.
`_get_module` (12 call sites), `_get_outcome` (5), and `_get_user` (2) stay in `LmsService`: modules,
outcomes, and users are not course-scope concepts.

`LmsService` keeps its 43 public methods and its single caller. It becomes the composition point: it
holds the collaborators, applies persistence, and owns the transaction.

Two invariants constrain every step:

- 403/404 discipline is behaviour, not detail. `CourseScope` must reproduce
  `app/services/lms.py:1503-1547` exactly, including the exists-but-not-yours split in
  `_educator_courses` and the `403` a student receives for a `DRAFT` course
  (`docs/plans/009-lms-behaviour-findings.md`, Finding 4).
- Nothing in `submit` moves. The writer lock at `:2204` and the terminal `_commit()` at `:2197` are
  untouched by every step here.

## Step 1: Write the characterisation tests before moving any code

Files:

- `src-main/backend/tests/test_lms_scope_rules.py` (new, temporary)

Changes:

- [ ] Construct `LmsService(session)` directly, with no `TestClient`, and assert the exact
      `LmsServiceError.status_code` for every scope path at `app/services/lms.py:1503-1547`.
- [ ] Cover: administrator reads any course; owning educator reads own course; non-owning educator
      gets `403`; enrolled student reads a `PUBLISHED` course; enrolled student gets `403` on a
      `DRAFT` course; unenrolled student gets `403`; absent course id gets `404`; `educator_courses`
      with a course owned by another educator gets `403` while an absent id gets `404`.
- [ ] Cover the task path: a task with no `course_id` gets `404`; a task in a course the student
      cannot read gets `403`.
- [ ] Cover `list_courses` per role, asserting which courses each role sees, so the inlined branching
      at `:186-204` is pinned before it is replaced by `visible_courses`.
- [ ] Assert status codes, not message text, so Step 2 can rephrase details without false failures.
- [ ] Add a module docstring stating that this file is scaffolding, deleted in Step 2, and naming
      `tests/test_course_scope.py` as its replacement.

Edge and failure cases:

- The `DRAFT`-course case asserts the current `403`. Doc 02 section 13.3 may require `404`; that
  question is Finding 4 in `docs/plans/009-lms-behaviour-findings.md` and is not decided here. Cite
  the finding in a comment on that assertion so nobody "fixes" it during Step 2.

**Acceptance:** `uv run --frozen pytest tests/test_lms_scope_rules.py` passes at commit `96bffc1`
with no production file changed. The Step 1 diff contains exactly one new test file.

## Step 2: Extract `CourseScope`, delegate to it, and delete the scaffolding

Files:

- `src-main/backend/app/services/course_scope.py` (new)
- `src-main/backend/app/services/lms.py`
- `src-main/backend/tests/test_course_scope.py` (new)
- `src-main/backend/tests/test_lms_scope_rules.py` (deleted in this step)

Changes:

- [ ] Add `CourseScope(session)` with the seven-method interface above, and a module docstring
      stating the invariants a caller must know: which role sees what, that denied scope raises `403`,
      that an absent record raises `404`, and that it performs no writes and no commit.
- [ ] Move the bodies of `_require_course_read`, `_require_course_owner`, `_educator_courses`,
      `_get_course`, and `_require_student_task` into it verbatim.
- [ ] Reduce `LmsService._require_course_read`, `_require_course_owner`, `_educator_courses`,
      `_get_course`, `_get_task`, and `_require_student_task` to one-line delegations, so the diff
      shows a move rather than a rewrite.
- [ ] Construct `CourseScope` once in `LmsService.__init__`.
- [ ] Replace the inlined role branching in `list_courses` (`:186-204`) with `visible_courses(actor)`,
      keeping the existing `order_by(Course.created_at.desc())` at the call site.
- [ ] Add `tests/test_course_scope.py`, constructing `CourseScope(session)` with nothing but a
      `Session`, covering every case Step 1 covered. This is the NFR9 independent test entry point.
- [ ] Delete `tests/test_lms_scope_rules.py` in the same commit, once `test_course_scope.py` is green.

Edge and failure cases:

- `_require_unlocked` (`app/services/lms.py:1587`) stays in `LmsService`. Prerequisite unlocking is
  the tasks-and-activity-state boundary, not course scope, and it raises `423`, not `403`.
- `_get_module`, `_get_outcome`, and `_get_user` stay in `LmsService`.
- `CourseScope` must not commit or flush. Any write left inside it is a review failure.
- `LmsServiceError` stays in `app/services/lms.py` and is imported by `course_scope.py`, or moves to
  a shared module if that import direction proves circular. Do not introduce a second error type: the
  route layer translates exactly one.

**Acceptance:** `tests/test_lms_scope_rules.py` passes unmodified immediately before its deletion,
`tests/test_course_scope.py` passes with no `TestClient` import, and both
`uv run --frozen python scripts/export_openapi.py --check` and
`uv run --frozen python scripts/generate_frontend_contracts.py --check` are green, proving no
contract moved.

## Step 3: Accept four collaborators instead of constructing them

Files:

- `src-main/backend/app/services/lms.py`
- `src-main/backend/app/api/routes/lms.py`

Changes:

- [ ] Accept `AssessmentSubmissionService` as a keyword-only constructor argument defaulting to
      today's construction, and use it at `:638`, `:793`, and `:1696`.
- [ ] Accept the grounded task-generation factory the same way, replacing the inline call at `:530`.
- [ ] Accept a clock callable defaulting to `lambda: datetime.now(UTC)`, and route the
      `datetime.now(UTC)` reads in reminder and dashboard paths through it.
- [ ] Move the `settings.learning_event_pseudonym_secret` read (`:2172-2178`) into `__init__` so the
      service can be constructed without process-level settings. Keep `HmacSha256Pseudonymizer` and
      change nothing about what is pseudonymised or logged.
- [ ] Leave `upload_material`'s `storage` parameter and the `get_lms_material_storage` dependency
      exactly as they are.

Edge and failure cases:

- Every new argument is keyword-only with a default reproducing today's construction, so no existing
  caller or test breaks and no route wiring changes.
- NFR16: moving the pseudonym-secret read must not change the pseudonym for a given learner. Add a
  test asserting the pseudonym for a fixed secret and learner id is unchanged.
- The clock change must not alter the seven-day engagement window or the 24-hour reminder window;
  those are behaviour, and Finding 1 in plan 009 depends on the reminder window staying as it is.

**Acceptance:** `uv run --frozen pytest` passes in full, and a new test constructs `LmsService` with
a fixed clock and a fixed pseudonym secret without touching process settings.

## Full verification

Per step, smallest check first, run in `src-main/backend`:

| Step | Check |
| --- | --- |
| 1 | `uv run --frozen pytest tests/test_lms_scope_rules.py` |
| 2 | `uv run --frozen pytest tests/test_course_scope.py tests/test_lms_core_api.py`, then `scripts/export_openapi.py --check` and `scripts/generate_frontend_contracts.py --check` |
| 3 | `uv run --frozen pytest` |

Release checks, from `.github/workflows/quality.yml:47-78` and `:112-132`:

- `uv run --frozen ruff check .`
- `uv run --frozen ruff format --check .`
- `uv run --frozen pytest --cov=app.services --cov-report=term-missing --cov-fail-under=80`
- `uv run --frozen pytest tests/test_migrations.py`
- `uv run --frozen python scripts/export_openapi.py --check`
- `uv run --frozen python scripts/generate_frontend_contracts.py --check`
- `npm run lint`, `npm test`, `npm run build`, `npm run test:e2e`

Coverage: the gate is the CI gate, `app.services` at or above 80 percent, currently 84.77 percent.
Raising `app/services/lms.py` above its current 78 percent is **not** an acceptance criterion for
any step. Step 1's tests will raise it as a side effect; report the number, do not tune tests to it.

`tests/test_migrations.py` and the two contract checks are negative controls. This plan changes no
schema and no contract, so a change in either means a step did something it promised not to do.

Frontend checks are listed because CI runs them, not because this plan changes frontend code.

Manual check that automation cannot prove: none identified.

## Migration and rollback

Not applicable. No model, schema, Alembic revision, stored column, enum value, or serialised payload
changes.

Rollback path: each step is an independent commit that moves code and adds tests. Reverting any
single step restores the prior module layout with no data consequence.

## Risks and controls

| Risk | Impact | Control and proof |
| --- | --- | --- |
| Extracting scope helpers turns a `403` into a `404` or the reverse | Doc 02 section 13.3 violation; scope disclosure under NFR16 | Step 1 writes characterisation tests before Step 2 moves any code; Step 2's acceptance requires them to pass unmodified immediately before deletion |
| Replacing the inlined role branching in `list_courses` changes which courses a role sees | Wrong course list per role; possible cross-course disclosure | Step 1 pins `list_courses` per role before Step 2 touches it |
| Deleting `test_lms_scope_rules.py` removes the safety net before its replacement is proven | A scope regression ships unnoticed | Deletion happens in the same commit as `test_course_scope.py`, after it is green; the two files cover the same case list |
| `course_scope.py` importing `LmsServiceError` from `lms.py` creates a circular import | Build failure, or an ad-hoc second error type with different status codes | Step 2 names the fallback explicitly: move the error to a shared module, never duplicate it |
| A collaborator default in Step 3 differs subtly from today's inline construction | Silent behaviour change in submission, task generation, or pseudonymisation | Every argument is keyword-only with a default reproducing today's call; full suite is Step 3's acceptance; a dedicated pseudonym-stability test is required |
| Scope creep back into recommendations, dashboards, `submit`, or `_commit` | An NFR17 or score-model regression becomes unattributable, and work is duplicated against plan 005 Step 3 | Those areas are named in "Outside this plan"; any diff touching `submit`, `_commit`, `_calculate_recommendations`, `student_dashboard`, or `educator_dashboard` is a review failure |
| Findings in plan 009 are "fixed" opportunistically during this refactor | Product policy set by an implementer, contrary to `.agents/instructions/core.md` | Step 1 requires an inline citation to Finding 4 on the `DRAFT` assertion; plan 009 proposes no fix |

## Missing-data report

| Item | Owner | Blocking effect |
| --- | --- | --- |
| NFR9 requires a "documented interface" but does not define the artefact. This plan uses a module docstring stating invariants, error modes, and write or commit behaviour. | Team | Non-blocking. A different artefact would be additive to Step 2. |
| Four behaviour questions found while tracing this path, including the `403`-versus-`404` scope-disclosure question | Recorded in `docs/plans/009-lms-behaviour-findings.md`, owners named there | Non-blocking. This plan preserves all four behaviours exactly. |
| Section 8.2 permits modules to "share a service in the MVP" (`docs/01-implementation-requirements.md:749-751`). Whether the existing HTTP tests already satisfy NFR9's "independent test entry point" is an interpretation this plan takes a position on rather than one the team has ruled on. | Team | Non-blocking. The concrete cost - five scope rules no test exercises directly, six inline collaborator constructions - stands regardless of the interpretation. |

## PR mapping

All three steps land as separate commits on `arv-person-a-assessment`, and a single pull request is
opened once Step 3 is complete. That PR must mirror every step, checklist item, and acceptance line,
and must record: each step's command output, the full release-check results from
`.github/workflows/quality.yml`, the before-and-after coverage numbers with the explicit note that
per-file coverage was not an acceptance criterion, every risk-control proof, and a pointer to
`docs/plans/009-lms-behaviour-findings.md` as work this PR deliberately did not do.

Independent test-judge, code-reviewer, and code-quality-reviewer verdicts are obtained once, against
the completed three-step diff. No step is complete on a passing build alone; a build proves only its
own scope.
