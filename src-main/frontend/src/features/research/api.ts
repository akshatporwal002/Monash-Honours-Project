import { request, API_BASE_URL, csrfToken, ApiError } from '../../app/api'
import type { ApiSchemas } from '../../api/generated'

export type Form = Omit<ApiSchemas['FormRead'], 'production_active' | 'definition'> & { instrument_key?: string; frozen?: boolean; production_active: boolean; definition: Omit<ApiSchemas['FormRead']['definition'], 'synthetic_only'> & { synthetic_only: boolean } }
export type Stage = ApiSchemas['InstrumentRecordWrite']['stage']
export type Participation = Omit<ApiSchemas['ParticipationRead'], 'production_active'> & { production_active: boolean }
export type Answer = ApiSchemas['InstrumentAnswer']
export type Packet = { id: string; stage: Stage; rubric: { code: string; wording: string; values: string[] }; redacted_evidence: string }
export type Plan = { id: string; revision: number; production_active?: boolean; plan: { conditions: string[]; stages: { stage: Stage; form_id: string }[]; rubrics: { code: string; wording: string; values: string[] }[] } }
export type Assignment = { allocation_id: string; stages: { stage: Stage; form: Form }[] }
export type Reconciliation = { plan_id: string | null; excluded_counts: Record<string, number>; rows: {
  allocation_id: string; participant_id: string; sequence_id: string; stage: Stage; form_id: string;
  status: 'unrecorded' | 'response' | 'explicit_gap' | 'ambiguous';
  observations: { record_id: string; kind: string; missing_reason: string | null; reason_code: string | null; missing_item_count: number }[];
  packet_ids: string[]; rating_ids: string[]; outcome_ids: string[];
}[] }
export const operationalFields = ['operational.episode', 'operational.adaptation_reasons', 'operational.override_reasons', 'operational.reserved_cost', 'operational.exposure_cost', 'operational.response_text', 'operational.code', 'operational.evidence', 'operational.model_references', 'operational.adaptations', 'operational.overrides', 'operational.source_references', 'operational.ai_output', 'operational.judge_result', 'operational.simulation', 'operational.latency_ms', 'operational.input_tokens', 'operational.output_tokens', 'operational.estimated_cost', 'operational.actual_cost', 'operational.outcome', 'operational.moderation']
export const studyFields = [...operationalFields, 'study.record_id', 'study.participant_id', 'study.sequence_id', 'study.stage', 'study.condition', 'study.plan_id', 'study.record_kind', 'study.instrument_record_id', 'study.packet_id', 'study.rubric_code', 'study.value_code', 'study.missing_reason', 'instrument.record_id', 'instrument.participant_id', 'instrument.sequence_id', 'instrument.stage', 'instrument.form_id', 'instrument.form_version', 'instrument.item_id', 'instrument.choice_code', 'instrument.integer_value', 'instrument.missing_reason', 'instrument.event_kind', 'instrument.reason_code', 'instrument.revision', 'instrument.supersedes_id', 'instrument.correction_reason_code', 'instrument.course_ref', 'instrument.outcome_ref', 'instrument.task_ref', 'instrument.response_ref']
export const key = () => crypto.randomUUID()
const post = <T>(url: string, body: object) => request<T>(url, { method: 'POST', body: JSON.stringify(body) })
const base = (study: string, course: string) => `/research/instruments/${encodeURIComponent(study)}/${encodeURIComponent(course)}`
export const studyApi = {
  reconciliation: (study: string, course: string) => request<Reconciliation>(`${base(study, course)}/study/reconciliation`),
  operationalPreview: (study: string, course: string, body: object) => post<{ fields: Record<string, { value: unknown; missing_reason: string | null; source_digest: string; source_references: string[]; adapter_version: string }> }>(`${base(study, course)}/study/operational/preview`, body),
  operationalCapture: (study: string, course: string, body: object) => post<{ id: string }>(`${base(study, course)}/study/operational/snapshots`, body),
  participation: (study: string, course: string, signal?: AbortSignal) => request<Participation>(`/research/governance/${encodeURIComponent(study)}/participation/${encodeURIComponent(course)}`, { signal }),
  governance: (study: string, body: object) => post(`/research/governance/${encodeURIComponent(study)}/decisions`, body),
  governanceHistory: (study: string) => request<unknown[]>(`/research/governance/${encodeURIComponent(study)}/decisions`),
  disposalPreview: (study: string, recordIds: string[]) => post<Record<string, unknown>>(`/research/governance/${encodeURIComponent(study)}/disposal/preview`, { record_ids: recordIds }),
  disposalExecute: (study: string, authorizationId: string, requestKey: string) => post<{ id: string; disposed_count: number }>(`/research/governance/${encodeURIComponent(study)}/disposal/execute`, { authorization_id: authorizationId, request_key: requestKey }),
  readForm: (study: string, course: string, id: string) => request<Form>(`${base(study, course)}/forms/${encodeURIComponent(id)}`),
  forms: (study: string, course: string, signal?: AbortSignal) => request<Assignment[]>(`${base(study, course)}/study/my-forms`, { signal }),
  researcherResponse: (study: string, course: string, body: object) => post<{ id: string }>(`${base(study, course)}/study/responses`, body),
  submit: (study: string, course: string, body: object) => post<{ id: string }>(`${base(study, course)}/study/my-responses`, body),
  plan: (study: string, course: string, signal?: AbortSignal) => request<Plan | null>(`${base(study, course)}/study/plan`, { signal }),
  records: (study: string, course: string) => request<Record<string, string | null>[]>(`${base(study, course)}/study/records`),
  decision: (study: string, course: string, body: object) => post<{ id: string }>(`${base(study, course)}/study/decisions`, body),
  packet: (study: string, course: string, id: string) => request<Packet>(`${base(study, course)}/study/packets/${encodeURIComponent(id)}`),
  form: (study: string, course: string, id: string, body: object) => post<Form>(`${base(study, course)}/forms/${encodeURIComponent(id)}`, body),
  freeze: (study: string, course: string, id: string, body: object) => post<Form>(`${base(study, course)}/forms/${encodeURIComponent(id)}/freeze`, body),
  export: async (study: string, course: string, fields: string[], stages: string[], format: string) => {
    const response = await fetch(`${API_BASE_URL}${base(study, course)}/study/exports`, {
      method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrfToken() ?? '' },
      body: JSON.stringify({ fields, stages, format }),
    })
    if (!response.ok) throw new ApiError('Study export is unavailable under the current permissions.', response.status)
    const blob = await response.blob()
    if (format === 'json') JSON.parse(await blob.text()) // An interrupted JSON stream must never become a download.
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = `full-study.${format}`; a.click(); URL.revokeObjectURL(url)
  },
}
