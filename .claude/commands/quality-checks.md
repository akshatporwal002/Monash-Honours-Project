---
description: Run the local checks that mirror CI, backend and/or frontend, and report exact results
argument-hint: [backend | frontend | all — defaults to the changed areas]
allowed-tools: Bash, Read, Grep, Glob
---

Scope: $ARGUMENTS

Changed areas: !`git diff --name-only origin/main...HEAD | cut -d/ -f1-2 | sort -u`

Re-read `.github/workflows/quality.yml` before you claim a full release run — it is the source of truth and
`.agents/workflows/quality-checks.md` is a transcription that can drift.

Backend, from `src-main/backend`:

```
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest --cov=app.services --cov-report=term-missing --cov-fail-under=80
uv run --frozen pytest tests/test_migrations.py
uv run --frozen python scripts/export_openapi.py --check
uv run --frozen python scripts/generate_frontend_contracts.py --check
```

Frontend, from `src-main/frontend`:

```
npm run lint
npm test
npm run build
npm run test:e2e
```

Rules: run targeted checks for the changed area first, then widen. Do not install dependencies, download
Playwright browsers, or hit package registries unless the user authorised it — report that as a blocked
check instead. On Windows use `npm.cmd` / `npx.cmd` if the shims are blocked.

Report a table of command, result (`PASS`, `FAIL`, `NOT RUN`, `BLOCKED`), and scope limit, against the
current head SHA. Never report a check you did not run as passing.
