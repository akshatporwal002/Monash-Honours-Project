# Project facts

Checked: 2026-08-14

- Product rules are controlled by the three numbered files under root `docs`.
- Application code is under `src-main`, not the repository root.
- The backend uses FastAPI, SQLAlchemy, Alembic, SQLite, Python 3.11, uv, pytest, and Ruff. Source: `src-main/backend/pyproject.toml` and `src-main/README.md`.
- The frontend uses React, TypeScript, Vite, Vitest, ESLint, Playwright, Node 22, and npm. Source: `src-main/frontend/package.json`.
- CI is defined in `.github/workflows/quality.yml`. It checks backend tests with 80 percent service coverage, migrations, contract drift, frontend lint, tests, build, browser E2E, dependency audits, and secrets.
- The current GitHub default branch is `main`. Recheck the remote before opening a PR.
- Product docs use the name LearnLens. Existing package, code, and README names still include QuantumLearn or `quantumlearn`. Do not mass rename them without a scoped plan.
- The backend already contains LMS, RAG, feedback, Quality Judge, research, analytics, audit, worker, and Qiskit-related code. Names alone do not prove full requirements.

These facts are a starting index. Current files and runtime proof always win.
