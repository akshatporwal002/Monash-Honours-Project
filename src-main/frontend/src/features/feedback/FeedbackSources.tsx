import { useId } from 'react'

import type { FeedbackSource } from './types'

export function FeedbackSources({ sources }: { sources: FeedbackSource[] }) {
  const headingId = useId()
  if (sources.length === 0) return null

  return (
    <section aria-labelledby={headingId}>
      <h3 id={headingId}>Sources</h3>
      <ul className="feedback-sources">
        {sources.map((source) => (
          <li key={source.source_id}>{source.label}</li>
        ))}
      </ul>
    </section>
  )
}
