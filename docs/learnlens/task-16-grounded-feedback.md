# Task 16: grounded assessed feedback

Status: implementation complete; final quality gates and independent review remain required before merge.

Branch: `feat/task-16-grounded-assessed-feedback`.
Base: `ef0a13d7fce3c6368bb50c9f36ce33251568e64b`, fetched and verified on 2026-09-07.
Worktree: `.tmp-coordinator/task16`.

## Behavior

Assessed feedback uses the existing feedback workflow, storage, worker leases, and recovery path.
It now provides criterion-linked guidance, recorded evidence, approved conceptual hints, source excerpts, and a reflection prompt.
Each claim is an exact excerpt with passage offsets, a content digest, and its source approval reference.
Response observations describe recorded fields without judging their correctness.
Current confirmed human criterion history can identify a criterion needing more evidence or revision.
Pending machine decisions and private assessor reasons never enter the learner projection.

The assessed adapter uses the versioned `bounded-extractive-v1` local template.
It does not send assessed responses to an external model or produce free-form AI assessment suggestions.
Practice feedback retains its configured provider.
The deterministic judge permits only the bounded payload reconstructed from the trusted frozen context.
Modified claims, invented learner statements, forged quotes, extra help, and absent reflection prompts are rejected.
Obvious instruction payloads in source text are rejected too. Source text is never executed or followed as an instruction.

Feedback approval does not write assessment results, criterion decisions, or assessor actions.
Task 35's separate AI assessment validation gate remains closed.

## Evidence and gaps found before editing

| Existing behavior | Gap | Change |
| --- | --- | --- |
| `PendingAssessmentFeedbackGenerator` refused assessed context | Every assessed response received a fallback | Production composition now uses the bounded assessed adapter |
| `TaskSourceRetrievalProvider` assigned relevance 1 | Approval and relevance were not checked | Existing scoped retrieval ranks exact approved passages |
| Generator checked citation membership | A valid ID could support an invented claim | Quote text, offsets, digests, and complete allowed content are checked |
| Assessment context used mutable task instructions | Later edits could change feedback context | Frozen response and reviewed revision readers supply the context |
| Context read machine evaluations | Later human corrections could be missed | Current confirmed human action and criterion evidence are revalidated |
| API returned cached content directly | Transfer, source withdrawal, and changed human history could leave unsafe content visible | Every read checks release conditions and saved source bindings |
| Generator exceptions skipped judged attempts | Provider failure could lose rejection history | Assessed failures become two recordable attempts before fixed fallback |

## Interfaces

`ValidatedFeedbackView.assessed` is an optional `learnlens.assessed-feedback.v1` DTO.
The surrounding response keeps `workflow_run_id`, `submission_id`, and `feedback_id`.
The assessed DTO adds exact assessment, task revision, form, response digest, criterion, human action, and help-use references.
It includes source revision and passage digests, approval IDs, retrieval request IDs, and retrieval versions.
Simulation references retain original run, circuit, checkpoint, stage, engine, and policy provenance.
No simulation is rerun to manufacture assessment feedback context.

The adapter reuses `FrozenResponseReader`, `FrozenReviewEvidenceReader`, `EpisodePayloadV1`,
`canonical_response_digest`, `extract_response_evidence`, and the current human assessment history.
It does not create another episode format or another hint-use table.
`EpisodeHelpUse` remains the authority for durable approved help requests.

`AssessedFeedbackGenerator` and `AssessedFeedbackJudge` wrap the existing practice adapters.
The workflow stores structured content, source attributions, both rejected attempts, and quality outcomes in its existing records.
No migration or schema-head change is needed. Generated API contracts include the new DTO.

## Help and release boundaries

Supported work retains unlimited approved conceptual hint requests with no result penalty.
Active transfer receives no instructional feedback. Approved access support remains available through the existing episode path.
The adapter withholds cached feedback while that learner has active transfer work in the same course.
This conservative rule prevents an earlier task's feedback from helping a fresh application.

Full episode feedback requires its saved transfer response. Reviewed non-episode work can release after submission.
Explicit `after_confirmation` or `after_assessment` timing requires a current confirmed human action.
Unknown timing values fail closed.
A void or faulted attempt cannot release assessed feedback.

Saved feedback whose human action has changed is withheld. Its original records remain available for authorised inspection.
The current workflow remains one durable feedback run per response; it does not silently regenerate after a human correction.
A new permitted response receives its own feedback workflow.
Task 24 still owns the wider learner result and appeal experience.

Sources must remain approved, indexed, available, and within the frozen task and course scope.
A changed approval, withdrawal, retirement, or indexing failure withholds the cached projection.
These checks do not rewrite the historical feedback, source, or learner response.
Missing reviewed historical context fails safely. Existing valid historical evidence and its warnings remain readable by authorised reviewers.
Invalid digests and foreign evidence remain rejected.

## Verification

Focused tests cover exact frozen context, human history, source approval and relevance, forged claims,
reflection, transfer privacy, ownership, course access, regeneration, fallback, provider failure, and durable replay.
The browser fixture uses ordinary source review, task review, publication, staff grants, and learner authentication.
No production permission or policy override is used.

The real UI journey submits a frozen episode, reads three criteria and supporting passages, checks reflection,
and reloads the same response, feedback, workflow, and source references.
It checks hidden pending results, hidden private solutions, keyboard operation, Axe, and page errors.
The synthetic fixture and journey are `tests/task16_browser_server.py` and `e2e/task16-feedback.local.mjs`.
Their isolated ports are 8166 and 5266. Evidence lives under `src-main/backend/.tmp-task16`.

Final check counts, commits, PR, reviews, and remote CI evidence are recorded below when verified.
Never infer delivery from this implementation checkpoint alone.

## Limits and recovery

The first assessed adapter deliberately produces bounded excerpts and evidence guidance, not unrestricted tutoring prose.
Lexical retrieval establishes task relevance within the approved passage set; it is not a semantic truth evaluator.
At most three short passages are quoted per feedback item. Unsupported context reaches a fixed safe fallback.
This limit concerns feedback size, not a learner's conceptual hint allowance.

The reflection requirement concerns the feedback prompt. Missing learner reflection is not converted into a formal result penalty.
Research eligibility remains separately governed. Arv Surana is the named research lead; study approval remains outstanding.
No hosted deployment, live learner study, or institutional approval is claimed.

No database migration is required. To roll back code, preserve the stored feedback and source records.
An earlier application ignores the additive assessed field, but its old generic feedback projection must not be used for a live rollback.
Review rollback privacy before release. Restore no database merely to erase recorded feedback.

Tasks 17, 24, and all other numbered tasks remain outside this change.


## Local verification checkpoint

- Frontend: 234 tests across 65 files passed. Lint and production build passed.
- Browser suite: all 72 Chrome, Edge, Firefox, and WebKit checks passed.
- Final authenticated Task 16 journey: passed with zero Axe findings and page errors, including keyboard disclosure and reload.
- Focused final feedback, release, retrieval, and workflow regression: 47 tests passed.
- Legacy retrieval follow-up: eight tests passed. Real worker kill and recovery: one test passed.
- Initial complete backend run: 1,031 passed, nine failed, with 86.53% service coverage.
  Eight failures shared the synthetic source index-state omission. One exposed missing legacy passage metadata.
  Both fixes passed the focused checks above. A complete corrected run and PR CI remain required.
- All 31 migration cases passed in that complete run. The sole head remains `20260907_0031`.
- Ruff lint and formatting, OpenAPI drift, and frontend contract drift passed.
- Locked Python dependency checks and Python/full npm/production npm audits passed with no known vulnerabilities.

Logs include `frontend-final.log`, `build-final.log`, `browser-final.log`, `final-regression.log`,
`legacy-retrieval.log`, and `worker-final.log` under `src-main/backend/.tmp-task16`.
The final authenticated evidence is `browser-final03/result.json` and `browser-final03/grounded-feedback.png`.
Headed Firefox had visibility/setup failures on this Windows desktop; the supported headless setting passed all unchanged assertions.
A prior agent helper survived its usage-limit interruption. Its exact owned process tree was identified and stopped.
The final authenticated run used fresh data and stopped its own server trees.

Independent final Standards and Spec reviews are outstanding because the review agents hit the account usage limit.
This does not count as a review pass. Do not merge until both reviews and the exact-head CI gates pass.
