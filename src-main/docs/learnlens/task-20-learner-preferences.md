# Task 20: Learner preferences

## Outcome

Authenticated learners can read and replace a complete set of explicit presentation and optional-support choices at `/students/me/preferences`. A guarded `/student/preferences` page and independent TaskView summary expose the same learner-owned state.

## Boundaries

Preferences are closed, non-diagnostic choices for pace, format, explanation detail, optional breaks, repeat practice, and non-essential personalisation. They are neither accessibility support nor instructional help and are not accepted by assessment, draft, checkpoint, transfer, submission, or feedback interfaces.

## Persistence and recovery

Each save appends a complete immutable revision, with learner-local ordering and idempotency keys. Reads without history return unsaved defaults. Stale writes and inconsistent retry keys return conflicts; an empty table may be downgraded, while populated preference history refuses downgrade.

## Verification

`test_task20_formal_result_isolation.py` first failed on the feature-less branch, then passed after implementation. It proves preference corrections before and after assessment evaluation do not alter frozen response references or create additional criterion/decision rows.

## Follow-on work

Task 22 may consume this module through a read-only, non-essential adaptation seam. It must not introduce a dependency from formal assessment to preference persistence.
