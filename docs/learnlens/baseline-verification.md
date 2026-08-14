# LearnLens Person B pre-feature baseline verification

Status: runnable local gates pass; external and manual release evidence remains unverified

Recorded: 2026-08-14T18:14:08+10:00

Branch: `codex/person-b-platform`

Baseline parent head: `0a11d0ad36068b4af886fe31fe4ec9b72a2f43b4`

Scope: Step 3 of `docs/plans/001-person-b-platform-implementation.md`

## Outcome

The runnable commands configured in `.github/workflows/quality.yml` pass locally after two bounded
baseline repairs:

1. Step 2 injected the deterministic workflow clock into paired research creation, repairing the
   two reproduced analytics failures without weakening the half-open time filter.
2. Step 3 raised stale minimum tool/dependency versions and refreshed only the affected lock
   entries so the configured audits and declared runtime engines pass.

This record is pre-feature evidence. It does not prove the later Person B modules, hosted service,
production availability, representative load, native Safari, manual assistive-technology use,
external-model quality/cost, or human usability targets.

## Environment

| Item | Observed value |
| --- | --- |
| Operating system | Microsoft Windows NT 10.0.26200.0 |
| Shell | Windows PowerShell 5.1.26100.9168 |
| Git | 2.54.0.windows.1 |
| Python | 3.11.9 |
| uv | 0.11.15, run from an external temporary tool environment so it is not audited as a project dependency |
| pytest | 9.1.1 |
| Node.js | 22.13.0, matching updated `.nvmrc` and locked dependency engine floors |
| npm | 10.9.0 |
| Qiskit | 2.5.1 |
| Qiskit Aer | 0.17.2 |
| pypdf | 6.15.0 |
| Browser automation | Playwright 1.61.1; system Chrome and Edge; managed Firefox 151.0 and WebKit 26.5 |
| Secret scanner | Gitleaks 8.30.1 installed outside the repository |

## Reproduced baseline defects and bounded repairs

| Initial evidence | Root cause | Repair | Final proof |
| --- | --- | --- | --- |
| `test_sql_analytics_use_half_open_filters_roster_and_terminal_research` and `test_person4_deterministic_end_to_end` both failed because research rate denominators were zero. | `ResearchEvaluation.created_at` used host wall time while the workflows/tests used a fixed historical time; analytics correctly filtered on `[start_at, end_at)`. | Step 2 injects one UTC creation observation from `TerminalIntegrationWorker._now`, persists it on both pair rows, and gives direct analytics fixtures explicit creation times. | Widened research/analytics/export/E2E set: 57 passed; start, immediately-before-end, and exact-end boundary tests pass. |
| Locked Ruff format check reported four clean files. | Working-copy line endings were not in the pinned formatter's canonical form. | Ran Ruff format only on `app/core/security.py`, `app/schemas/__init__.py`, `app/services/feedback/providers.py`, and `app/services/rag/feedback_adapter.py`. | Full format check reports 230 files already formatted. Git has no semantic content diff for these four files. |
| Node 22.12.0 produced engine warnings for the current ESLint/jsdom stack. | Locked packages require Node 22.13.0 or newer within the supported Node 22 line. | Raised `.nvmrc` and the package engine floor to 22.13.0. | Final `npm ci` under Node 22.13.0 has no engine warning. |
| Full npm audit reported high advisories in `brace-expansion 5.0.8`, `nanoid 3.3.16`, and `undici 7.28.0`; production audit was already clean. | The lockfile predated fixed transitive releases. | Package-lock-only audit repair selected `brace-expansion 5.0.9`, `nanoid 3.3.18`, and `undici 7.29.0`; no direct package major changed. | Final full and production npm audits both report zero vulnerabilities. |
| Python audit reported two pypdf advisories at 6.14.2. It also saw stale local-only setuptools plus uv installed inside the project environment for initial diagnostics. | The pypdf lock predated 6.15.0; tooling packages were not project dependencies and would not exist in a clean CI-created environment. | Raised the pypdf floor and lock to 6.15.0; moved uv outside the project environment; removed unmanaged uv/setuptools; raised the CI uv pin from vulnerable 0.11.12 to fixed 0.11.15. | Final pip-audit reports no known vulnerabilities and only skips the editable project distribution. |

## Backend verification

Commands were run from `src-main/backend` with `APP_ENV=test` and the CI pseudonym secret where
configured. uv used the updated CI-equivalent version 0.11.15.

| Command | Result | Duration and exact evidence |
| --- | --- | --- |
| `uv lock --check` | PASS | Exit 0 in 0.028 s; 68 packages resolved without lock drift. |
| `uv sync --frozen --all-extras` | PASS | Frozen environment synchronized; pypdf 6.15.0, pytest 9.1.1, Qiskit 2.5.1, and Aer 0.17.2 present. |
| `uv run --frozen ruff check .` | PASS | Exit 0 in 0.073 s; all checks passed. |
| `uv run --frozen ruff format --check .` | PASS | Exit 0 in 0.065 s; 230 files already formatted. |
| `uv run --frozen pytest --cov=app.services --cov-report=term-missing --cov-fail-under=80` | PASS | 388 passed in 59.10 s; command duration 61.091 s; total service statement coverage 83.41%, above the 80% gate. |
| `uv run --frozen pytest tests/test_migrations.py` | PASS | 4 passed in 3.00 s; command duration 3.909 s. |
| `uv run --frozen python scripts/export_openapi.py --check` | PASS | Exit 0 in 1.790 s; checked contract is current. |
| `uv run --frozen python scripts/generate_frontend_contracts.py --check` | PASS | Exit 0 in 0.113 s; checked frontend contract is current. |
| `uv run --frozen --with pip-audit==2.9.0 pip-audit --skip-editable` | PASS | Exit 0 in 2.233 s; no known vulnerabilities; editable `quantumlearn-api` intentionally skipped. |

## Frontend verification

Commands were run from `src-main/frontend` with Node 22.13.0 and npm 10.9.0.

| Command | Result | Duration and exact evidence |
| --- | --- | --- |
| `npm ci` | PASS | Exit 0 in 5.386 s; 338 packages installed, 339 audited, zero vulnerabilities, and no engine warning. |
| `npm run lint` | PASS | Exit 0 in 20.593 s. |
| `npm test` | PASS | 8 files and 59 tests passed; command duration 22.554 s. jsdom emitted six `HTMLCanvasElement.getContext` not-implemented diagnostics; assertions still passed. |
| `npm run build` | PASS | TypeScript and Vite production build passed in 7.995 s; 284 modules transformed. |
| `npx playwright install --with-deps chrome msedge firefox webkit` | PASS WITH LOCAL NOTE | System Chrome/Edge were already installed. Managed Firefox/WebKit were then installed explicitly because the combined Windows command stopped after reporting Chrome. No repository file changed. |
| `npm run test:e2e` | PASS | 20 of 20 passed in 35.2 s; command duration 39.507 s: five scenarios each on Chrome Stable, Edge Stable, Firefox, and WebKit. |
| `npm audit --audit-level=high` | PASS | Exit 0 in 0.931 s; zero vulnerabilities. |
| `npm audit --omit=dev --audit-level=high` | PASS | Exit 0 in 0.914 s; zero vulnerabilities. |

## Repository and privacy verification

| Command | Result | Scope and limit |
| --- | --- | --- |
| `python src-main/scripts/validate_gap_matrix.py docs/learnlens/implementation-gap-matrix.md` | PASS | 143 canonical rows: FR=39, PD=12, BP=15, NFR=31, AC=22, AT=24. This proves matrix structure, not every requirement. |
| `gitleaks git --redact --no-banner --verbose .` | PASS | Gitleaks 8.30.1 scanned 31 commits and about 9.75 MB in 0.768 s; no leaks found. Output was redacted by command policy. |
| `git diff --check` | PASS | No whitespace errors in the current Step 3 diff. |

## External and manual evidence not established

| Evidence | Status | Owner and release effect |
| --- | --- | --- |
| Native latest Safari on macOS | NOT RUN | Accessibility/browser owner; Playwright WebKit is not native Safari, so NFR18 and AC17 remain incomplete. |
| NVDA, JAWS, or VoiceOver complete-path review | NOT RUN | Accessibility owner; automated Axe/keyboard checks do not prove complete WCAG 2.2 AA. |
| Manual 200%/400% zoom, reflow, contrast, focus, and equivalent circuit/result review | NOT RUN | Accessibility owner; required before claiming NFR4/AC17. |
| Hosted TLS/DNS/deployment and monthly availability | NOT RUN | Operations; blocks NFR6, hosted portion of NFR15/NFR19, and release readiness. |
| Representative 50-user and 100-user load/scale tests | NOT RUN | Operations; blocks NFR7/NFR8. Local E2E is not load evidence. |
| Forced full-application restart and isolated restore drill | NOT RUN | Operations; current unit/integration recovery and backup checks are partial evidence only. |
| External-model accuracy, false-approval/false-rejection, fairness, latency, usage, and AUD cost dataset | NOT RUN | Assessment/research governance; blocks NFR12-NFR14/NFR22/NFR28 and automated evaluator release. |
| Student/educator usability, setup-time, and learnability studies | NOT RUN | Product/research owner; blocks NFR1-NFR3. |
| Full Person B functionality and formal Person A integration | NOT RUN | Steps 4-43; this document is intentionally the pre-feature baseline. |

## Gate conclusion

All locally runnable pre-feature commands are green on the Step 3 working tree. The repository may
proceed to the next planned step, but no external/manual item above is upgraded to PASS, and no
formal assessment implementation or pilot-readiness claim is made by this baseline.
