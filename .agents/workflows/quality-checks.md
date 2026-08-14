# Quality checks

These commands mirror `.github/workflows/quality.yml` as of 2026-08-14. Re-read that workflow before each release run.

## Backend

Run from `src-main/backend`:

```powershell
uv lock --check
uv sync --frozen --all-extras
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest --cov=app.services --cov-report=term-missing --cov-fail-under=80
uv run --frozen pytest tests/test_migrations.py
uv run --frozen python scripts/export_openapi.py --check
uv run --frozen python scripts/generate_frontend_contracts.py --check
```

Set the same test environment values used by CI when a command needs them. Never use production credentials.

## Frontend

Run from `src-main/frontend`:

```powershell
npm ci
npm run lint
npm test
npm run build
npx playwright install chrome msedge firefox webkit
npm run test:e2e
npm audit --audit-level=high
npm audit --omit=dev --audit-level=high
```

Use `npm.cmd` and `npx.cmd` on Windows when PowerShell blocks the script shims.

## CI-only and manual proof

The workflow also runs Python and npm dependency audits plus Gitleaks. Browser and WCAG claims still need recorded manual keyboard, focus, zoom, reflow, screen-reader, and equivalent-circuit checks where the controlling docs require them.

Do not install tools, download browsers, or access package registries without the permission needed for network and filesystem writes.
