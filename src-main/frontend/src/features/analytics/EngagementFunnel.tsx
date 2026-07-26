import { useId } from 'react'

import { eventLabel, formatMetric, metricDetails } from './format'
import type { FunnelStage } from './types'

export function EngagementFunnel({ stages }: { stages: FunnelStage[] }) {
  const headingId = useId()
  const maximum = Math.max(1, ...stages.map((stage) => stage.count))

  return (
    <section className="analytics-section" aria-labelledby={headingId}>
      <h2 id={headingId}>Chronological engagement funnel</h2>
      <p>Each stage counts learner-task pairs that reached it after every preceding stage.</p>
      <figure className="analytics-funnel">
        <svg
          className="analytics-funnel__chart"
          viewBox={`0 0 100 ${Math.max(1, stages.length) * 18}`}
          preserveAspectRatio="none"
          aria-hidden="true"
          focusable="false"
        >
          {stages.map((stage, index) => (
            <rect
              className="analytics-funnel__bar"
              key={stage.event_type}
              x="0"
              y={index * 18 + 2}
              width={(stage.count / maximum) * 100}
              height="12"
              rx="2"
            />
          ))}
        </svg>
        <figcaption>
          <div className="analytics-table-scroll">
            <table>
              <caption>Text equivalent of the chronological engagement funnel</caption>
              <thead>
                <tr>
                  <th scope="col">Stage</th>
                  <th scope="col">Learner-task pairs</th>
                  <th scope="col">From previous stage</th>
                  <th scope="col">Metric basis</th>
                </tr>
              </thead>
              <tbody>
                {stages.map((stage) => (
                  <tr key={stage.event_type}>
                    <th scope="row">{eventLabel(stage.event_type)}</th>
                    <td>{stage.count}</td>
                    <td>{formatMetric(stage.previous_stage_rate)}</td>
                    <td>{metricDetails(stage.previous_stage_rate)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </figcaption>
      </figure>
    </section>
  )
}
