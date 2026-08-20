import type { ResultState } from '../../../features/assessment/types'
import { cx } from '../cx'
import styles from './LifecycleTag.module.css'

export interface LifecycleTagProps {
  lifecycle: ResultState
  className?: string
}

const labels: Record<ResultState, string> = {
  NOT_ASSESSED: 'Not assessed',
  PROVISIONAL: 'Provisional',
  CONFIRMED: 'Confirmed',
  OVERRIDDEN: 'Overridden',
  VOID: 'Void',
}

/** Result-lifecycle state for assessor tables. Outlined ink — visually unrelated to ResultSeal. */
export function LifecycleTag({ lifecycle, className }: LifecycleTagProps) {
  return (
    <span className={cx(styles.tag, lifecycle === 'PROVISIONAL' && styles.dashed, className)}>
      {labels[lifecycle]}
    </span>
  )
}
