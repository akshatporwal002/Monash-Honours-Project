import { api } from '../../app/api'
import type { ApiSchemas } from '../../api/generated'

export type AssessmentDefinition = ApiSchemas['AssessmentDefinitionRead']
export type AssessmentDraft = ApiSchemas['AssessmentDefinitionDraftCreate']
export type AssessmentReviewDetail = ApiSchemas['AssessmentReviewDetailRead']
export type AssessmentReviewAction = ApiSchemas['AssessorReviewAction']
export type AssessmentReviewActionRequest = ApiSchemas['AssessmentReviewActionCreate']
export type AssessmentResult = ApiSchemas['AssessmentResult']
export type ResultState = ApiSchemas['ResultState']

export const assessmentApi = {
  createDraft: (courseId: string, outcomeId: string, payload: AssessmentDraft) =>
    api.assessment.createDefinition(courseId, outcomeId, payload),
  history: (courseId: string, definitionId: string) => api.assessment.history(courseId, definitionId),
  publish: (courseId: string, definitionId: string, expectedVersion: number, reason: string) =>
    api.assessment.publish(courseId, definitionId, { expected_version: expectedVersion, reason }),
  reviewQueue: (courseId: string, filters: {
    outcome_id?: string
    result?: AssessmentResult
    result_state?: ResultState
    review_flag?: string
    minimum_age_hours?: number
  }) => api.assessment.reviewQueue(courseId, filters),
  reviewDetail: (decisionId: string) => api.assessment.reviewDetail(decisionId),
  reviewAction: (decisionId: string, payload: AssessmentReviewActionRequest) =>
    api.assessment.reviewAction(decisionId, payload),
}
