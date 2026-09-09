# Task 21: curriculum and diagnostic paths

Task 21 starts from main `65a9457` plus the uncommitted Task 20 dependency.
The original Task 20 worktree remains unchanged. Its 38 inherited files and hashes
are recorded in `.tmp-task21/task20-baseline.json`. No commit or remote write is authorised.

## Contract and scope

An educator publishes an immutable, outcome-scoped pathway version. Each step links
a concept, an approved task revision, source approvals, prerequisites, and an exit rule.
There must be at least three ordered tasks. Existing formal task forms and assessment
rules remain authoritative. A diagnostic cannot bypass them.

The graph records bounded support levels and a lower optional support level after
confirmed diagnostic success. Learners can still request approved help. Personalisation
opt-out stops optional fading, without changing the pathway's required conditions.

Each learner diagnostic start freezes its pathway version, target, prompt, and independent
conditions. Submission captures prior knowledge, reasoning, confidence, uncertainty about
the concept, and requested support as protected learning evidence. It creates no grade.
The provisional state always requires human review. Only a current course assessor can
confirm a practice bypass, with a reason and verified independent conditions.

Immutable versions, starts, submissions, and confirmations use unique request receipts.
Replays return the original record. Conflicting keys or stale versions return 409.
Evidence and diagnostic submission commit together. Reads never create records.

Task 22's durable feedback continuation and activity recommendation adapters remain separate.

## Verification links

| Requirement | Required proof |
| --- | --- |
| FR10, PD2 | Three-step graph, approved revision/source links, invalid and cyclic prerequisites rejected |
| FR11 | Learner-requested diagnostic, frozen target and conditions, current assessor grant, explained practice-only bypass |
| PD1 | Initial offer, persisted evidence, no formal decision or grade |
| FR35-FR37 | Optional fading honours preferences and retains approved help |
| NFR31 | Strict contracts, observed responses only, no inferred sensitive traits |
| History and safety | Replay, stale requests, rollback, protected rows, revoked approval, course and actor scope |

Run focused tests, migration checks, contract generation, backend and frontend gates.
Perform Standards, Spec, and Test Judge self-reviews, respecting the user's ban on sub-agents.
