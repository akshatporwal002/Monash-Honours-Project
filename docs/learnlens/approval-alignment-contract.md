# Approval-time feedback and adaptation alignment

BP3 requires prospective links from outcome, Bloom target, activity/task, evidence and criteria through feedback, result and adaptation before approval. Existing outcome, task-form, evidence, criterion and pass-rule checks remain in place. New definition approvals additionally require an explicit versioned `alignment` object inside `next_action_contract`.

The assessor supplies the declarations. They describe the intended feedback and adaptation; they are not learner records, result overrides, generated feedback, or executable routing instructions. Publication does not require a learner to have submitted work. The existing result and adaptation services retain their decision boundaries.

## Version one shape

```json
{
  "when_incomplete": "Existing next-action policy may remain here.",
  "alignment": {
    "schema_version": 1,
    "criterion_feedback": [
      {
        "criterion_key": "existing_stable_criterion_key",
        "evidence_source_types": ["learner_response"],
        "met": "Assessor-authored feedback plan for evidence meeting this criterion.",
        "not_met": "Assessor-authored feedback plan for evidence not meeting this criterion.",
        "not_evaluable": "Assessor-authored plan explaining unavailable or unusable evidence."
      }
    ],
    "result_adaptation": {
      "PASS": {
        "feedback": "Assessor-authored explanation linking criterion decisions to the pass rule.",
        "adaptation": "Assessor-authored next learning action, or explicit reason none is needed."
      },
      "INCOMPLETE": {
        "feedback": "Assessor-authored explanation of the evidence missing under the pass rule.",
        "adaptation": "Assessor-authored next learning or reassessment action."
      }
    }
  }
}
```

This illustrates the fields, not an approved curriculum or ready-to-publish policy. Every current criterion, including optional criteria, must appear exactly once by its stable key. Each feedback entry must name exactly that criterion's declared evidence source types without duplicates. Both result branches and all three criterion decision plans are required. Descriptions must be nonblank strings of at most 4,000 characters. The version-one contract permits at most 256 criterion entries and 64 evidence types per entry; references are at most 255 characters. Unknown fields inside `alignment` and unsupported schema versions are rejected. Other `next_action_contract` metadata is preserved.

## Authoring and compatibility

Incomplete policies can still be saved as drafts. Approval rejects missing, malformed or mismatched links with a validation error before changing any approval state. Adding/removing a criterion or changing its evidence types requires updating the declarations before approving the new version. The advanced definition editor's **Next action and review policy** JSON field displays a required structure using the current criterion keys and evidence types, with empty descriptions for the assessor to fill. It preserves existing policy metadata; no automatic curriculum choices are supplied.

After saving a simple setup, **Complete feedback and adaptation in definition editor** opens its saved course, definition and version for completion. The button is disabled while local changes are unsaved, a request is pending, or the version is stale. Generated saves retain their existing direct editor route and complete multi-criterion content. Both paths require the assessor to complete the declarations before publication.

Existing approved versions retain their original immutable JSON and remain readable. Their frozen metadata is not silently backfilled. The new gate applies when a new definition version is approved, including revisions derived from historical versions. Equivalent-form publication continues using the existing construct checks against its already approved definition; this change does not retrospectively require editing that frozen definition.

Focused tests cover complete declarations, missing/invalid/versioned fields, criterion and evidence identity mismatches, missing result branches, preservation of opaque metadata, atomic rejection, and a new approval alongside an unchanged historical definition. Validation checks structure and references; the assessor still reviews the educational substance.
