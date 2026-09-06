# Define learner evidence and model-update rules

ID: 15
Parent: [LearnLens route to pilot readiness](../map.md)
Label: wayfinder:grilling
Type: grilling
Mode: HITL
Status: open
Direction: accepted
Assignee: unassigned
Blocked by: 01, 06
Decision owners: Teaching specialists and learner-services owner; names to be recorded
Source tasks: 14, 17, 18, 19, 20, 27, 29, 34

## Question

How will observations support or contradict learner estimates in the first complete loop?

- Define evidence types, help context, recency, uncertainty, and rule versions for each estimate.
- Specify how predictions, reasoning, revisions, feedback use, and transfer affect estimates, including conflicting observations.
- Define the effects of learner annotations and educator corrections while preserving original evidence.
- Give examples where an estimate changes a teaching decision, and cases where evidence is insufficient.

A resolution must provide: A reviewable set of inference rules and examples, with evidence links, correction effects, and uncertainty labelled as unvalidated until tested.

## Context

- [Evidence and learner-model tasks](../../../LearnLens_Remaining_Tasks.md)
- [Evidence and learner estimates](../../../LearnLens_Architecture_and_Sources.md)
- [Current learner-model contracts](../../../src-main/backend/app/services/learner_model/contracts.py)

## Comments

Charted on 6 September 2026. No answer or policy approval has been recorded.

### Recommended direction accepted

The user accepted this recommended direction in conversation:

Use explicit, reviewable learner-model rules with evidence links and uncertainty. Include improvement, conflicting evidence, and insufficient-evidence examples.

Still needed to complete this ticket: Specify the actual inference rules, evidence types, help context, recency, correction effects, and validation examples.

The ticket remains open for these details and any required approval evidence.
