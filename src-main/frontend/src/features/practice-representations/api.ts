import { request } from '../../app/api'
import type { Representation } from '../../components/SupportRepresentation'

// Dedicated wire contracts until the coordinator regenerates the combined API.
export type PracticeRepresentation = Representation & {
  representation_id: string
  explanation_detail: 'brief' | 'detailed'
  support_kind: 'instructional' | 'accessibility'
}
export type Choice = Pick<PracticeRepresentation, 'representation_id' | 'title' | 'mode' | 'explanation_detail' | 'support_kind' | 'instructional_support_level'>
export type Catalog = {
  revision_id: string; review_event_id: string; preference_version: number
  on_request: boolean; recommended_id: string | null; selected_id: string | null
  selection: 'preference' | 'override'; explanation: string; choices: Choice[]
}
export type Selection = {
  revision_id: string; preference_version: number; representation_id: string
  request_key: string; selection: 'preference' | 'override'
}
export type Receipt = {
  evidence_id: string; revision_id: string; review_event_id: string; preference_version: number
  selection: 'preference' | 'override'; delivered_at: string; representation: PracticeRepresentation
}
export const practiceRepresentations = {
  catalog: (taskId: string, signal?: AbortSignal) => request<Catalog>(`/practice-representations/tasks/${taskId}`, { signal }),
  deliver: (taskId: string, body: Selection, signal?: AbortSignal) => request<Receipt>(`/practice-representations/tasks/${taskId}/deliver`, { method: 'POST', body: JSON.stringify(body), signal }),
}
