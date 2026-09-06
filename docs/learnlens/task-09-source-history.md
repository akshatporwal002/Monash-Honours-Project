# Task 9: preserved source history

Status: implemented and locally verified on 7 September 2026; ready for local integration.

Branch: `feat/task-9-immutable-source-revisions`.

## Preserved evidence

Successful processing now saves an immutable source revision and its passages.
Each revision retains the source label, file hash, storage key, extraction version, and extracted blocks.
Each passage retains its original chunk ID, text, heading, location, and hash.
The current search chunks remain a replaceable index over the latest successful extraction.

Reprocessing replaces that index without deleting archived passages.
Task creation and edits, generated tasks, feedback persistence, and assessed submissions save citation records.
Those records link the output version to the exact passage and any approval recorded when it was used.
Assessment feedback reads the attempt's saved citations instead of the task's current source list.

Source review decisions are append-only approval or revocation events.
Changing an approval leaves earlier decisions and output citations intact.
SQLite guards reject updates, deletes, and replacement inserts into source history.
ORM guards reject object changes and deletion too.

## Reviewer access

The following routes require course management access under the existing access policy.
Their common prefix is `/api/v1/courses/{course_id}/materials`.

| Route | Purpose |
| --- | --- |
| `GET /{material_id}/revisions` | List the source's revisions and review history |
| `GET /{material_id}/revisions/{revision_id}` | Recover a revision's exact passages and approval records |
| `GET /passages/{passage_id}` | Recover one cited passage |
| `GET /citations/{output_type}/{output_id}` | Find preserved task, feedback, or assessment citations |
| `POST /{material_id}/revisions/{revision_id}/approvals` | Record approval or revocation with an actor and reason |
| `POST /{material_id}/replacement` | Save a replacement upload while retaining earlier files |
| `DELETE /{material_id}` | Retire the material and retain its history |

Citation lookup supports output-version filtering and offset/limit pagination.
Reviewers can follow a citation's material and revision IDs to the exact passage and review history.
Course scope applies to every lookup, including retired sources.

Uploads use a content hash in the filename, so replacement does not overwrite earlier bytes.
Retirement hides the material from current listings, learner downloads, and new retrieval.
Authorised reviewers retain access to its archived passages and citations.

## Migration and recovery

Migration `20260907_0023` follows `20260821_0022` and updates the readiness pin.
It adds four source-history tables and two material lifecycle fields.
Existing chunks become `LEGACY_SNAPSHOT` passages with their original IDs.
The migration records no inferred educator approval.

Existing task material aliases resolve to the passages available at migration time.
These citation records use the version label `legacy-unverified`.
Surviving direct feedback passage references can be linked the same way.
Old feedback material aliases and assessed attempts are not assigned guessed historical passages.
Already deleted source text cannot be recovered by this migration.

The migration can run again without duplicating preserved revisions or citations.
Downgrades refuse populated source history before changing the schema.
The same preflight preserves existing assessment, evidence, model, and review histories.
Use the verified-backup recovery procedure when a populated deployment must return to an earlier version.
Back up both the database and uploaded files; the database alone cannot restore original documents.

## Verification

Focused checks cover original passage recovery, frozen labels and locations, source replacement,
approval retention, course access, retirement, raw mutation rejection, and failed reprocessing.
The application tests also check citation persistence through task generation, feedback, and assessment submission.
Migration checks cover fresh creation, existing records, repeat execution, protected downgrade refusal, and empty round trips.

| Check | Result |
| --- | --- |
| Full backend suite with service coverage | 741 passed; 85.31% service statement coverage |
| Final source-history tests, including populated migration replay | 6 passed |
| Fresh migration followed by Alembic schema comparison | No new upgrade operations detected |
| Backend lint and format | Passed; 316 files already formatted |
| OpenAPI and generated TypeScript drift checks | Passed |
| Frontend unit and accessibility suite, two workers | 178 passed across 52 files |
| Frontend lint and production build | Passed |
| Git whitespace check | Passed |

The initial frontend run had one 15-second timeout in `AssessorSetup.test.tsx` during parallel checks.
The complete rerun passed with two workers and the same test deadlines.
The build retains its existing warning about a JavaScript chunk exceeding 500 kB.
Backend and source-history logs are saved locally under `src-main/backend/.tmp-task9/`.
These are ignored local artifacts; the results above are the durable handoff record.
Remote CI, browser journeys, manual checks, and independent final review remain later release evidence.

## Boundaries and next task

Task 12 will enforce source approval as part of the complete publication lifecycle.
Task 9 records approval evidence but does not declare existing unreviewed tasks approved.
Task 10 owns durable processing claims, worker recovery, retries, and concurrent publication fencing.
Task 9 commits a successful source revision and its SQL search chunks together.
Its current vector index remains rebuildable cache state and can require rebuilding after provider failure.

Destructive retention rules remain unresolved under D-08. No destructive source purge was added.
No live provider, hosted deployment, institutional approval, or educational validation is claimed here.
Remote publication remains pending the requested GitHub push approval.
