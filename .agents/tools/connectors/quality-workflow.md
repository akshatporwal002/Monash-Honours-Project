# Quality workflow connector

The source of truth is `.github/workflows/quality.yml`. Map its jobs to `.agents/workflows/quality-checks.md` for local runs.

Required job groups are:

- Backend Python 3.11 checks.
- Frontend Node 22 checks and browser E2E.
- Python and npm dependency audits.
- Gitleaks secret scan.

Record results against the current head SHA. Treat pending, cancelled, skipped, stale, or unavailable checks as not passed.
