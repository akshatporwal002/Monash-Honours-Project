# Before implementation hook

Run before editing product code, migrations, configuration, or CI.

- Confirm `git status` was inspected.
- Confirm the three controlling docs were read for the affected requirement.
- Confirm current behaviour was traced through code and tests.
- Confirm gaps and missing policy are recorded.
- Confirm `docs/plans/NNN-<slug>.md` exists.
- Confirm the planned step has files, checklist items, tests, and acceptance proof.

If any item fails, block implementation and return to grounding or planning.
