# Task 14 learning episode handoff

Task 14 implements typed learning responses, immutable prediction checkpoints, and reviewed fresh application stages. Local checks pass. Independent Standards/Spec review and coordinator integration remain release gates.

## Commit and ownership record

- Verified base: `865467740c1c122834bd67d3c7f6a7ca77bd381c`.
- Pure contract: `d8a26e989c7a04f7b2de8fe869725962e45f234f`, following `dcfac3a77e98c116cad58d1ec486fbf25921fdd2`.
- Backend foundation: `3eda90720f4a5776d80afbd8c8954a34428d6052`.
- Coordinator review, freeze, and publication wiring: `dca96f9bea4570d9e9050af4805092b01df86e7f`.
- Coordinator authoring, contracts, and migration fixture updates: `dd6bec5412c12a4c69b8a35b01dce8ec1e325bc9`.
- Backend history and migration hardening: `9100121a3628179ccf7c0e819ab2be189281f875`.
- Coordinator typed contract refresh and heading fix: `5d57ec63b5fa1f0df990fb03d5f7da9dd8a03565`.
- The final implementation commit contains this handoff. The delivery message supplies its exact SHA.

Task 14 owns episode schemas, persistence, lifecycle services, simulation bindings, learner workspace, and focused tests. The coordinator owns task review, form publication, authoring controls, generated contracts, and shared fixtures. Task 15 owns evaluator decisions and assessor workflow. No push or main update was performed by Task 14.

## Delivered behavior

Prediction, reasoning, explanation, revision, reflection, and transfer have typed, lossless response shapes. Text and code retain whitespace. Circuit JSON retains nested fields. Existing FR9 task types keep their handlers. Unknown or staged types show an unsupported state and do not silently become short answers.

The task workspace keeps instructions, circuit editing, simulation results, explanation, reflection, and saved responses together. Controls have labels, keyboard gate buttons, episode navigation, and circuit text equivalents. Withdrawn task history renders the learner's saved episode through `SavedTaskHistory` and `EpisodeSnapshot`.

The server saves a draft before simulation. It requires an immutable prediction checkpoint bound to learner, task, work start, stage, part, prediction, circuit, shots, and seed. Changed input requires a new checkpoint. Read, list, reload, and result projections check this boundary. Invalid input, timeout, and interrupted execution preserve accepted work. A technical failure does not create a formal assessment penalty.

Checkpoint history records prediction and input before submission. It does not manufacture a formal response. History uses pages of 20 by default, with a maximum request of 100 and a nonnegative offset. The learner can load every older page. History remains scoped to the current learner and course ownership, including withdrawn tasks.

Revision references identify an actual earlier response in the same learner, task, work, and stage scope. Earlier versions retain their own evidence references. Reflection can be saved after a submission by creating a later response with an explicit revision reason. Reflection and help use are not added as automatic formal penalties.

## Reviewed plan and privacy

`EpisodePlanV1` lives in `marking_criteria.episode_plan`, covered by the exact teaching revision. Form creation freezes its canonical copy in `TaskFormVersion.constraints.episode_plan`. Publication requires equality to the reviewed revision. Legacy tasks with no plan keep their existing behavior.

`validate_reviewed_episode_plan(marking_criteria, frozen_plan=None)` validates the plan and rejects a different frozen copy. Default required responses are prediction and explanation. Conceptual hints are unlimited during supported work. Accessibility support remains available in both stages.

Initial task reads omit hints and all private transfer content. The authenticated episode-state route provides supported hints before transfer. Server-authorized stage entry returns only the fresh prompt, instructions, starter inputs, and stage references. The private solution is never returned, including after entry. Transfer state removes instructional hints.

The local fixture uses a synthetic reviewed and published multipart Hadamard task at APPLY. It proves the approval mechanism and learner flow. It does not approve unseen live teaching content.

## Shared contracts and Task 15 adapter

Pure schemas are in `app/schemas/episode.py`. The read-only protocol and typed failures are in `app/services/episode_contract.py`.

```python
SqlAlchemyFrozenResponseReader(session).read(*, assessment=assessment_reference)
```

The reader returns `FrozenResponseRead`, including content, episode, immutable work/form references, evidence reference, and historical declared conditions. Missing, stale, and invalid data raise `FrozenResponseMissing`, `FrozenResponseStale`, and `FrozenResponseInvalid`, under `FrozenResponseError`.

The reader checks frozen links, learner ownership, response version, digest, revisions, and simulation bindings. It uses direct immutable reads under `no_autoflush`. It does not call simulation recovery or write an interrupted outcome.

`canonical_response_digest` preserves the exact historical `assessment.response.v1` path. Episode submissions use `assessment.response.v2`, which binds all episode data and frozen references. `extract_response_evidence` and `export_response_snapshot` preserve the full response. Historical declared conditions support both dictionary and list shapes.

Task 13's exact work-start equality, unchanged successful retries after publication changes, whitespace, and retryable write-busy behavior remain covered by regressions. The old positional simulation fixture now names its original columns explicitly. Its immutability assertion remains intact.

All four episode routes declare safe response DTOs:

| Route under `/students/me/tasks/{task_id}/episode` | Response |
| --- | --- |
| GET | `EpisodeStateRead` or null |
| POST `/checkpoints` | `EpisodeCheckpointReceipt` with saved draft |
| POST `/transfer` | `EpisodeStateRead` |
| GET `/checkpoints?limit=20&offset=0` | `EpisodeCheckpointPage` with items and next offset |

Frontend episode data and response types use generated `ApiSchemas` aliases. The existing `request<T>` helper is exported for Task 15, retaining existing CSRF and error handling.

## Migration and rollback

Migration `20260907_0030` follows `0029`. It adds episode columns, immutable checkpoint/stage tables, and simulation foreign keys. SQLite's task-type CHECK expands to admit all six new types. The safe table rebuild preserves rows, indexes, foreign keys, and every trigger. It runs a foreign-key check before committing.

Simulation references use explicit `ON DELETE RESTRICT`. Real migrated schema reflection now matches model metadata, including Alembic `command.check`. PostgreSQL DDL uses the corresponding named constraints; PostgreSQL execution was not run locally.

Downgrade preflights protected history before any DDL. It refuses existing episode records, new task types, and protected legacy/review/evaluation history. It does not coerce types or discard responses. Empty-database downgrade and replay pass. Manifest-preservation tests confirm that refused downgrades leave the schema and history intact.

## Verification record

Run commands from this worktree's backend or frontend. Backend used the root `.venv` interpreter read-only, task-local `PYTHONPATH`, TEMP/TMP, and unique basetemp directories. Frontend used Node 22.13.0 and its own dependencies.

| Check | Result and evidence |
| --- | --- |
| Full migrations plus episode, Task 13, simulation regression suite | 94 passed, backend `.tmp-task14/finalbackend25.log` |
| Final typed-route, paging, episode lifecycle and pure contracts | 31 passed, backend `.tmp-task14/typed28.log` |
| Backend Ruff and format | Passed on changed backend files |
| Learner workspace, App, saved task history UI | 26 passed, backend `.tmp-task14/frontend-tests28.log` |
| Frontend lint | Passed, backend `.tmp-task14/frontend-lint29.log` |
| Production build | Passed, backend `.tmp-task14/frontend-build29.log`; existing bundle-size advisory remains |
| Real Chrome synthetic learner journey | Passed, backend `.tmp-task14/browser29.log` and `browser29/result.json` |

The principal backend command was:

```text
python -m pytest tests/test_migrations.py tests/test_task14_lifecycle.py tests/test_task14_contract.py tests/test_assessment_work_starts.py tests/test_simulation_evidence.py -q --basetemp=.tmp-task14/finalbackend25
```

After typed routes and pagination, the focused command was:

```text
python -m pytest tests/test_task14_lifecycle.py tests/test_task14_contract.py -q --basetemp=.tmp-task14/typed28
```

Frontend commands were `npm.cmd run lint`, `npm.cmd run build`, and `npm.cmd test -- src/test/Task14EpisodeWorkspace.test.tsx src/test/App.test.tsx src/test/TaskPageHistory.test.tsx`.

The reproducible browser files are `tests/task14_browser_server.py`, `e2e/task14-vite.config.ts`, and `e2e/task14-episode.local.mjs`. Set `TASK14_BROWSER_RUN` to a fresh scratch name and `TASK14_PYTHON` to the backend interpreter. Start the fixture from backend and Vite with `--config e2e/task14-vite.config.ts` from frontend. Run `node e2e/task14-episode.local.mjs` from frontend.

The observed journey used normal login and production APIs. It checked keyboard gate entry, immutable prediction, controlled timeout, draft reload, real Aer simulation in both stages, hidden solution, supported hint removal, fresh application code, submission, earlier-response revision, and post-submission reflection. It created 21 predictions and loaded the older page. Axe found no serious or critical violations. Screenshots are in backend `.tmp-task14/browser29/controlled-timeout.png` and `submitted-episode.png`.

Task-owned listeners on ports 8144 and 5244 were stopped after verification. A final `netstat` check showed neither listener. Coordinator servers on 8140 and 5240 were left alone.

## Explicit staged PD4 extensions

The following types are staged individually: matching, sequencing, state comparison, diagnosis, probability interpretation, part-complete work, and confidence prompts. `STAGED_TASK_TYPES` records them in `services/task_types.py`.

Each needs its own validated schema, registered handler, accessible renderer, lifecycle and failure tests, evidence extraction, evaluator input, and lossless export tests before support can be claimed. Use the `EpisodePayloadV1` stage/content boundary, explicit task handler registry, and TaskView renderer selection as the extension points. Confidence must not become an accidental grading penalty.

## Remaining gates and boundaries

The coordinator must complete independent Standards/Spec review and combined integration checks. Supported release browser projects are `chrome-stable`, `edge-stable`, `firefox`, and `webkit`; this task's observed local journey used installed Chrome only. The coordinator owns combined cross-browser release evidence.

Task 15 must use the final typed read-only adapter in assessor review and evaluator workflows. Task 14 provides evaluator-ready inputs; it does not activate AI assessment suggestions under D-07. Task 17 owns the full evidence stream. Task 26 owns fresh formal reassessment. Tasks 33 and 34 own governed exports. None of those tasks is claimed complete here.
