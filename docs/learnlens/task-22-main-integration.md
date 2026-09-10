# Task 22 integration verification

This records the 9 September 2026 integration of Task 22 with the published application.
The published baseline `e3ce194ce8fda49a37d2c0f11ac5f08228ef2096` passed GitHub CI run `34312645000`.
The verification below covers the combined preference, curriculum, and activity-continuation behavior.

## Combined behavior

The published Task 20 preference schema remains authoritative. Its original migration `20260908_0033` is unchanged.
The `/students/me/preferences` API and `/learner-preferences/me` controls share one protected revision history.
Both interfaces use the same personalisation opt-out. The support controls map their bounded presentation choices
onto the published enum values. Existing richer format choices remain stored in their original history.
Support amount and feedback display remain intact when the published interface changes another preference.
The support API keeps its existing conflict checks, reset history, and task-effective restrictions.

The shared service is now a package, exposing the existing support service alongside the published service modules.
The API, model imports, educator controls, learner workspace, and generated contracts include both implementations.
The dashboard remains read-only while projecting Task 22's durable choices.
Tutor, learner results, reassessment, human review, optional rewards, reminder controls, and backups remain present.
This integration does not add new numbered-task scope or enable Task 35 operational AI assessment.

## Migration order and data protection

Published migrations through `20260909_0039` keep their identities and definitions.
Unpublished Task 21 and 22 migrations move after that chain:

- `20260909_0040` adds support display fields with defaults to the published preference history and restores immutable guards.
- `20260909_0041` adds the Task 21 curriculum and diagnostic records.
- `20260909_0042` adds Task 22 activity receipts and choices. This was the sole head for these integration checks.

The upgrade test creates preference history at published revision 0039, upgrades to head, and checks every original field.
It also checks schema drift and foreign keys. The cross-interface test proves shared opt-out, revision order, and retained support choices.
Downgrade preflight checks later-task protected history before any Task 22 DDL.
No application database was migrated during this integration. Tests use isolated disposable databases.

## Verification record

All 1,222 backend tests are verified through full runs and corrective reruns, with 87.66% service coverage.
The full runs initially used the earlier environment: shard A passed 527 of 529 tests; shard B passed 689 of 693.
Five failures came from missing Windows time-zone data. All 13 reminder tests passed in the combined frozen environment.
One inherited downgrade assertion expected the older failure point. It now verifies refusal at head 0042; both tests in its file pass.
A further 103-test run in the combined environment passed migration, protected-history, preferences, and upgrade checks.
No failed assertion remains unresolved. This records actual run history rather than claiming one clean invocation.

All 112 browser regressions pass across Chrome, Edge, Firefox, and WebKit.
The earlier browser attempt used the old environment and encountered reminder validation failures and Windows Firefox timeouts.
The final run uses the combined environment and headless Firefox. The preference test now targets its summary disclosure,
not the new navigation link with the same label. No product behavior was changed to work around those browser failures.
The frontend build, lint, and all 267 tests pass.
Focused persistence tests found and fixed a new-column length mismatch and an old lowercase storage assertion.
The new published-data upgrade and shared-history tests pass.
The frozen combined Python dependency audit reports no known vulnerabilities.

Full backend checks use separate processes and isolated databases, caches, and coverage files.
The frozen environment includes `tzdata`, required by the reminder implementation on Windows.
All browser helpers use isolated ports and hidden processes.

The Task 20/21/22 implementation records describe their original verification.
This integration record describes the combined preference storage and revised migration sequence.
The package lock and generated contracts are checked against this combined tree.
The npm dependency tree is unchanged from the verified Task 22 tree; its required high-severity audit gate passed,
with two moderate development-only advisories and no production findings.

Separate self-review passes checked standards, specification boundaries, and test evidence.
Independent review, deployment, and remote database migration are not established by these local checks.

The final authenticated Task 22 journey passed in Chrome, Edge, Firefox, and WebKit, with zero page errors and Axe violations.
It exercised checked feedback, model update, approved suggestion, accept/defer/replace, educator override, and reload history.
