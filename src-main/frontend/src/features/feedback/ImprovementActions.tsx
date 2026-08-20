import { useId } from 'react'

import styles from './feedback.module.css'

export function ImprovementActions({ actions }: { actions: string[] }) {
  const headingId = useId()
  if (actions.length === 0) return null

  return (
    <section aria-labelledby={headingId}>
      <h3 id={headingId}>Ways to improve</h3>
      <ol className={styles.actions}>
        {actions.map((action) => (
          <li key={action}>{action}</li>
        ))}
      </ol>
    </section>
  )
}
