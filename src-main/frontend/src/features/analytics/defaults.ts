import type { AnalyticsFilterState } from './types'

function utcDateInput(date: Date): string {
  return date.toISOString().slice(0, 10)
}

export function defaultAnalyticsFilters(now = new Date()): AnalyticsFilterState {
  const end = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1))
  const start = new Date(end)
  start.setUTCDate(start.getUTCDate() - 30)
  return {
    courseId: '',
    dateFrom: utcDateInput(start),
    dateTo: utcDateInput(end),
    experimentalCondition: '',
    taskType: '',
    model: '',
    judgeDecision: '',
  }
}
