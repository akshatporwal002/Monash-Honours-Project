import type { AssessmentResult, AssessmentReviewAction, ResultState } from './api'
import type { AssessmentPurpose, CriterionDecision } from './types'

export const actionLabels: Record<AssessmentReviewAction, string> = {
  CONFIRM: 'Confirm result',
  OVERRIDE: 'Override result',
  WITHHOLD: 'Withhold result',
  VOID: 'Void result',
  RETURN: 'Return for review',
}

/*
 * Status values render through the ui status components (ResultSeal,
 * LifecycleTag, JudgeTag) or through these fixed label maps - never through
 * readable() lowercasing (plan 006 Step 7).
 */
export const resultLabels: Record<AssessmentResult, string> = {
  PASS: 'Pass',
  INCOMPLETE: 'Incomplete',
}

export const lifecycleLabels: Record<ResultState, string> = {
  NOT_ASSESSED: 'Not assessed',
  PROVISIONAL: 'Provisional',
  CONFIRMED: 'Confirmed',
  OVERRIDDEN: 'Overridden',
  VOID: 'Void',
}

export const criterionDecisionLabels: Record<CriterionDecision, string> = {
  MET: 'Met',
  NOT_MET: 'Not met',
  NOT_EVALUABLE: 'Not evaluable',
}

export const purposeLabels: Record<AssessmentPurpose, string> = {
  DIAGNOSTIC: 'Diagnostic',
  FORMATIVE: 'Formative',
  AS_LEARNING: 'Assessment as learning',
  SUMMATIVE: 'Summative',
  RESEARCH: 'Research',
}

/** For non-status identifier strings only (version keys and similar). */
export function readable(value: string | null): string {
  return value ? value.toLowerCase().replaceAll('_', ' ') : 'Not set'
}
