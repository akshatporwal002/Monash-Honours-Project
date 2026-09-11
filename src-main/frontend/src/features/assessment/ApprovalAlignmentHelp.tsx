import type { AssessmentDraft } from './api'

export function ApprovalAlignmentHelp({ criteria }: { criteria: AssessmentDraft['criteria'] }) {
  const shape = {
    schema_version: 1,
    criterion_feedback: criteria.map((criterion) => ({
      criterion_key: criterion.stable_key,
      evidence_source_types: criterion.evidence_source_types,
      met: '', not_met: '', not_evaluable: '',
    })),
    result_adaptation: {
      PASS: { feedback: '', adaptation: '' },
      INCOMPLETE: { feedback: '', adaptation: '' },
    },
  }
  return <section aria-label="Feedback and adaptation approval requirements">
    <h3>Complete the feedback and adaptation plan before approval</h3>
    <p>In the policy below, add an <code>alignment</code> object with the structure shown here. Keep your other policy fields.
      Every criterion needs a feedback plan for met, not met and not evaluable evidence. Both Pass and Incomplete need a result explanation and an adaptation plan.</p>
    <p>Write each plan in your own words. An adaptation can explicitly explain why no further action is needed.
      Blank descriptions cannot be approved. Drafts can be saved while this plan is incomplete.</p>
    <details><summary>Required alignment structure for these criteria</summary>
      <pre aria-label="Required alignment JSON">{JSON.stringify(shape, null, 2)}</pre>
      <p>These empty fields are a template, not approved policy. Fill every description (maximum 4,000 characters each).
        Keep each current criterion key exactly once and its evidence sources unchanged. Update this mapping if you change criteria.</p>
    </details>
  </section>
}
