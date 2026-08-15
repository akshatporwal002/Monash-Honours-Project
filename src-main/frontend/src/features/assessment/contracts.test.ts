import {
  assessmentPurposeValues,
  assessmentResultValues,
  bloomKnowledgeValues,
  bloomProcessValues,
  criterionDecisionValues,
  misconceptionStateValues,
  qualityReviewDecisionValues,
  resultStateValues,
  submissionStateValues,
} from './types'

test('assessment contracts match generated wire values', () => {
  expect(assessmentResultValues).toEqual(['PASS', 'INCOMPLETE'])
  expect(resultStateValues).toEqual([
    'NOT_ASSESSED',
    'PROVISIONAL',
    'CONFIRMED',
    'OVERRIDDEN',
    'VOID',
  ])
  expect(submissionStateValues).toEqual([
    'NOT_STARTED',
    'DRAFT',
    'SUBMITTED',
    'UNDER_REVIEW',
    'RETURNED',
    'COMPLETED',
  ])
  expect(assessmentPurposeValues).toEqual([
    'DIAGNOSTIC',
    'FORMATIVE',
    'AS_LEARNING',
    'SUMMATIVE',
    'RESEARCH',
  ])
  expect(bloomProcessValues).toEqual([
    'REMEMBER',
    'UNDERSTAND',
    'APPLY',
    'ANALYSE',
    'EVALUATE',
    'CREATE',
  ])
  expect(bloomKnowledgeValues).toEqual([
    'FACTUAL',
    'CONCEPTUAL',
    'PROCEDURAL',
    'METACOGNITIVE',
  ])
  expect(criterionDecisionValues).toEqual(['MET', 'NOT_MET', 'NOT_EVALUABLE'])
  expect(qualityReviewDecisionValues).toEqual(['APPROVED', 'REJECTED'])
  expect(misconceptionStateValues).toEqual([
    'PERSISTED',
    'WEAKENED',
    'CORRECTED',
    'UNCERTAIN',
  ])
})
