import { request } from '../../app/api'
import type { AssessmentDraft } from './api'
import type { AuthoringDefinition } from './definitionEditing'

const base = (courseId: string) => `/assessment/courses/${encodeURIComponent(courseId)}`
export const definitionEditingApi = {
  history: (courseId: string, definitionId: string) => request<AuthoringDefinition[]>(
    `${base(courseId)}/definitions/${encodeURIComponent(definitionId)}/history`,
  ),
  save: (definition: AuthoringDefinition, draft: AssessmentDraft) => request<AuthoringDefinition>(
    `${base(definition.course_id)}/outcomes/${encodeURIComponent(definition.outcome_id)}/definitions/${encodeURIComponent(definition.assessment_definition_id)}`,
    { method: 'PUT', body: JSON.stringify({ ...draft, expected_version: definition.version }),
      headers: { 'Content-Type': 'application/json' } },
  ),
  publish: (definition: AuthoringDefinition, reason: string) => request<AuthoringDefinition>(
    `${base(definition.course_id)}/definitions/${encodeURIComponent(definition.assessment_definition_id)}/publish`,
    { method: 'POST', body: JSON.stringify({ expected_version: definition.version, reason }),
      headers: { 'Content-Type': 'application/json' } },
  ),
}
