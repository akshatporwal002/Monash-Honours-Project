# Define versioned evidence and recovery boundaries

ID: 17
Parent: [LearnLens route to pilot readiness](../map.md)
Label: wayfinder:grilling
Type: grilling
Mode: HITL
Status: open
Direction: accepted
Assignee: unassigned
Blocked by: none
Decision owners: Assessment, evidence, retrieval, and platform owners; names to be recorded
Source tasks: 7, 9, 10, 11, 12, 13, 14, 15, 17, 18, 22, 25, 37

## Question

Which versioned records and processing boundaries preserve a complete learning episode through change, retry, and restart?

- Specify shared references for sources, passages, circuits, runs, assessed conditions, responses, observations, model snapshots, and teaching decisions.
- Design policy version references before concrete policy values are approved. Publication and assessed use still require the relevant approvals.
- Define the exact start-of-work event that freezes assessed conditions and how later rule changes produce an explicit conflict.
- Specify acceptance, processing claims, stale-claim recovery, idempotency, and terminal failure at each boundary.
- Use failure examples across material processing, submission, evaluation, feedback, model update, and next-activity selection. Preserve existing service boundaries where they meet the contract.

A resolution must provide: A bounded cross-service contract and failure table that can feed the implementation spec, including atomic writes and recovery responsibilities.

## Context

- [Versioning and recovery tasks](../../../LearnLens_Remaining_Tasks.md)
- [Assessment specification](../../../docs/02-pass-incomplete-bloom-assessment-spec.md)
- [Worker operations](../../../src-main/docs/worker-operations.md)

## Comments

Charted on 6 September 2026. No answer or policy approval has been recorded.

### Recommended direction accepted

The user accepted this recommended direction in conversation:

Freeze approved assessment versions through an explicit Start assessed task action. Resume saved work safely without duplicate submissions. The detailed technical contract is delegated to the agent.

Still needed to complete this ticket: Design and verify the version references, atomic writes, processing claims, retry limits, stale-claim recovery, and failure cases. Relevant approval gates still apply to assessed use.

The ticket remains open for these details and any required approval evidence.
