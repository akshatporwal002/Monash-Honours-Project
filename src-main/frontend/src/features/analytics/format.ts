import type { MetricValue } from './types'

const compactNumber = new Intl.NumberFormat('en-AU', {
  maximumFractionDigits: 2,
})

const currency = new Intl.NumberFormat('en-AU', {
  style: 'currency',
  currency: 'AUD',
  maximumFractionDigits: 4,
})

export function formatMetric(metric: MetricValue): string {
  if (metric.value === null) return 'Not available'
  if (metric.unit === 'ratio') return `${compactNumber.format(metric.value * 100)}%`
  if (metric.unit === 'ratio_points') {
    const value = metric.value * 100
    return `${value > 0 ? '+' : ''}${compactNumber.format(value)} pp`
  }
  if (metric.unit === 'milliseconds') return `${compactNumber.format(metric.value)} ms`
  if (metric.unit === 'currency_units') return currency.format(metric.value)
  if (metric.unit === 'tokens') return `${compactNumber.format(metric.value)} tokens`
  if (metric.unit === 'score') return `${compactNumber.format(metric.value)}/100`
  if (metric.unit === 'attempts') return `${compactNumber.format(metric.value)} attempts`
  return compactNumber.format(metric.value)
}

export function metricDetails(metric: MetricValue): string {
  return `${compactNumber.format(metric.numerator)} / ${metric.denominator}; sample ${metric.sample_size}`
}

export function formatDateTime(value: string | null): string {
  if (value === null) return 'Never active'
  return new Intl.DateTimeFormat('en-AU', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'UTC',
  }).format(new Date(value))
}

export function conditionLabel(condition: string): string {
  if (condition === 'agentic_rag') return 'Agentic RAG'
  if (condition === 'single_step_baseline') return 'Single-step baseline'
  return condition
    .split('_')
    .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1)}`)
    .join(' ')
}

export function eventLabel(eventType: string): string {
  const labels: Record<string, string> = {
    task_view: 'Task viewed',
    draft_save: 'Draft saved',
    submission: 'Submitted',
    feedback_view: 'Feedback viewed',
    completion: 'Completed',
  }
  return labels[eventType] ?? eventType
}
