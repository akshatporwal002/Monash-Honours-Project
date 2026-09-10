import { request } from '../../app/api'
import type { ApiSchemas } from '../../api/generated'

export type Check = ApiSchemas['MisconceptionRead']
export type Candidate = ApiSchemas['MisconceptionCandidateRead']
export type Stage = ApiSchemas['MisconceptionAnswer']['stage']
export const stageName: Record<Stage, string> = { PROBE: 'Check question', REVISION: 'Revision after help', TRANSFER: 'Fresh check' }
export const stateName: Record<Check['state'], string> = { UNCERTAIN: 'Uncertain', PERSISTED: 'Persisted', WEAKENED: 'Weakened', CORRECTED: 'Corrected' }
const post = <T>(path: string, body: object) => request<T>(path, { method: 'POST', body: JSON.stringify(body) })
export const checksApi = {
  list: (offset = 0, signal?: AbortSignal) => request<Check[]>(`/misconceptions?offset=${offset}`, { signal }),
  candidates: (offset = 0, signal?: AbortSignal) => request<Candidate[]>(`/misconceptions/teaching?offset=${offset}`, { signal }),
  read: (id: string, signal?: AbortSignal) => request<Check>(`/misconceptions/${encodeURIComponent(id)}`, { signal }),
  open: (body: ApiSchemas['MisconceptionOpen']) => post<Check>('/misconceptions', body),
  answer: (id: string, body: ApiSchemas['MisconceptionAnswer']) => post<Check>(`/misconceptions/${encodeURIComponent(id)}/responses`, body),
  review: (id: string, body: ApiSchemas['MisconceptionReview']) => post<Check>(`/misconceptions/${encodeURIComponent(id)}/reviews`, body),
  exit: (id: string, body: ApiSchemas['MisconceptionExit']) => post<Check>(`/misconceptions/${encodeURIComponent(id)}/exit`, body),
}
