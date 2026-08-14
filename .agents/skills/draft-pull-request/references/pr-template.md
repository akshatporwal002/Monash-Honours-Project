## Outcome

State what now works and what remains outside scope.

## Source and requirements

| Requirement | Source evidence | Implementation evidence |
| --- | --- | --- |
|  | `docs/...` | `path`, symbol, migration, or test |

## Plan execution

Plan: `docs/plans/NNN-slug.md`

### Step 1: Copy the plan step title

- [ ] Copy every checklist item and mark its real state.
- [ ] Add file and test proof beside each item.

**Acceptance:** Copy the plan acceptance line, then state the result and evidence.

Repeat for every plan step without merging or omitting steps.

## Data and compatibility

State migrations, backfills, generated contracts, compatibility, rollback, record checks, or why each does not apply.

## Verification

| Check | Result | Evidence or limit |
| --- | --- | --- |
| Small targeted test | PASS, FAIL, or NOT RUN | Command and key output |
| Backend release checks |  |  |
| Frontend release checks |  |  |
| Browser and access checks |  |  |
| GitHub quality workflow |  |  |

## Agent gates

| Gate | Verdict | Findings or evidence |
| --- | --- | --- |
| Test Judge |  |  |
| Code Reviewer |  |  |
| Code Quality Reviewer |  |  |
| GitHub Workflow Agent |  |  |

## Risks and open items

List each risk, owner, and next action. State `None` only after checking the plan and review outputs.

## Review readiness

- [ ] Plan and diff match.
- [ ] Step acceptance is complete.
- [ ] Required tests and CI pass.
- [ ] Blocking agent findings are closed.
- [ ] Known limits are visible.
