import { useId } from 'react'

import type { FeedbackSource } from './types'
import styles from './feedback.module.css'

export function FeedbackSources({ sources }: { sources: FeedbackSource[] }) {
  const headingId = useId()
  if (sources.length === 0) return null

  return (
    <section aria-labelledby={headingId}>
      <h3 id={headingId}>Sources</h3>
      <ul className={styles.sources}>
        {sources.map((source) => (
          <li key={source.source_id}>{source.label}</li>
        ))}
      </ul>
    </section>
  )
}
