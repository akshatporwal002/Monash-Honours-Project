import { useId } from 'react'

import type { AnalyticsApiClient, AnalyticsFilterState } from './types'

export function ExportControls({
  client,
  filters,
}: {
  client: AnalyticsApiClient
  filters: AnalyticsFilterState
}) {
  const headingId = useId()
  return (
    <section className="analytics-section" aria-labelledby={headingId}>
      <h2 id={headingId}>Research export</h2>
      <p>Download privacy-safe terminal research records for the applied filters.</p>
      <div className="analytics-export-actions">
        <a
          className="analytics-button"
          href={client.researchExportUrl('csv', filters)}
          download
        >
          Download CSV
        </a>
        <a
          className="analytics-button analytics-button--secondary"
          href={client.researchExportUrl('json', filters)}
          download
        >
          Download JSON
        </a>
      </div>
    </section>
  )
}
