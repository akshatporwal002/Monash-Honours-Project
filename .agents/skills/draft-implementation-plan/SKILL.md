---
name: draft-implementation-plan
description: Inspect LearnLens source files, trace current behaviour, and write a committed implementation plan under docs/plans. Use for feature work, fixes, migrations, refactors, policy changes, or any request that needs implementation before code changes begin.
---

# Draft Implementation Plan

Create the plan from repository evidence. Do not implement the planned change while using this skill.

## Follow the evidence order

1. Read `.agents/instructions/core.md` and `.agents/rules/evidence-first-delivery.md`.
2. Read the controlling files in this order:
   - `docs/01-implementation-requirements.md`
   - `docs/02-pass-incomplete-bloom-assessment-spec.md`
   - `docs/03-codex-implementation-work-order.md`
3. Inspect `git status` and preserve unrelated work.
4. Locate the affected code, tests, migrations, contracts, and CI steps under `src-main`.
5. Trace the full path from user or job input through storage and services to output.
6. Cite file paths, symbols, test names, and requirement IDs for every current-state claim.

Treat missing proof as `UNVERIFIED`. Do not turn a filename, route name, or test name into proof of behaviour.

## Resolve the scope

State the requested outcome, affected roles, data, interfaces, and requirement IDs. Record assumptions only when evidence supports them. Put unresolved policy, missing samples, and conflicting sources in the missing-data report.

Stop before implementation when missing data changes the product rule, security boundary, migration result, or acceptance test. Ask for that decision instead of inventing a default.

## Write the durable plan

Find the next free three-digit number in `docs/plans`. Create `docs/plans/NNN-<slug>.md` from `references/plan-template.md`.

Every implementation step must be small and independently reviewable. Give each step:

- Exact files or symbols to change.
- The behaviour and data contracts involved.
- Edge, failure, access, audit, and migration cases that apply.
- Its own task checklist.
- A bold `**Acceptance:**` line with observable proof.

Do not use one global checklist in place of step-level acceptance. Keep tests with the step that introduces the behaviour, then list the full verification suite separately.

## Preserve LearnLens controls

Call out any effect on these rules:

- Learner results are only `PASS` or `INCOMPLETE`.
- Bloom targets and evidence rules are assessor-approved and versioned.
- Formal results require authorised assessor action.
- Evidence, inference, progress, research data, and assessment results stay separate.
- Access support cannot lower the assessment standard.
- Accepted work survives external, model, and simulation faults.
- Direct identifiers and full learner answers stay out of general logs.

## Publish the plan

The file is the plan. Chat text is not a replacement.

When the request authorises the normal Git workflow:

1. Stage only the plan file.
2. Commit it as `docs(plans): add plan NNN <slug> [skip ci]`.
3. Push the plan branch.
4. Open a plan-only PR against the verified target branch.
5. Mirror the plan in the PR body, including every checklist and acceptance line.

Never include unrelated working-tree changes. If authentication, approval, or repository state blocks publishing, leave the plan file intact and report the exact pending Git actions.

## Check before handoff

- Confirm every claim has file or runtime evidence.
- Confirm every requirement ID maps to a plan step and named test.
- Confirm the plan covers data migration, rollback, access, privacy, audit, and failure handling when relevant.
- Confirm exact local and CI commands come from repository configuration.
- Confirm each step has a checklist and acceptance line.
- Confirm missing facts are reported, not guessed.
