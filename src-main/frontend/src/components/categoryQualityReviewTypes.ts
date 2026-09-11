export const qualityDimensions = [
  ['factual_accuracy', 'Factual accuracy'], ['grounding_and_source_use', 'Grounding and source use'],
  ['relevance', 'Relevance'], ['outcome_and_bloom_alignment', 'Outcome and Bloom alignment'],
  ['evidence_rule_alignment', 'Evidence rule alignment'], ['support_and_answer_leakage', 'Support and answer leakage'],
  ['clarity_and_next_steps', 'Clarity and next steps'], ['accessibility_and_inclusive_wording', 'Accessibility and inclusive wording'],
  ['bias_and_unsupported_learner_claims', 'Bias and unsupported learner claims'],
  ['reflection_and_independent_work', 'Reflection and independent work'],
] as const

export type Finding = {
  dimension: typeof qualityDimensions[number][0]
  outcome: 'SATISFIED' | 'VIOLATED' | 'UNVERIFIED' | 'NOT_APPLICABLE'
  basis: 'human'
  reason: string
  evidence_references: string[]
}
export type QualitySubmission = { request_digest: string, findings: Finding[] }
