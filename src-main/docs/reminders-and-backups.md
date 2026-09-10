# Reminder operation and isolated backup restoration

## Reminder delivery

Run the existing `quantumlearn-worker` process after upgrading the database. Its reminder pass
scans active enrolments in published courses in bounded batches, then waits one minute after a
complete scan. Dashboard reads calculate their projections without creating reminders or saving
recommendations. Existing submission commands still persist their recommendations.

Automatic reminders become eligible 24 hours after the effective deadline. Both automatic and
educator reminders respect the global `reminders_enabled` setting, learner opt-out or timed pause,
current task access, accepted submissions, individual access-plan pauses, and the rolling 24-hour
delivery limit. A restart may repeat a scan; the database delivery guard prevents duplicate delivery.
Marking a reminder as read does not restart its delivery window.

Learners manage notification preferences under their preferences page. Course owners configure an
IANA time zone in the course editor and record individual arrangements under **Manage individual
deadlines**. Existing courses default to UTC. New local deadlines are converted to absolute instants;
nonexistent daylight-saving times are rejected and repeated times require an explicit occurrence.
Changing a course time zone changes presentation, not a previously recorded deadline's instant.

An extension cannot shorten the course deadline. Each arrangement replaces the previous individual
arrangement for that learner and task. An access-plan pause continues until changed or revoked.
Private staff reasons remain in the owner-only history; learners receive the separately entered
notice and their effective deadline. These records do not change assessment criteria or results.
Revision checks reject stale edits and request keys make identical retries safe.

Migration `20260909_0039` preserves arrangements and preferences as append-only history. Downgrade
refuses populated history or configured non-UTC course zones. An empty downgrade retains the additive
UTC column so existing course snapshots remain unchanged. Production recovery should use a verified
backup and the corresponding application version.

## Capture a backup

For Docker capture and preparing a fresh rollback volume, use the packaged
[release commands](deployment.md#release-backup-and-rollback-candidate). The backend
image includes both `scripts.learning_backup` and `scripts.verify_sqlite_backup`.
The commands below are the corresponding source-checkout interfaces.

From `src-main/backend`, using the installed backend Python environment:

```powershell
python -m scripts.learning_backup create --database C:/LearnLens/data/app.db --uploads C:/LearnLens/uploads --output-dir C:/LearnLens/backups
```

The command creates a uniquely named directory containing `database.sqlite3`, `uploads/` and
`manifest.json`. The SQLite backup API captures one consistent database snapshot. The command then
copies every source file referenced by that snapshot, including historical source revisions.
Immutable storage keys make these files match the snapshot even if another source version is being
uploaded. Unreferenced files and in-flight staging files are excluded. Missing files or mismatched
recorded SHA-256 content hashes fail capture and remove only the new incomplete bundle.

Verification checks SQLite integrity and foreign keys, every table's count and content digest,
schema definitions (including history-protection triggers), one recorded migration head, database
bytes and uploaded-file bytes. Capture also performs an isolated restore before reporting success.
The manifest detects accidental corruption; it is not a digital signature. Store the entire bundle
in access-controlled storage with the same protections as the live learner data. Files without a
recorded SHA-256 source hash can be checked against their captured bytes, but not against an absent
original content hash.

## Restore for inspection

```powershell
python -m scripts.learning_backup restore --bundle C:/LearnLens/backups/learnlens-BUNDLE --destination C:/LearnLens/restore-candidate
```

The parent directory must already exist and the destination must not exist. The command verifies the
bundle before creating a destination, copies it, and verifies the copied database and files again.
It never overwrites an existing database or directory and does not switch application configuration.
Traversal paths, symbolic links and Windows reparse points within file keys are rejected.

Before an operational cutover, run the matching application version against the candidate database
and upload directory, check its readiness migration head and permissions, and inspect representative
source downloads and protected histories. Keep the live deployment separate until that review is
complete. This tool does not restore external provider configuration, secrets, logs or unrelated
filesystem content. Broader process-termination, provider-fault and release drills remain Task 37.
