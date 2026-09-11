# Versioned assessor definition editor

The assessor workspace can load existing definitions and revise their complete set of criteria. Saving a generated assessment draft opens the matching editor automatically, using the saved course and definition identity. Existing single-criterion setup remains available.

The editor preserves stable criterion keys, approved anchors, critical-error rules, evidence sources, evaluator selection, Bloom and knowledge targets, eligibility, task forms, nested policies and other supported metadata. Stored criterion-version references are translated back to stable keys for the versioned write API. New criterion keys avoid all identities in loaded history. A referenced criterion cannot be deleted until its rule references are removed. Boolean conditions have controls for all, any and not; opaque policy objects and lists have advanced structured editors.

Saved changes create a new unapproved version. Published definitions are read-only until the assessor starts a revision. Approval requires a saved draft, an explicit review acknowledgement and an approval reason; the server retains responsibility for publication readiness and authority. A conflict preserves the full local form, disables save/approval and permits history inspection followed by explicit replacement with a server version. Reloading history alone does not replace local edits.

The definition authoring response now includes `outcome_id` and a dedicated `AssessmentAuthoringCriterionRead` with anchors and critical-error rules. Learner criterion reads retain their previous fields. No storage or migration changes are involved. Root integration owns regeneration of the canonical OpenAPI and TypeScript contracts.

## Boundaries

- Existing versioned writes capture the current teaching-task revision and refresh source version/digest. The editor explains this behavior; frozen published forms remain unchanged. Exact historical task-revision selection is not a supported draft input.
- Editing existing task forms preserves their number and task identities. The UI permits editing their family, context and constraints; adding or replacing task forms is outside this editor's scope.
- Definition history is opened by ID for existing records. Generated saves supply that identity automatically; no course-wide definition search endpoint was added.
- Supported opaque metadata is retained without interpretation. Invalid or missing authoring metadata is rejected rather than filled with empty anchors or guessed policies.

## Focused verification

- Editor regression coverage: multi-criterion metadata round trip, add/remove references, required fields and invalid structured data, stale save/history/reload, frozen revision and explicit approval, safe error reporting, stable-key reservation, and generated save opening all five criteria.
- Existing setup and generated-preview regressions retained.
- Authoring API checks cover owner and scoped-assessor reads, private metadata round trips, creation of an unapproved revision, unchanged published history and unauthorized history access.
- Learner task reads assert that anchors and critical-error rules are absent.
- TypeScript and scoped frontend/backend lint checks; no broad test suites or browser checks.
