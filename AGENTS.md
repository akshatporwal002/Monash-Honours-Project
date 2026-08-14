# LearnLens agent instructions

Read `.agents/instructions/core.md` before changing this repository. Use `.agents/workflows/change-delivery.md` for every code, configuration, migration, or workflow change.

The required order is evidence, written plan, implementation, tests, local agent reviews, then human PR review. Do not request PR review while a gate is missing or failed.

Use the three root files under `docs` as the controlling product specifications. Prove current behaviour from code and tests under `src-main`. Preserve unrelated work and report any check that did not run.
