import type { QualityReviewDecision } from '../../../features/assessment/types'
import { cx } from '../cx'
import styles from './JudgeTag.module.css'

export interface JudgeTagProps {
  decision: QualityReviewDecision
  className?: string
}

/**
 * Quality Judge decision — educator/assessor surfaces only. Square-cornered,
 * mono, deliberately unlike ResultSeal so it can never be read as the learner's
 * assessment result (AT20, D3 §5.2).
 */
export function JudgeTag({ decision, className }: JudgeTagProps) {
  return (
    <span className={cx(styles.tag, className)}>
      Quality review: {decision === 'APPROVED' ? 'approved' : 'rejected'}
    </span>
  )
}
