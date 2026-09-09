import { request } from './api'
import type { ApiSchemas } from '../api/generated'

export type Activity = Required<ApiSchemas['ActivityRead']>
export type ActivityAction = ApiSchemas['ActivityAction']
const root = '/activity-continuation'
export const activityContinuation = {
  submission: (id: string) => request<Activity>(`${root}/submissions/${encodeURIComponent(id)}`),
  read: (id: string) => request<Activity>(`${root}/${encodeURIComponent(id)}`),
  course: (id: string, offset = 0) => request<Activity[]>(`${root}/courses/${encodeURIComponent(id)}?offset=${offset}&limit=20`),
  act: (id: string, body: ActivityAction) => request<Activity>(`${root}/${encodeURIComponent(id)}/actions`, { method: 'POST', body: JSON.stringify(body) }),
}
