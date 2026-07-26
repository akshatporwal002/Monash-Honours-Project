import { formatMetric, metricDetails } from './format'
import type { MetricValue } from './types'

type MetricCardProps = {
  label: string
  metric: MetricValue
}

export function MetricCard({ label, metric }: MetricCardProps) {
  return (
    <article className="analytics-metric-card">
      <h3>{label}</h3>
      <p className="analytics-metric-card__value">{formatMetric(metric)}</p>
      <p className="analytics-metric-card__detail">{metricDetails(metric)}</p>
    </article>
  )
}

export function MetricCell({ metric }: { metric: MetricValue }) {
  return (
    <>
      <span>{formatMetric(metric)}</span>
      <small>{metricDetails(metric)}</small>
    </>
  )
}
