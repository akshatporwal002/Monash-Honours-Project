import { useId } from 'react'

import { conditionLabel } from './format'
import { MetricCard, MetricCell } from './MetricCard'
import type {
  ExperimentalCondition,
  MetricValue,
  ResearchMetrics,
} from './types'

const CONDITIONS: ExperimentalCondition[] = [
  'agentic_rag',
  'single_step_baseline',
]

const PAIRED_ROWS: Array<{
  label: string
  key: keyof ResearchMetrics['paired_agentic_minus_baseline']
}> = [
  { label: 'Pass rate', key: 'pass_rate' },
  { label: 'Relevance', key: 'relevance' },
  { label: 'Latency', key: 'latency_ms' },
  { label: 'Total tokens', key: 'total_tokens' },
  { label: 'Cost', key: 'cost' },
]

function MetricTableCell({ metric }: { metric: MetricValue }) {
  return (
    <td className={metric.value === null ? 'analytics-value--missing' : undefined}>
      <MetricCell metric={metric} />
    </td>
  )
}

export function ResearchSummary({ metrics }: { metrics: ResearchMetrics }) {
  const judgeHeadingId = useId()
  const qualityHeadingId = useId()
  const performanceHeadingId = useId()
  const pairedHeadingId = useId()

  return (
    <>
      <section className="analytics-section" aria-labelledby={judgeHeadingId}>
        <h2 id={judgeHeadingId}>Judge and retrieval results</h2>
        <div className="analytics-card-grid">
          <MetricCard label="First-pass judge rate" metric={metrics.first_pass_rate} />
          <MetricCard
            label="Regeneration success"
            metric={metrics.regeneration_success_rate}
          />
          <MetricCard label="Retrieval hit rate" metric={metrics.retrieval_hit_rate} />
        </div>
        <p className="analytics-supporting-note">
          Retrieval relevance threshold: {metrics.retrieval_threshold} (
          {metrics.retrieval_threshold_version}).
        </p>
      </section>

      <section className="analytics-section" aria-labelledby={qualityHeadingId}>
        <h2 id={qualityHeadingId}>Research quality by condition</h2>
        <div className="analytics-table-scroll">
          <table>
            <caption>Judge outcomes and fallback rates for each research condition</caption>
            <thead>
              <tr>
                <th scope="col">Condition</th>
                <th scope="col">Overall pass</th>
                <th scope="col">Hallucination</th>
                <th scope="col">Average relevance</th>
                <th scope="col">Fallback</th>
              </tr>
            </thead>
            <tbody>
              {CONDITIONS.map((condition) => {
                const conditionMetrics = metrics.by_condition[condition]
                return (
                  <tr key={condition}>
                    <th scope="row">{conditionLabel(condition)}</th>
                    <MetricTableCell metric={conditionMetrics.overall_pass_rate} />
                    <MetricTableCell metric={conditionMetrics.hallucination_rate} />
                    <MetricTableCell metric={conditionMetrics.average_relevance} />
                    <MetricTableCell metric={conditionMetrics.fallback_rate} />
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="analytics-section" aria-labelledby={performanceHeadingId}>
        <h2 id={performanceHeadingId}>Latency and cost</h2>
        <div className="analytics-table-scroll">
          <table>
            <caption>Primary pipeline performance and complete usage measurements</caption>
            <thead>
              <tr>
                <th scope="col">Condition</th>
                <th scope="col">Average latency</th>
                <th scope="col">P95 latency</th>
                <th scope="col">Average tokens</th>
                <th scope="col">Average cost</th>
              </tr>
            </thead>
            <tbody>
              {CONDITIONS.map((condition) => {
                const conditionMetrics = metrics.by_condition[condition]
                return (
                  <tr key={condition}>
                    <th scope="row">{conditionLabel(condition)}</th>
                    <MetricTableCell metric={conditionMetrics.average_latency_ms} />
                    <MetricTableCell metric={conditionMetrics.p95_latency_ms} />
                    <MetricTableCell metric={conditionMetrics.average_total_tokens} />
                    <MetricTableCell metric={conditionMetrics.average_cost} />
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="analytics-section" aria-labelledby={pairedHeadingId}>
        <h2 id={pairedHeadingId}>Paired agentic − baseline comparison</h2>
        <p>Positive values mean the agentic condition measured higher.</p>
        <div className="analytics-table-scroll">
          <table>
            <caption>Differences for comparable completed research pairs only</caption>
            <thead>
              <tr>
                <th scope="col">Measure</th>
                <th scope="col">Agentic − baseline</th>
              </tr>
            </thead>
            <tbody>
              {PAIRED_ROWS.map((row) => (
                <tr key={row.key}>
                  <th scope="row">{row.label}</th>
                  <MetricTableCell
                    metric={metrics.paired_agentic_minus_baseline[row.key]}
                  />
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  )
}
