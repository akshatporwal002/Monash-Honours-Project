# NNN: Plan title

Status: proposed

Owner: unassigned

Created: YYYY-MM-DD

Target branch: verified branch name

## Outcome

State the user-visible or system result. Name what is outside this plan.

## Source evidence

| Claim or rule | Evidence | Requirement |
| --- | --- | --- |
|  | `path:line` or symbol/test | FR, PD, BP, NFR, AC, or AT ID |

## Current-state trace

Trace input, permission checks, service calls, stored data, output, audit, and failure handling. Mark gaps as `MISSING`, `CONFLICTING`, or `UNVERIFIED`.

## Proposed design

Describe boundaries, data contracts, version rules, and key choices. Add a small diagram only when it makes the flow clearer.

## Step 1: One reviewable change

Files:

- `path/to/file`

Changes:

- [ ] Add or change one defined behaviour.
- [ ] Add its migration or compatibility handling when needed.
- [ ] Add named unit or integration tests.
- [ ] Update linked contracts and docs.

Edge and failure cases:

- State the cases and expected safe result.

**Acceptance:** Name the test, command, runtime proof, or visible result that closes this step.

## Step 2: Next reviewable change

Repeat the same fields. Split unrelated work into another step.

**Acceptance:** Give observable proof for this step.

## Full verification

List the smallest checks for each step, then the release checks from `.github/workflows/quality.yml`. Include manual browser and access checks when automation cannot prove the claim.

## Migration and rollback

State forward migration, data checks, compatibility window, recovery path, and record-count proof. Write `Not applicable` with a reason when no stored data changes.

## Risks and controls

| Risk | Impact | Control and proof |
| --- | --- | --- |
|  |  |  |

## Missing-data report

List every missing policy decision, real sample, expected output, owner, and blocking effect. Write `None found` only after the evidence pass.

## PR mapping

The implementation PR must mirror every plan step, checklist item, acceptance line, verification result, risk, and open item.
