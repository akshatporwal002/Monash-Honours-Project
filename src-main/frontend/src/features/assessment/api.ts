import { api } from '../../app/api'
import type { ApiSchemas } from '../../api/generated'

export type AssessmentDefinition = ApiSchemas['AssessmentDefinitionRead']
export type AssessmentDraft = ApiSchemas['AssessmentDefinitionDraftCreate']

export const assessmentApi = {
  createDraft: (courseId: string, outcomeId: string, payload: AssessmentDraft) =>
    api.assessment.createDefinition(courseId, outcomeId, payload),
  history: (courseId: string, definitionId: string) => api.assessment.history(courseId, definitionId),
  publish: (courseId: string, definitionId: string, expectedVersion: number, reason: string) =>
    api.assessment.publish(courseId, definitionId, { expected_version: expectedVersion, reason }),
}
