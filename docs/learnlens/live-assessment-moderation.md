# Live assessment moderation and evaluator revalidation

Implements the software workflow in BP9/BP11 and assessment specification §17.
Task 8 D-01, D-07 and D-09 still control visibility, AI release and policy activation.
No migration, test or example supplies an institutional approval or evaluator release.

## Course moderation

An authorised course assessor records a versioned policy with explicit initial
double-review count, later sampling percentage, drift interval, approval reference,
training/shared-anchor reference and expiry. The form supplies no numeric defaults.
The proposed 20/25%/50 settings are not adopted automatically.

An active policy captures each new assessment attempt's eligibility in its submission
transaction. The retained record includes policy ID, task family, family response
sequence, selection and drift flags. Initial responses use their chronological family
sequence; later sampling uses a deterministic hash of policy and attempt IDs.
Drift checkpoints always require review. Opening the queue also captures eligible
pending attempts that predate policy activation. Policy replacement cannot reroll
existing selections. Expiry leaves existing selected reviews visible and enforceable.

The existing assessor workspace contains **Open assessment moderation**. Reviewers
inspect the frozen response, conditions, criterion rules and approved anchors using
the human assessment form. Each stage retains actor, time, result, reasons and exact
criterion/evidence references. The second reviewer must be a different authorised
assessor. A third assessor resolves a PASS/INCOMPLETE disagreement. Drift disagreement
has a separate resolution stage and invalidates a previously validated evaluator.
Prospective second reviewers receive no prior judgement history or criterion decisions
from the moderation queue and human evidence response until they submit their independent
decision. Drift resolution excludes the authors of both sides of that disagreement.

After formal confirmation, **Start correction review** opens another numbered moderation
cycle. It records the proposed correction as a new original decision, requires another
independent second review and any disagreement resolution, and then permits a separate
human confirmation/override. The existing learner-visible formal result remains in place
while correction is pending. Original cycles remain immutable, and repeated corrections
retain separate action keys and request digests.

Moderation decisions do not confirm a formal result. Both ordinary review actions and
human criterion confirmation enforce required moderation stages and the resolved
result. Learners cannot see these provisional moderation records. Scoped grants are
rechecked under the course write lock, and history cannot be updated, deleted or
replaced. Repeating an identical recorded stage returns its existing receipt.
Policy, review and evaluator-validation writes also append correlated platform audit
events in the same transaction, including actor, result and relevant policy/rule/model
version information. All five moderation/validation endpoints expose typed response
models for generated API contracts.

When no policy has ever been activated, the moderation queue reports
`POLICY_REQUIRED`; established human confirmation continues without being labelled
moderated acceptance. This follows D-09's outstanding sampling approval rather than
inventing a policy or disabling all existing human assessment. An expired configured
policy blocks new sampling eligibility until renewed. Already confirmed unmoderated
results retain their correction rights when a policy is later introduced.

## Evaluator validation ledger

An administrator can record externally approved validation evidence through
`POST /assessment/courses/{course_id}/evaluator-validation`. It requires the exact
current fingerprint, signed release and expert/case/agreement/fairness/revalidation
references, explicitly approved error limits, measured false-pass and false-incomplete
rates within those limits, and a future expiry. No error threshold is supplied by code.
The service records this evidence; it does not independently authenticate external
documents or perform the expert study.

The fingerprint covers task and teaching-review versions, source revision/passage and
approval identities, retrieval chunks, Bloom targets, criteria, pass rules, outcome and
curriculum versions, persisted settings, configured model/retrieval settings, and
backend Python prompt/runtime code. Code paths are relative and line endings are
normalised. Row ordering is fixed. Operational timestamps, local storage keys, the
upload-directory mount setting and processing tokens are excluded; retrieval policy
and retirement/revocation presence remain semantic.
Validation history itself is excluded. Only dependency digests are retained.

ORM material changes append an `INVALIDATED` event in the changing transaction.
Status reads and evaluator entry also check deployed configuration/code and expiry.
Repeated unchanged reads do not append events. Revalidation must reference the current
fingerprint and new approved evidence; earlier validation and assessment records remain
intact. Indirect/shared tables and backend code are conservatively hashed globally,
so another course's indirect source/retrieval or runtime changes can invalidate this
course. This intentionally favours revalidation over a missed dependency; it is not
course-local invalidation isolation.

Validation and operational activation remain separate. The existing runtime still
uses the human/rules path, AI activation remains `PENDING`, and D-07's operational AI
suggestion gate is not enabled by recording a ledger event. The 108-case validation
artifacts and study ratings are unchanged; their provenance refresh belongs to the
coordinator.

## Migration and verification

Migration `20260911_0049` adds four tables without backfilled approvals. Downgrade
refuses populated governance history. Its predecessor must follow the coordinator's
integrated migration ordering.
The migration also permits another reasoned override of an already overridden result,
while retaining the requirement for a matching append-only assessor action and a changed
result. Its original lifecycle trigger is restored only on an empty-governance downgrade.

Focused tests in `test_live_assessment_moderation.py` cover policy eligibility,
independent reviewers, original/second/resolved decisions, both confirmation entry
points, expiry, drift resolution, route permissions/replay, validation changes and
stable reads, exact source history, and populated forward migration with real submission
sampling. Reviewer component tests cover absent policy values, disagreement/access
states and moderation submission without formal confirmation. Existing human-review
and assessor-review tests remain passing.
Review follow-up regressions in `test_moderation_review_followups.py` cover repeated
correction cycles on a migrated database, blind second-review responses, drift conflict
of interest, correlated audit atomicity and typed response contracts. A deferred-response
panel test verifies that changing course clears prior selection/policy state and rejects
late responses from the previous course.

Actual sampling approvals, trained named reviewers, shared anchors, external validation
measurements, signed release evidence and operational activation records remain required.
