import type { ApiSchemas } from '../../api/generated'

export type AssessmentResult = ApiSchemas['AssessmentResult']
export type ResultState = ApiSchemas['ResultState']
export type SubmissionState = ApiSchemas['SubmissionState']
export type AssessmentPurpose = ApiSchemas['AssessmentPurpose']
export type BloomProcess = ApiSchemas['BloomProcess']
export type BloomKnowledge = ApiSchemas['BloomKnowledge']
export type CriterionDecision = ApiSchemas['CriterionDecision']
export type QualityReviewDecision = ApiSchemas['QualityReviewDecision']
export type MisconceptionState = ApiSchemas['MisconceptionState']
export type AssessmentVersionReference = ApiSchemas['AssessmentVersionReference']
export type EvidenceReference = ApiSchemas['EvidenceReference']
export type EvidenceReferenceResolution =
  ApiSchemas['EvidenceReferenceResolutionEnvelope']['resolution']
export type FormalResultSummary = ApiSchemas['FormalResultSummary']

function enumValues<Value extends string>(
  exhaustiveValues: Record<Value, true>,
): readonly Value[] {
  return Object.keys(exhaustiveValues) as Value[]
}

export const assessmentResultValues = enumValues<AssessmentResult>({
  PASS: true,
  INCOMPLETE: true,
})

export const resultStateValues = enumValues<ResultState>({
  NOT_ASSESSED: true,
  PROVISIONAL: true,
  CONFIRMED: true,
  OVERRIDDEN: true,
  VOID: true,
})

export const submissionStateValues = enumValues<SubmissionState>({
  NOT_STARTED: true,
  DRAFT: true,
  SUBMITTED: true,
  UNDER_REVIEW: true,
  RETURNED: true,
  COMPLETED: true,
})

export const assessmentPurposeValues = enumValues<AssessmentPurpose>({
  DIAGNOSTIC: true,
  FORMATIVE: true,
  AS_LEARNING: true,
  SUMMATIVE: true,
  RESEARCH: true,
})

export const bloomProcessValues = enumValues<BloomProcess>({
  REMEMBER: true,
  UNDERSTAND: true,
  APPLY: true,
  ANALYSE: true,
  EVALUATE: true,
  CREATE: true,
})

export const bloomKnowledgeValues = enumValues<BloomKnowledge>({
  FACTUAL: true,
  CONCEPTUAL: true,
  PROCEDURAL: true,
  METACOGNITIVE: true,
})

export const criterionDecisionValues = enumValues<CriterionDecision>({
  MET: true,
  NOT_MET: true,
  NOT_EVALUABLE: true,
})

export const qualityReviewDecisionValues = enumValues<QualityReviewDecision>({
  APPROVED: true,
  REJECTED: true,
})

export const misconceptionStateValues = enumValues<MisconceptionState>({
  PERSISTED: true,
  WEAKENED: true,
  CORRECTED: true,
  UNCERTAIN: true,
})
