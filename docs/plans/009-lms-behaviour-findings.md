# 009: Behaviour findings in the shared LMS service

Status: diagnostic only, no implementation proposed

Owner: unassigned; each finding names the decision owner it needs

Created: 2026-08-26

Target branch: `arv-person-a-assessment`

Evidence snapshot: commit `96bffc1`

## Outcome

Record four behaviour questions found in `app/services/lms.py` while drafting plan 008. None is a
refactor. Each needs a product or policy decision before any code changes, and three of the four
fall inside territory that plan 005 Step 3 (`docs/plans/005-remaining-feature-roadmap.md:109-133`)
already claims.

This plan proposes **no fix**. `.agents/instructions/core.md` forbids using implementation to
discover an unstated product rule, and the decisions below are unstated. The purpose of this file
is that the findings survive past the conversation that produced them, with evidence attached.

Outside this plan: any code change, any migration, any acceptance test. Plan 008 does not depend on
this plan and must not be blocked by it; plan 008 records current behaviour as its baseline and
cites the findings here.

## Source evidence

| Claim or rule | Evidence | Requirement |
| --- | --- | --- |
| Learner results are only `PASS` or `INCOMPLETE`; no numeric formal grades | `docs/01-implementation-requirements.md:17-32`; `docs/02-pass-incomplete-bloom-assessment-spec.md:11-24` | AC19, AT1-AT3 |
| Numeric score, percentage, average, mastery, and `passing_score` are to be removed from formal assessment paths | `docs/plans/005-remaining-feature-roadmap.md:119-122` | FR12, FR21, AT1-AT3, AT19, AT20 |
| Shared LMS paths still retain score-oriented writes and projections | `docs/plans/005-remaining-feature-roadmap.md:39-41` | AC19 |
| Plan 005 Step 2 is `BLOCKED` pending approved values for D-01 and D-06, and Steps 2 and 3 must ship together | `docs/plans/005-remaining-feature-roadmap.md:5-6`, `:249` | - |
| `403` for denied role or course scope; `404` without leaking whether another learner's record exists | `docs/02-pass-incomplete-bloom-assessment-spec.md:597-599` | Doc 02 section 13.3 |
| Course scope, least privilege, and minimal disclosure apply | `docs/01-implementation-requirements.md:938` | NFR16 |
| Evidence, inference, activity state, formal results, and research data stay distinct | `CLAUDE.md` hard rules; `docs/01-implementation-requirements.md:17-32` | AC19 |

## Finding 1: a read endpoint writes and commits

`LmsService.student_dashboard` is reached by `GET /dashboard/student`. Its second statement calls
`_create_overdue_reminders` (`app/services/lms.py:800`), which creates `Reminder` rows and commits
them (`app/services/lms.py:1832-1862`). Deduplication is a query for any reminder for the same
student and task created within the last 24 hours (`app/services/lms.py:1874-1881`), plus a
`dedupe_window` string derived from the day number (`:1886`). There is no database constraint
enforcing the window.

Observed consequences:

- A `GET` has a write side effect, so it is not safely repeatable. Two dashboard loads racing inside
  the same 24-hour window can both read no existing reminder and both insert, because the guard is a
  read-then-write with no unique constraint behind it. `UNVERIFIED` - no test exercises concurrent
  dashboard loads; the concurrency proof at
  `tests/test_data_integrity.py::test_concurrent_submissions_receive_one_consistent_attempt_sequence`
  covers submissions only.
- Reminder creation is gated on the `reminders_enabled` setting (`:1833`, `:1873`), so the write is
  configuration-dependent as well as request-dependent.

Decision needed: may a read endpoint create learner-visible records, or should overdue reminders be
produced by a scheduled job or by the submission path? If they stay on the read path, does the
24-hour window need a database constraint rather than a query guard?

Owner: product owner, with data-integrity input for the constraint question.

Blocking effect: none on plan 008, which leaves this call exactly where it is. Blocks any claim
that dashboard reads are side-effect free.

## Finding 2: unguarded numeric score in educator dashboard aggregation

`LmsService.educator_dashboard` buckets attempts by task type and by learning outcome using
`attempt.score` directly, with no null check (`app/services/lms.py:1152-1157`):

- `by_type[task.task_type.value].append(attempt.score)`
- `by_outcome[task.learning_outcome_id].append(attempt.score)`

`SubmissionAttempt.score` is set to `None` for assessed tasks. `LmsService.submit` computes
`score, _ = self._grade(task, payload) if frozen_versions is None else (None, "")`
(`app/services/lms.py:672`), so every submission against a task with frozen assessment versions
stores a null score.

`UNVERIFIED` - whether the aggregation raises, silently produces a wrong average, or is unreachable
in practice has not been run. The behaviour depends on what the downstream `LabelScoreRead`
construction does with a list containing `None`. No existing test seeds an assessed attempt and then
loads the educator dashboard.

Decision needed: none at product level, most likely. This is probably a defect. It is recorded here
rather than fixed because confirming it needs a test that seeds an assessed attempt, and because
plan 005 Step 3 may delete the aggregation outright.

Owner: implementer, once plan 005 Step 3's fate is known.

Blocking effect: none on plan 008. Blocks any claim that the educator dashboard is correct for
courses containing assessed tasks.

## Finding 3: learner-facing percentage average in recommendation text

`LmsService._calculate_recommendations` aggregates `attempt.score` per learning outcome
(`app/services/lms.py:901-909`), picks the outcome with the lowest average, and builds a
learner-visible `RecommendationRead.reason` string (`app/services/lms.py:929-933`):

```
f"Your {average}% average for "
f"“{outcome.title if outcome else 'this outcome'}” "
"is your lowest-performing learning outcome."
```

This is adaptation output, not a formal assessment result, so it does not by itself breach the
`PASS` / `INCOMPLETE` rule. Two separate questions arise:

- It presents a numeric percentage average to a learner. `docs/plans/005-remaining-feature-roadmap.md:121`
  lists percentage and average presentation for removal, and `:39-41` already flags shared LMS paths
  as retaining score-oriented projections.
- The phrasing is deficit-framed and ranks the learner's own outcomes ("lowest-performing").
  Whether adaptation text may characterise a learner this way is a separate product question from
  whether it may show a number.

Decision needed: what a recommendation reason may say once numeric averages are removed. A
replacement string cannot be invented during a refactor without setting product policy.

Owner: product owner. Overlaps plan 005 Step 3, which is blocked behind D-01 and D-06.

Blocking effect: none on plan 008, which no longer touches recommendations. This finding is the
reason plan 008 stopped touching them.

## Finding 4: `403` where Doc 02 section 13.3 may require `404`

`CourseScope`'s current behaviour, in `LmsService._require_course_read`
(`app/services/lms.py:1503-1520`), returns `403` in every denied case:

- A student enrolled in a course whose state is not `PUBLISHED` gets `403` (`:1509-1517` falls
  through to `:1520`).
- A student not enrolled in an existing course gets `403`.
- A non-owning educator gets `403` (`:1521-1526`).
- An absent course id gets `404` from `_get_course` (`:1542-1547`).

`_educator_courses` makes the distinction explicit: a course that exists but belongs to another
educator gives `403`, an absent id gives `404` (`:1534-1538`).

`docs/02-pass-incomplete-bloom-assessment-spec.md:597-599` states: use `403` for denied role or
course scope, and `404` "without leaking whether another learner's record exists." The two rules
are in tension for the case of a record that exists but is outside the requester's scope. The
current code answers "403 for scope" consistently; a stricter reading of the second rule would
answer `404` for anything the requester may not see, so that the response does not confirm the
record exists.

`UNVERIFIED` - which reading the specification intends. The two sentences are adjacent in the same
list and are not reconciled there.

Decision needed: for a student requesting a course they cannot see, is the correct response `403`
(current) or `404` (non-disclosing)? The same answer should then apply to tasks, modules, and
outcomes.

Owner: product owner, with assessor-policy input. This is an NFR16 disclosure question, not a
cosmetic one.

Blocking effect: none on plan 008. Plan 008 Step 1 asserts the current `403` as its
characterisation baseline and cites this finding; plan 008 Step 2 must preserve it exactly. If the
decision lands on `404`, that is a behaviour change needing its own plan, and plan 008's tests are
the thing that will make it a one-place edit.

## Full verification

Not applicable. This plan changes nothing and asserts nothing that a test could close. Every
current-state claim above cites `path:line` at commit `96bffc1`; every claim that would need a run
to confirm is marked `UNVERIFIED`.

## Migration and rollback

Not applicable. No code, schema, or data change.

## Risks and controls

| Risk | Impact | Control and proof |
| --- | --- | --- |
| A finding here is treated as an approved change and implemented during a refactor | Product policy set by an implementer, contrary to `.agents/instructions/core.md` | This plan proposes no fix and names a decision owner per finding; plan 008 explicitly preserves current behaviour |
| Findings 1-3 are forgotten because plan 005 Step 3 stays blocked on D-01 and D-06 | Known defects and a live numeric-presentation question persist unowned | This file exists so the evidence outlives the drafting conversation; a pointer belongs in plan 005 Step 3 whenever that plan is next revised |
| Finding 4 is resolved as `404` after plan 008 has shipped | A scope behaviour change across course, task, module, and outcome paths | Plan 008 Step 2 concentrates the rule in one module, so the change is a single-file edit with existing direct tests |

## Missing-data report

| Item | Owner | Blocking effect |
| --- | --- | --- |
| May a read endpoint create learner-visible records? Finding 1. | Product owner | Blocks any side-effect-free claim for dashboard reads |
| Does the reminder 24-hour window need a database constraint? Finding 1. | Data-integrity owner | Blocks a concurrency claim for reminder creation |
| Does `educator_dashboard` raise or silently mis-aggregate for a null score? Finding 2. | Implementer | `UNVERIFIED`; needs a test seeding an assessed attempt |
| What may a recommendation reason say once numeric averages are removed? Finding 3. | Product owner | Blocked behind plan 005 D-01 and D-06 |
| `403` or `404` for an existing record outside the requester's scope? Finding 4. | Product owner, assessor policy | Blocks any NFR16 non-disclosure claim |

## PR mapping

This plan carries no implementation, so it maps to no PR of its own. It is referenced by plan 008,
and a pointer to it belongs in plan 005 Step 3 the next time that plan is revised. Editing plan 005
is a change to an approved plan and needs its owner's agreement; it has not been made.
