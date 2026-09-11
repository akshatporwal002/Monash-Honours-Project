# NFR10 suppression and exclusion audit — 11 September 2026

Read-only source/configuration audit of candidate `dff979d`. This document records
the reasons supported by the code and the accountable maintenance roles. A role
is a maintenance responsibility, not a claim that a named human approved an
exception. The inventory was read-only; the subsequent authorized repair moved
five imports and ran only Ruff check/format on the two affected Python files.
No application, test or profile execution was performed. Final CI and performance
acceptance are reported separately.

Scope: tracked files under `src-main` and `.github`, the root `.gitleaksignore`,
backend `pyproject.toml`, frontend ESLint/TypeScript/Vite/Playwright configuration,
and the quality workflow. Searches covered `noqa`, Python type ignores, TypeScript
and ESLint disables, coverage ignores, test skips, accessibility rule exclusions
and workflow bypasses. Git-tracked enumeration avoids ignored local environments
and private scratch files. Line references below describe this candidate.

## Configured boundaries and written exclusion rules

| Boundary | Actual configuration and reason | Accountable role / disposition |
| --- | --- | --- |
| Backend lint | `backend/pyproject.toml` selects `E4,E7,E9,F,I`; CI runs Ruff check and format over `backend/.`, including tests, scripts and migrations. There are no repository-configured path exclusions or per-file ignores. Tool-default environment/cache/build exclusions are not application exemptions. | Backend maintainer. Do not describe this as checking every Ruff rule. |
| Backend coverage | `.github/workflows/quality.yml` measures `app.services` statement coverage at 80%. API, models, migrations, scripts and tests are outside this **measurement**, not excluded from pytest or lint. This matches NFR10's service-coverage denominator; no inline coverage-ignore directives were found. | Integration maintainer. Preserve the service denominator and report its limit; do not imply whole-backend coverage. |
| Backend tests | Pytest discovers `tests`; no configured skip/xfail policy was found. `tests/test_quantum_simulation.py:13–14` uses `importorskip` for optional Qiskit/Aer. CI installs `--all-extras`, so optional local absence must not be used as quantum CI evidence. | Simulation/test maintainer. Conditional local skip is justified by optional dependency packaging. |
| Python static types | No mypy/Pyright command or configuration is present in the audited quality gate. Python `type: ignore` comments listed below do not suppress an active CI type checker. Ruff is not a replacement for Python type checking. | Backend/integration maintainer. Do not claim Python static-type verification from this workflow. |
| Frontend lint | `eslint.config.js` excludes generated `dist`, applies recommended JS/TypeScript rules to `**/*.{ts,tsx}`, and retains React hooks rules. No source inline ESLint or TypeScript disables were found. The React Refresh export rule is a warning with `allowConstantExport: true`, appropriate to Vite's constant-export refresh support; it is not a blocking error. JS/MJS tooling has no corresponding configured recommended-rule block. | Frontend/tooling maintainer. Dist is rebuilt output; do not claim equivalent lint coverage for JS/MJS helpers. |
| Frontend types | `tsconfig.app.json` checks `src`, including generated contracts and unit tests, with `strict`; `tsconfig.node.json` includes the named Vite/Playwright configs and `e2e/urls.ts`. Both use `skipLibCheck` for dependency declaration files. E2E test bodies and MJS runners are outside `tsc -b`; browser execution and TS lint are separate checks. | Frontend/tooling maintainer. Dependency declaration checking is omitted, not application checking. |
| Browser selection | `playwright.config.ts` excludes learning-loop and misconception journeys only from the ordinary browser invocation; the workflow runs each in a separate mandatory stage using their specialized fixture servers. Four configured engines run; WebKit does not establish native Safari acceptance. CI retries twice and forbids `.only`; retries are not skips. | Browser-test maintainer. A preceding failure can prevent later stages; retain that missing execution explicitly. |
| Unit-test resources | Vite limits workers to two while retaining isolation and existing deadlines. No custom Vitest test/coverage exclusions or inline accessibility rule exclusions were found. | Frontend-test maintainer. Resource bound, not an assertion exemption. |
| Dependency audits | Python `pip-audit --skip-editable` omits the local project distribution, whose code is checked separately; installed dependencies remain audited. npm runs both the full tree and production-only tree, with `high` failure threshold. `npm ci --audit=false` avoids duplicating the separately required audit. The retry wrapper ultimately fails after three attempts. | Dependency/security maintainer. Moderate/low findings remain reportable; do not describe the threshold as zero advisories. |
| Secret scan | Eight exact historical `commit:path:generic-api-key:line` fingerprints exist in `.gitleaksignore`; no path-wide or rule-wide allowlist is added. Each has its existing rationale/owner in the [secret-scan register](secret-scan-gate-2026-09-10.md). Full-history default rules, redacted reporting and the separate positive-control path/line assertion remain enforced by `.github/scripts/secret_scan.py`. Text-patch scanning has the documented binary/submodule limitations. | Security maintainer; retain the existing recorded owner rather than inventing renewed approval. Changes require exact new evidence, never broadening an old fingerprint. |

Paths in the inventories below are relative to `src-main/backend`.

## Active Ruff suppressions

| Locations / rule | Code-based reason | Accountable role / disposition |
| --- | --- | --- |
| `app/models/__init__.py:1,221–224,226,231,237–238` — F401 | Package imports expose model names and register tables/history guards with shared SQLAlchemy metadata; these imports have effects even without local references. | Persistence maintainer; justified registration/re-export boundary. |
| `migrations/env.py:6,9`; `tests/conftest.py:7`; `tests/test_evidence_models.py:15`; `tests/test_migrations.py:33` — F401 | Import all required model modules before constructing/comparing metadata or creating tables. | Migration/test maintainer; justified metadata registration. |
| `app/models/user.py:61`; `app/models/persistence.py:678` — F821 | String ORM relationship annotations reference models registered in the shared model registry without importing reciprocal modules at runtime. | Persistence maintainer; justified circular model-registration boundary. A future type-checking pass may add `TYPE_CHECKING` imports without changing runtime loading. |
| `tests/learning_loop_browser_server.py:32`; `task16_browser_server.py:22`; `task20_browser_server.py:23`; `task21_browser_server.py:23`; `task22_browser_server.py:25` — E402 | Set isolated environment/database paths and amend the fixture import path before importing synthetic scanner support, which loads application configuration. | Browser-fixture maintainer; justified initialization order, confined to disposable test servers. |
| `tests/test_evaluator_release_workflow.py:10`; `test_moderation_review_followups.py:13`; `test_submission_integrity_cues.py:12` — F401 | Import the `migrated` pytest fixture for discovery/injection. | Assessment-test maintainer; justified fixture registration. |
| `tests/test_evaluator_release_packet.py:9` — F401 | `ROOT` is used directly; `example` is an imported fixture retrieved through `request.getfixturevalue("example")`. | Evaluator-test maintainer; justified fixture registration. |
| Former `app/api/routes/research_study.py:178,180–181,187` — E402 | Operational-export imports were placed after existing route definitions without an initialization requirement. The imports are now in the top group and all four suppressions are removed. | Research API maintainer; **finding A resolved**. |
| Former `app/models/assessment_moderation.py:134` — E402 | `DDL,event` are now in the top SQLAlchemy import block; history-listener registration remains after the declarations. The suppression is removed. | Persistence maintainer; **finding A resolved**. |

The file-level `B008` directives in `app/api/routes/materials.py:2`,
`retrieval.py:2` and `task_generation.py:2` refer to FastAPI `Depends` defaults.
`B008` is not selected by the current Ruff configuration, so these directives are
inactive. Likewise `SLF001` at `tests/test_continuation_repository.py:453` and
`test_database_worker.py:344–345` is inactive; the tests intentionally inspect
private claim-finalization/worker wiring to exercise failure recovery. Responsible
roles are the retrieval API and durable-worker test maintainers respectively.
Remove redundant directives when touching these files, or document a narrowly
scoped exception if those rules are deliberately enabled later.

## Python type-ignore inventory

These comments document local typing compromises; they do not disable runtime
validation or remove test assertions. They are inactive in the configured CI type
gate because that gate does not run a Python type checker. Grouped entries share
the stated reason and maintenance role; they are not blanket exceptions for future
code in those files.

| Locations | Actual reason | Accountable role / disposition |
| --- | --- | --- |
| `migrations/env.py:47` | SQLAlchemy connect callback receives a DBAPI connection annotated as `object`; SQLite cursor access enables foreign keys. | Migration maintainer; dynamic driver boundary, retain actual SQLite qualification. |
| `tests/test_assessment_contracts.py:216`; `test_assessment_evidence_port.py:107,171`; `test_assessment_models.py:436`; `test_rag_contracts.py:27,69` | Deliberately mutate frozen objects, call a prohibited constructor, assign an invalid evaluator enum, or pass absent extraction input to assert rejection/fallback. | Assessment/retrieval test maintainers; justified negative-test inputs. |
| `tests/test_assessment_feedback_context.py:311,326` | A generator with no valid output is a sentinel: assessed-context gates must reject or use the assessed path without invoking the ordinary generator. | Feedback-test maintainer; justified non-use sentinel. |
| `tests/browser_e2e_server.py:286,476`; `test_person4_e2e.py:247,383` | Independent-session audit recorder provides the expected recording operation without the concrete recorder class. | Browser/audit test maintainer; recording adapter test double. |
| `tests/test_audit.py:121,146`; `test_audit_event_mapping.py:22,83`; `test_learning_events.py:265,397`; `test_research_export.py:305` | Recording or deliberately failing recorder/hook substitutes exercise mapping, best-effort isolation and sanitized failures. | Audit/privacy test maintainer; narrow test doubles. |
| `tests/test_evidence_capture_adapters.py:70,139,187–188,197`; `test_evidence_privacy.py:143` | Recording/failing analytics, repository and audit substitutes exercise accepted evidence, reconciliation and analytics failure independently. | Evidence/privacy test maintainer; narrow test doubles. |
| `tests/test_feedback_application.py:295,435,437,529,531`; `test_feedback_pipeline.py:228,264` | Recording audit hooks, terminal observer and failing pipeline substitutes exercise execution/terminal-failure behavior. | Feedback-worker test maintainer; narrow test doubles. |
| `tests/test_database_worker.py:329–334,345` | Unused adapter sentinels isolate worker wiring; private pass audit access verifies the selected composition. | Durable-worker test maintainer; narrow wiring inspection. |
| `tests/test_terminal_observer_composition.py:195,199,211,252` | Repository/observer/research substitutes verify independent terminal consumers and durable failure handling. | Continuation/research test maintainer; narrow test doubles. |
| `tests/test_terminal_integration_outbox.py:593` | Monkeypatch the worker's private apply operation to inject a dispatch failure. | Outbox-test maintainer; justified fault injection. |
| `tests/test_metrics.py:36`; `test_research_baseline.py:99` | Heterogeneous override dictionaries construct typed records for valid and invalid metric/provider cases. | Research-test maintainer; fixture construction boundary. |
| `tests/test_feedback_agent.py:136`; `test_feedback_pipeline.py:168`; `test_quality_judge.py:152` | Helpers annotate coroutine arguments too broadly as `object`, then pass them to `asyncio.run`. | Feedback-test maintainer; **typing cleanup**, use a coroutine/generic return annotation rather than treating this as a necessary long-term exception. |
| `tests/test_assessment_definitions.py:178` | Seed helper assumes `session.scalar` found a task but declares non-optional return. | Assessment-test maintainer; **typing cleanup**, assert the task ID is non-null before return. |
| `tests/test_research_baseline_worker.py:101` | One-shot fake claim storage is cleared to `None` although its inferred type is non-optional. | Research-worker test maintainer; **typing cleanup**, declare optional fake state. |
| `tests/test_terminal_observer_composition.py:218,239,259,266–267` | Test `caplog` is annotated too broadly for `.at_level` and `.text`. | Continuation-test maintainer; **typing cleanup**, annotate `pytest.LogCaptureFixture`. |

## Findings and closure

**A — Resolved: unjustified import-order exemptions.** After campaign cleanup,
the four operational imports in `app/api/routes/research_study.py` were moved to
the top group and `DDL,event` joined the existing top SQLAlchemy imports in
`app/models/assessment_moderation.py`. All five `E402` comments are removed.
Routes and history-listener registration retain their original order. Diff review
found only the import relocation and suppression removal. Ruff check and Ruff
format check pass for these two files; the formatter first normalized mixed line
endings introduced by the edit. No tests, import execution or full suite were run.

**B — Residual typing/dead-directive cleanup.** The explicitly marked typing
compromises and inactive B008/SLF001 directives above should not be represented as
necessary permanent exceptions. They do not bypass any currently enabled check.
They can be removed through correct helper annotations/assertions and deletion of
inactive directives in a bounded maintenance change. No claim of passing Python
static type checking is made.

The documented coverage/build-output/dependency boundaries, registration imports,
fixture initialization and negative-test cases have concrete reasons. This report
supplies the missing written inventory and role ownership and records finding A's
repair; it does **not** authorize new exemptions, establish human approval or close final CI,
security, accessibility, packaging or load acceptance. Re-audit changed entries
when their modules or configured rule sets change.
