# LearnLens route to pilot readiness

Label: wayfinder:map
Status: open
Created: 2026-09-06
Tracker: local Markdown

## Destination

Settle the decisions needed for an implementation-ready plan covering all 41 remaining LearnLens tasks through pilot readiness.
Use one complete quantum learning loop as the first delivery milestone, then hand the decisions to `/to-spec` and `/to-tickets`.

## Notes

The user confirmed this destination on 6 September 2026. The team has five members.
Work need not be split evenly. Plan by dependencies and relevant skills; no delivery date is imposed by this map.

The user accepted the recommended directions, then settled legacy score and client retirement through a separate decision.
Each accepted direction and its remaining details are recorded in its ticket; completed decisions are indexed below.
These choices settle the stated direction; missing criteria, named approvals, and execution evidence remain open.

Read the [remaining tasks](../../LearnLens_Remaining_Tasks.md) for the work order and acceptance checks.
The audit covers code at `d049eef`. At charting, local `main` was `b8b4b75`; only the two supplied planning documents differ.
No new runtime, CI, provider, hosted, or study evidence was collected while charting.

Use [Wayfinder](../../.agents/skills/wayfinder/SKILL.md) to work this map.
For a decision conversation, use [grilling](../../.agents/skills/grilling/SKILL.md) and [domain modeling](../../.agents/skills/domain-modeling/SKILL.md).
Read the [domain glossary](../../CONTEXT.md) when discussing learner evidence, estimates, or formal results.
Consult the [requirements](../../docs/01-implementation-requirements.md), [assessment specification](../../docs/02-pass-incomplete-bloom-assessment-spec.md), and [work order](../../docs/03-codex-implementation-work-order.md) when settling a contract or gate.
The [proposed architecture](../../LearnLens_Architecture_and_Sources.md) supplies the first-loop boundary and modular backend direction.

The [policy register](../../docs/learnlens/known-limits-and-deferred-decisions.md) keeps its existing fixed rules.
All twelve policy entries remain pending at charting. A team member is not assumed to hold any approval role.
Record the exact owner, approval evidence, scope, version, and effective date when a policy decision is resolved.

The build tasks already specify immediate repairs, feature work, and release checks. They are not duplicated as decision tickets.
The immediate repairs remain available for separate implementation work; only the relevant policy can block dependent activation.
For the first loop, distinguish a bounded slice from completing every broad prerequisite heading.
Human assessment or advisory evaluation can support that loop while the separate AI assessment release gate remains unmet.

Each file in [decision tickets](issues/) holds one question. Its `Source tasks` field links it to the existing work order.
Use the [local tracker rules](../../.agents/skills/setup-matt-pocock-skills/issue-tracker-local.md) to find the next open, unblocked, unclaimed child.
Claim before work. Resolve through the required human exchange, append the answer to that child, then add its named link below.
Store each decision in its ticket; link policy approval records to that answer rather than copying it.
Planning approval does not replace later validation, ethics, or release evidence. Keep a register entry pending while its own requirements remain unmet.

Charting resolved no child tickets. Follow-up directions are recorded without closing tickets whose completion requirements remain unmet.
The map is ready for handoff only when every planning question and in-scope unknown is settled.
The implementation spec must account for every remaining task, including final evidence on the tested commit.
The map itself does not approve deployment or pilot activation.

## Decisions so far

<!-- Append one named link and a short gist for each resolved child. -->

- [Approve legacy score and client retirement](issues/11-legacy-score-retirement.md#answer): retire immediately with no compatibility window; preserve protected history and verify the coordinated change.

## Not yet specified

- Additional outcome-specific decisions after the first loop has a defined scope and approved evidence rules.
- New failure cases exposed by the shared evidence and recovery contract.
- Further teaching decisions exposed by conflicting learner evidence or unsuitable next activities.
- Concrete interaction prototypes revealed by the learner workflow discussion.
- External research questions exposed by the study design, privacy plan, evaluator protocol, or chosen provider environment.

## Out of scope

- Implementing the 41 build tasks during this planning effort. Its destination is a plan ready for implementation.
- Collecting live study data, running release experiments, deploying, or activating the pilot during charting.
- A requirement to split work equally among the five members.
- Reopening fixed assessment rules or adding separate agent servers and a new database without evidence.
