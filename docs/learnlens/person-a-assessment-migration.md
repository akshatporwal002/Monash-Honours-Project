# Person A assessment migration and recovery

## Scope

Revision `20260815_0018` preserves the old numeric LMS attempt data in
`assessment_legacy_history`. The table is migration-only after migration.

It copies each existing `submission_attempts` row with its original status and
score. It does not create an assessment decision and does not map a score,
percentage, or completed submission to `PASS`.

If an older deployment has the retired `legacy_learner_results` table, the
revision imports it as compatibility history. Only an explicit public `FAIL`
maps to compatibility `INCOMPLETE`. The original result, score, response ID,
migration revision, migration actor, and migration reason remain in the
history row. It also writes one deduplicated audit event for that consequential
mapping. `PASS` and unknown values stay unmapped until an approved human
migration policy exists.

Legacy Quality Judge `pass` and `fail` values are not learner-result inputs.
They stay in the Quality Judge compatibility path, where `pass` means
`APPROVED` and `fail` means `REJECTED`.

## Upgrade procedure

1. Confirm the current Alembic heads before creating or applying a revision.

   ```powershell
   Set-Location src-main/backend
   .\.venv\Scripts\python.exe -m alembic heads
   ```

2. Make and verify a backup before removing any compatibility data.

   ```powershell
   .\.venv\Scripts\python.exe scripts/verify_sqlite_backup.py `
     --database .\quantumlearn.db `
     --output-dir .\backups
   ```

   The command runs SQLite integrity and foreign-key checks, copies the
   database, restores that copy to an isolated temporary file, and compares
   row counts plus per-table SHA-256 digests. Keep the backup and its JSON
   manifest together.

3. Run the migration.

   ```powershell
   .\.venv\Scripts\python.exe -m alembic upgrade head
   ```

4. Check that source attempt counts match archived attempt rows. Check that
   every non-null `response_version_id` in the archive points to the original
   response. Inspect every `mapped_result` row and its deduplicated migration
   audit event before exposing it to any client.

## Recovery rules

The revision is idempotent after the complete history schema exists. It uses the
source-table plus source-record key to skip rows already archived. If a process
stops after copying rows but before Alembic records the revision, rerun
`alembic upgrade head`. Do not delete or rewrite history rows to retry it.

SQLite can leave partial DDL after an interrupted migration. On startup, this
revision validates every archive column type and nullability, key, check,
foreign-key action, index, and immutability trigger before copying a row. If it
finds an incomplete archive table, it stops with a recovery error. Restore the
verified backup, confirm the old revision, and rerun the upgrade. Do not try to
repair or fill the partial table by hand.

If the deployment has multiple Alembic heads, stop before applying this
revision. Create a merge revision that only joins graph heads. It must not
change Person A legacy mapping rules or reinterpret Person B data.

If `legacy_learner_results` exists with a different shape, the migration stops
without modifying it. Back up the database, document the columns and values,
and add a reviewed compatibility adapter. Unknown source results stay unmapped.

Downgrading a populated archive is blocked. Only use a rollback after the
verified backup exists and its manifest matches, then restore that backup and
the prior package. A clean archive can downgrade normally. The source legacy
tables are not removed by this revision.
