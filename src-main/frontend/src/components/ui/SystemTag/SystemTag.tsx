import { cx } from '../cx'
import styles from './SystemTag.module.css'

export type SystemOutcome = 'SUCCEEDED' | 'FAILED'

export interface SystemTagProps {
  outcome: SystemOutcome
  className?: string
}

/**
 * Request/execution outcome for technical and admin surfaces only.
 * FAILED here is a system event — never a learner result (D3 §5.2).
 */
export function SystemTag({ outcome, className }: SystemTagProps) {
  return (
    <span className={cx(styles.tag, outcome === 'FAILED' && styles.failed, className)}>
      {outcome === 'SUCCEEDED' ? 'succeeded' : 'failed'}
    </span>
  )
}
