import type { ReactNode } from 'react'

import { cx } from '../cx'
import styles from './EstimateChip.module.css'

export interface EstimateChipProps {
  /** The estimate itself, e.g. "Developing". */
  children: ReactNode
  /**
   * Uncertainty wording — required. An inference may never render without it
   * (NFR27: users must tell evidence from inference).
   */
  uncertainty: string
  className?: string
}

/**
 * Learner-model estimate — always outlined (certainty grammar: inference, not fact),
 * always carrying its uncertainty. Never chip-shaped like a formal result and never
 * a substitute for one (D1 §12.3).
 */
export function EstimateChip({ children, uncertainty, className }: EstimateChipProps) {
  return (
    <span className={cx(styles.chip, className)}>
      <span className={styles.value}>{children}</span>
      <span className={styles.uncertainty}>{uncertainty}</span>
    </span>
  )
}
