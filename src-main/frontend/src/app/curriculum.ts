import { request } from './api'
import type { ApiSchemas } from '../api/generated'

export type Pathway = ApiSchemas['PathwayRead']
export type Diagnostic = ApiSchemas['DiagnosticRead']
export type DiagnosticResponse = ApiSchemas['DiagnosticSubmit']
export type PathwayPublish = ApiSchemas['PathwayPublish']
const post = (body: object) => ({ method: 'POST', body: JSON.stringify(body) })
export const curriculum = {
  pathways: (course: string) => request<Pathway[]>(`/curriculum/courses/${encodeURIComponent(course)}/pathways`),
  diagnostics: (course: string, offset = 0) => request<Diagnostic[]>(`/curriculum/courses/${encodeURIComponent(course)}/diagnostics?offset=${offset}&limit=20`),
  publish: (outcome: string, body: PathwayPublish) => request<Pathway>(`/curriculum/outcomes/${encodeURIComponent(outcome)}/pathways`, post(body)),
  start: (body: ApiSchemas['DiagnosticStart']) => request<Diagnostic>('/curriculum/diagnostics', post(body)),
  submit: (id: string, body: DiagnosticResponse) => request<Diagnostic>(`/curriculum/diagnostics/${encodeURIComponent(id)}/response`, post(body)),
  confirm: (id: string, body: ApiSchemas['DiagnosticConfirm']) => request<Diagnostic>(`/curriculum/diagnostics/${encodeURIComponent(id)}/confirmation`, post(body)),
}
