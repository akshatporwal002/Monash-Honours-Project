# Task 20: Learner preferences

Status: implemented and locally verified in `feat/task-20-learner-preferences`; uncommitted.
Worktree: `.tmp-coordinator/task20`. Base: `65a9457d27e849465e7f227471336552bb22b8b4`, verified after fetching origin.
No commit, push, pull request, merge, hosted deployment, or Task 21 work is included.
The original untracked implementation handoff remains in the main worktree.

## What now works

Learners can inspect, save, correct, and reset explicit choices from their dashboard or task workspace.
The server restores choices after reload and a new authenticated session.
The editor shows the saved version, unsaved changes, recoverable errors, and earlier revisions.
Disabling personalisation retains requested choices and restores baseline presentation.

The supported effects are deliberately bounded:

| Choice | Workspace effect | Limit |
| --- | --- | --- |
| Pace | Optional links through task, response, and saved work | No deadlines or task order change |
| Support format | Optional guidance as text or a stepwise list | The approved response form stays fixed |
| Explanation detail | Brief or detailed optional workspace guidance | Approved feedback content is not rewritten |
| Breaks | Explicit save-draft and break control | Save failure keeps the draft; deadlines do not pause |
| Repeat practice | New local draft after checking current practice permission | Excludes formal tasks, episodes, locked tasks, and disabled resubmission |
| Support amount | Show approved hint controls or open them on request | Unlimited approved hints remain available; access support stays separate |
| Feedback form | Inline or expandable explanation from the same saved feedback | Summary, assessed details, sources, actions, and reporting stay available |
| Personalisation | Turn optional preference effects off | Baseline learning, required feedback, reflection, and approved access support remain available |

Repeat practice does not submit an assessment or create a formal reassessment.
The existing submission service still checks task permission when work is submitted.
A learner must save a dirty draft before starting another practice draft.
Fresh application suppresses optional instructional guidance and repeat practice.
The server derives that stage from saved episode state and frozen work, never a request flag.

## Interfaces and ownership

The settings are global per learner because all current consumers are workspace presentation controls.
Course conditions still determine which settings can take effect for a task.
`LearnerPreferenceService.read` supplies a small typed interface for future consumers.
`LmsService.effective_preferences` resolves approved task and stage limits without creating task-view evidence.

| Endpoint | Contract |
| --- | --- |
| `GET /api/v1/learner-preferences/me` | `PreferenceRead`: version and requested values |
| `PUT /api/v1/learner-preferences/me` | `PreferenceUpdate`: expected version, request key, full values |
| `POST /api/v1/learner-preferences/me/reset` | `PreferenceReset`: expected version and request key |
| `GET /api/v1/learner-preferences/me/history` | Bounded revision pages with limit and offset |
| `GET /api/v1/learner-preferences/me/tasks/{task_id}/effective` | Requested values, effective values, version, stage, practice permission, and limitations |

Defaults are self-paced overview, text, brief guidance, no break or repeat prompts, enabled personalisation,
visible approved hint controls, and inline feedback explanation.
Opt-out uses those baseline presentation values while reporting `personalisation_enabled=false`.
Reset appends the defaults as a new revision. It never deletes earlier choices.

Identity comes from the authenticated active learner. No endpoint accepts another learner's identifier.
Task-effective reads also enforce existing course and task access.
Write requests use the existing CSRF guard and a 60-request-per-minute technical rate limit.
Unknown fields, sensitive profile fields, unsupported choices, and unexpected query fields are rejected.
Preference responses use `Cache-Control: no-store`.

The current version starts at zero. Each successful action appends one unique learner/version record.
An exact request replay returns its original receipt, including a competing identical request.
A reused request key with different content or a stale version returns 409.
The editor keeps its draft and requires an explicit saved-version refresh before retrying a conflict.
Retryable errors retain both the draft and its request key.
The browser test also drops a response after the real server commits, then recovers that receipt on retry.

These records describe explicit choices only. They are separate from learning evidence and inferred model snapshots.
Global settings changes have no invented course, outcome, response, or ability claim.
Existing task actions continue through their established evidence services.
Preferences cannot alter frozen work, criteria, formal decisions, source release, consent, or Task 19 corrections.
Task 35 operational AI assessment remains disabled.

## Storage and recovery

Migration `20260908_0033` adds `learner_preference_revisions` after `20260908_0032`.
There is no backfill and no destructive change to protected history.
Typed database checks and unique keys constrain saved choices and revision order.
SQLite triggers reject updates, deletes, replacement inserts, and non-successor revisions.
ORM updates and deletes are also rejected.
Migration replay preserves existing records and restores missing guards after interrupted DDL.
Populated history blocks downgrade before destructive work.
Use a forward fix or a verified pre-upgrade restore for recovery; never erase choice history to roll back code.

## Verification

The implementation tests are:

- `backend/tests/test_learner_preferences.py`: persistence across sessions, all choices, reset/history,
  strict fields, active owner scope, stale writes, exact replay, concurrent saves, rollback, CSRF,
  authenticated session renewal, frozen-stage limits, unchanged evidence/model/decision records, and migration protection.
- `frontend/src/test/LearnerPreferences.test.tsx`: draft retention, request replay, explicit conflict refresh,
  keyboard controls, Axe, effective effects, opt-out baseline, and separate access support.
- `frontend/src/features/feedback/FeedbackPanel.test.tsx`: expandable explanation preserves required feedback and sources.
- `frontend/e2e/learner-preferences.e2e.ts`: ordinary mounted preferences, persistence, and opt-out in all four CI browsers.
- `frontend/e2e/task20-preferences.local.mjs`: real authenticated UI-to-API journey with all choices,
  new sign-in, saved reflection, break save, correction, reset history, competing sessions,
  committed response loss, permitted repeat practice, keyboard, Axe, and 390-pixel reflow.

Completed checks:

- Final full frontend suite: 242 passed across 67 files. The focused workspace/feedback suite also passed 23 tests.
- Frontend lint and production build: passed. The existing bundle-size warning remains.
- Existing browser suite: 80 passed across Chrome, Edge, Firefox, and WebKit.
  Firefox needed execution outside the sandbox because page creation failed before reaching the application.
- New Task 20 CI browser journey: four passed, one per browser.
- Final authenticated Task 20 journey: passed with zero Axe violations and page errors.
  The mobile screenshot was inspected after the navigation transition settled.
- Final preference suite and corrected migration replay: 18 passed.
  This includes competing identical requests and recovery of a missing history guard after interrupted DDL.
- Ruff, format, OpenAPI drift, generated contracts, and sole Alembic head: passed.
- Python lock verification, Python dependency audit, full npm audit, and production npm audit: passed.
  Audits found no known vulnerabilities; the local editable application is excluded from the package audit.
- First full backend run: 1,104 passed and one migration replay failure, with 86.55% service coverage.
  The additive migration now handles replay; its focused regression passes.
- Second full backend run: interrupted after the disk filled and caused migration failures.
  Only completed Task 20 scratch data and the audit download cache were removed.
- Final full backend run: 1,106 passed with 86.99% service statement coverage.
  This includes all 31 cases in `test_migrations.py`, plus the Task 20 migration/history tests.
  The final focused migration-recovery suite also passed after the missing-guard recovery change.

Logs and local browser evidence are under `src-main/backend/.tmp-task20`.
The complete backend receipt is `backend-full3.log`; the complete frontend receipt is `frontend-final.log`.
Existing browser receipts are `browser-full1.log` and the successful Firefox rerun, `browser-firefox2.log`.
The new four-browser preference receipt is `browser-preferences-four.log`.
The final authenticated receipt is `browser-1788872750698/result.json`, with `preferences-mobile.png` beside it.
Gitleaks over nonzero Task 20 commits is not applicable because no Task 20 commit exists.

## Review and limits

The coordinator completed separate Standards, Spec, and Test Judge self-reviews.
The user's instruction prohibits sub-agents, so independent agent reviews are not claimed.
Standards checks cover scope, additive migration, typed contracts, source ownership, and unrelated-work preservation.
Spec checks cover every requested control, global versus effective state, opt-out, transfer, and protected assessment history.
Test Judge checks cover real persistence, owner denial, concurrency, transaction failure, and the authenticated browser path.
The reviews found and resolved the effective opt-out flag and interrupted-migration guard recovery issues.
No blocking code finding remains, and the complete local backend gate passed.

These are local engineering checks, not a hosted release or institutional pilot approval.
No manual screen-reader study or native Safari check was performed. WebKit is the tested Safari-engine proxy.
Automated keyboard, Axe, and reflow evidence does not replace human accessibility testing.
Diagnostics, pathway selection, tutor dialogue, appeals, and other numbered tasks remain outside this change.
