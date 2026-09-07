# Task 15 human assessment handoff

Task 15 makes attempts without a decision reachable by a scoped assessor. The assessor inspects frozen evidence, records each criterion decision and reason, and confirms the result from the saved pass rule.

## Behaviour

- The unresolved queue includes pending, review-required, and faulted work. It has bounded API pages and a load-more control.
- Review shows the complete supported response, prediction, reasoning, explanation, reflection, revision history, and separate transfer response. Code keeps whitespace. Simulations show exact inputs, shots, seed, versions, state, and outcome.
- Both unresolved work and the selected existing review record offer human criterion entry. Every criterion requires an explicit decision, reason, and approved evidence reference.
- Human decisions use human actor/action provenance. Existing automated rows remain unchanged. Corrections append history and follow the existing result lifecycle.
- A valid frozen standard stays available for explicit human review after a later rule is published. Automatic evaluation retains its stale-version conflict behaviour.
- Invalid, missing, stale, foreign, pending, and failed technical evidence blocks formal confirmation. It does not create an INCOMPLETE result.
- A course lock, complete job snapshot token, conditional job claim, and worker lease checks fence competing writes. A repeated action key returns its original receipt; changed content or stale state conflicts.
- The first provisional calculation and audited CONFIRM share one transaction. No provisional result becomes learner-visible between those steps.

## Circuit boundary

Strict approved `circuit_v1` rules compare qubit count and ordered h/x/cx operations for the declared supported or transfer stage. Known shots and seed metadata is validated but does not affect structural equality. Unknown circuit fields remain unsupported. These checks make no claim about conceptual mastery or probability distributions.

MIXED circuit criteria require human assessment. The shared publication gate permits only the strict deterministic-plus-human circuit path. VALIDATED_AI and all other MIXED paths remain blocked. D-07 operational AI suggestions and D-01 hidden provisional results remain in force.

## Local evidence

- Backend scoped regression run: 69 tests passed across Task 15 circuit/human/migrated/route tests and existing assessment evaluation, job, and review API tests.
- Follow-up worker tests: 10 human tests passed, including replaced claims and leases that expire during evaluation. Both leave no criterion or formal decision rows.
- Frontend: 16 tests passed across new human-review and existing assessor-review tests. Two further UI retry tests passed, covering retained entries, network replay keys, and refreshed conflict keys. TypeScript, ESLint, and the production build passed.
- Real Chrome journey `e2e/task15-human-review.local.mjs`: ordinary educator login, persisted unresolved job, full multipart and earlier evidence, keyboard inspection and confirmation, human provenance after reload, zero Axe violations, and no browser page errors.
- Browser evidence is isolated under `src-main/backend/.tmp-task15/browser02/`. The final result screenshot was inspected after the queue settled.
- Migrated database tests exercise append-only update/delete/replace guards, repeat migration, protected downgrade refusal, foreign-key checks, simultaneous human actions, expired workers, and read-only evidence reads.

The local tests use synthetic fixtures and isolated SQLite databases. They do not establish educational validity or release approval. Independent review and combined integration gates remain coordinator-owned.

## Dependencies and rollback

The branch consumed pure episode contract `d8a26e989c7a04f7b2de8fe869725962e45f234f`, then foundation and reviewed-plan wiring `dca96f9bea4570d9e9050af4805092b01df86e7f` through separate merges. Migration 0031 follows Task 14 migration 0030 and adds real human history tables and guards.

A downgrade refuses to delete recorded human assessment history. Restore a verified backup for rollback after data exists. Do not erase assessor decisions to force a downgrade.

The coordinator owns shared authoring, generated contracts, final migration ordering, independent review, push, and integration. Task 14 migration and historical-condition fixes were consumed at `9100121a3628179ccf7c0e819ab2be189281f875`. Its final typed-state and checkpoint-page changes were consumed at `3f329acdb534ca065059e0b15963798a68dd8141`. Combined release gates remain coordinator-owned.

## Independent review fixes

Both P2 findings are addressed. The assessor sees the exact reviewed task revision, supported and fresh transfer questions, starter content, frozen outcome wording, Bloom target, and pass-rule expression. Current mutable teaching content is never substituted.

Each earlier response has its own validated simulation inputs, versions, outcomes, and fault status. Historical technical faults remain visible without blocking a complete later response. Current required evidence still blocks unsafe confirmation. Both unresolved and existing review APIs use the same read-only evidence reader.

The P3 circular private coupling was removed. The human service uses a public review transaction operation for confirmation. Existing review reads use the independent frozen evidence reader.

Review-fix checks passed: 37 backend tests, 19 frontend tests, Ruff, ESLint, and production build. The fresh browser04 journey inspected both questions, the pass rule, and an earlier-only completed simulation before recording all three criterion decisions. Keyboard actions, reload, human provenance, zero Axe violations, and zero browser page errors passed. Its frozen-evidence screenshot was inspected.

After the final typed-state dependency merge, the expanded regression run passed 76 backend tests. TypeScript and all 19 review UI tests also passed. Later Task 14 review fixes remain separately tracked by the coordinator.
