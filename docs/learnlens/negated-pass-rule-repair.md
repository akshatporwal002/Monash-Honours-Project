# Negated pass-rule repair

Date: 2026-09-06

Branch: `fix/assessment-negated-unknown-evidence`

Starting commit: `85b42d21841a904963736bd1d8d630d6aa1978a1`

## Outcome

Remaining Task 1 is repaired at the `PassRuleEngine.evaluate` boundary.
`ALL_OF(a, NOT(b))` now returns `INCOMPLETE` when mandatory `a` is met and `b` is unknown.
Missing, conflicting, and not-evaluable evidence stay unknown through nested negation.
The cause was reducing unknown evidence to false before applying `NOT`.

## Requirements completed

- Remaining Task 1: preserve uncertainty through nested rules and retain review reasons.
- AT8 and AT9: scoped rule-engine evidence for definite pass rules and incomplete decisions.
  This does not claim complete application acceptance coverage for those requirements.

Changed implementation: `src-main/backend/app/services/assessment/pass_rules.py`.
Regression tests: `src-main/backend/tests/test_pass_rule_engine.py`.
The gap matrix links this evidence as a dated addition to its older baseline.

## Existing behaviour preserved

Definite evidence still resolves Boolean expressions. A false clause resolves `ALL_OF`;
a true clause resolves `ANY_OF`. Unknown optional evidence does not block an independently resolved rule.
Mandatory criteria still require an unambiguous `MET` decision.
Evidence lists, conflict reasons, missing-evidence reasons, and public contracts remain intact.

## Data changes

No schemas, migrations, stored records, or public contracts changed.
Existing assessment history is untouched; this repair applies to future rule evaluations.
Recovery means reversing only this feature's code and test diff after review.
That would restore the known defect, so keep affected negated rules under human review if rolled back.

## Verification

Commands ran from `src-main/backend` using Python 3.11.15.

- Before the fix: `.venv/Scripts/python.exe -m pytest tests/test_pass_rule_engine.py -k negation_preserves -q`
  produced **6 failed, 3 passed**. Failures included the exact reported `NOT_EVALUABLE` trigger.
- After the initial fix: `.venv/Scripts/python.exe -m pytest tests/test_pass_rule_engine.py -q`
  produced **30 passed** before adding compound and mandatory-boundary cases.
- Final targeted run: **68 passed**, including **41 pass-rule cases**.
- `uv lock --check` and `uv sync --frozen --all-extras`: passed after an access-enabled retry.
- `.venv/Scripts/ruff.exe check app/services/assessment/pass_rules.py tests/test_pass_rule_engine.py`: passed.
- `.venv/Scripts/ruff.exe format --check app/services/assessment/pass_rules.py tests/test_pass_rule_engine.py`: passed.
- `git diff --check`: passed.
- Separate Standards and Spec agents reviewed the actual uncommitted two-file diff against the starting commit.
  Both reported zero findings. Reviews were static, with runtime proof supplied by the commands above.

Final targeted test command and isolated configuration:

```powershell
$env:APP_ENV = 'test'
$env:DATABASE_URL = 'sqlite://'
$env:LEARNING_EVENT_PSEUDONYM_SECRET = 'ci-only-pseudonym-secret-32-bytes-minimum'
$repairTemp = Join-Path $env:TEMP ('learnlens-negation-' + [guid]::NewGuid().ToString('N'))
.venv/Scripts/python.exe -m pytest tests/test_pass_rule_engine.py tests/test_assessment_evaluation_api.py tests/test_assessment_evaluation_jobs.py tests/test_assessment_definitions.py tests/test_assessment_submissions.py --basetemp $repairTemp -q --tb=short
```

Initial setup failures were resolved: uv cache/network access needed an access-enabled retry,
and pytest's existing shared temp directory denied access. A fresh unique temp directory fixed the latter.
An earlier command named a nonexistent `test_assessment_evaluation.py`; no tests ran for that command.
The final command uses the actual API and job test files.

## Open items

Remaining Task 2, evaluator settings and approval validation, is the next assessment repair.
The rest of the immediate batch remains open under the existing handoff.

## Limits

Full backend coverage, frontend, browser, hosted, provider, dependency audit, and release checks were not run.
No manual UI check applies to this internal rule-engine change.
No commit, push, merge, deployment, or live database operation was performed.

