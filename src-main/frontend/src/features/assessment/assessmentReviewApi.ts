import type { ApiSchemas } from '../../api/generated'
import { request } from '../../app/api'

export type UnresolvedAssessment = ApiSchemas['UnresolvedAssessmentRead']
export type HumanAssessmentWrite = ApiSchemas['HumanAssessmentWrite']

export const humanReviewApi = {
  queue: (courseId: string, offset = 0) => request<UnresolvedAssessment[]>(`/assessment/courses/${encodeURIComponent(courseId)}/unresolved-attempts?limit=50&offset=${offset}`),
  detail: (attemptId: string) => request<UnresolvedAssessment>(`/assessment/attempts/${encodeURIComponent(attemptId)}/human-review`),
  finalise: (attemptId: string, payload: HumanAssessmentWrite) => request<ApiSchemas['HumanAssessmentReceipt']>(
    `/assessment/attempts/${encodeURIComponent(attemptId)}/human-review`,
    { method: 'POST', body: JSON.stringify(payload) },
  ),
}
