# LearnLens — Claude Code operating contract

Canonical harness rules live in `.agents/`. This file is the Claude Code entry point; it
summarises the same contract and maps it onto Claude-native tooling. When this file and
`.agents/` disagree, `.agents/` wins and the drift is a bug — fix it.

## Repository map

- Product specs (controlling, read in this order): `docs/01-implementation-requirements.md`,
  `docs/02-pass-incomplete-bloom-assessment-spec.md`, `docs/03-codex-implementation-work-order.md`.
- Application code: `src-main/backend` (FastAPI, SQLAlchemy, Alembic, SQLite, Python 3.11, uv,
  pytest, Ruff) and `src-main/frontend` (React, TypeScript, Vite, Vitest, ESLint, Playwright, Node 22).
- CI source of truth: `.github/workflows/quality.yml`.
- Plans: `docs/plans/NNN-<slug>.md`. Change records: `.agents/context/change-record-template.md`.

Product docs say LearnLens; packages and code still say QuantumLearn. Do not mass-rename.

## Required delivery sequence

Ground → plan → implement → test → independent local review → human PR review.
Full definition: `.agents/workflows/change-delivery.md`.

| Stage | Use |
| --- | --- |
| Ground | `/ground-change` |
| Plan | `/draft-plan` (skill: `draft-implementation-plan`) |
| Implement | one plan step at a time, tests with the behaviour |
| Test | `/quality-checks`, then `/judge-tests` |
| Review | `/review-change` (two independent subagents) |
| PR | `/prepare-pr` (skill: `draft-pull-request`) |

The agent that wrote the code never issues its own test, correctness, or quality verdict — that
is why the reviewers are subagents with no write tools. Any new commit makes affected verdicts stale.

## Hard rules

- Learner results are only `PASS` or `INCOMPLETE`. No learner-facing `FAIL`, no numeric formal grades.
- Formal confirmation requires an authorised assessor. Automated evaluation is provisional.
- Confidence, time, attempts, hints, access support, research state, or game points never lower a result.
- Quality Judge results are a separate namespace from learner assessment.
- Evidence, inference, activity state, formal results, and research data stay distinct.
- Course and learner scope is enforced in services and queries, not only the UI.
- No secrets, direct learner IDs, hidden prompts, or full learner answers in logs, PR bodies, or memory.
- Forward migrations only; keep old data readable until conversion proof exists.
- Full list: `.agents/rules/learnlens-product-constraints.md`, `.agents/guardrails/`.

## Evidence discipline

Cite `path:line`, symbols, test names, requirement IDs (FR, PD, BP, NFR, AC, AT), and exact commands.
Say `NOT RUN`, `UNVERIFIED`, or `BLOCKED` when proof is missing. A build, a route name, or an HTTP 200
proves only its own scope. Never convert a blocked gate into a warning to keep moving.

## Worktree etiquette

Inspect `git status` before editing. Existing changes are user-owned: do not discard, stage, commit,
or reformat unrelated files. Stage explicit paths only.

## Permissions

Read, search, and local edits are normal work. Branch/commit/push/PR writes need the active task to
ask for them. Merge, deploy, force-push, history rewrite, and protection bypass need separate explicit
authority and are denied in `.claude/settings.json`. Source: `.agents/permissions/policy.md`.

## Quality commands

Backend (`src-main/backend`): `uv run --frozen ruff check .`, `ruff format --check .`,
`pytest --cov=app.services --cov-fail-under=80`, `pytest tests/test_migrations.py`,
`python scripts/export_openapi.py --check`, `python scripts/generate_frontend_contracts.py --check`.
Frontend (`src-main/frontend`): `npm run lint`, `npm test`, `npm run build`, `npm run test:e2e`.
Re-read `.github/workflows/quality.yml` before claiming a release run; it is authoritative.
