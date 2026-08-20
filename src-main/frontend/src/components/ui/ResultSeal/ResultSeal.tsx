import { CheckCircle2, CircleDot } from 'lucide-react'

import type { AssessmentResult, ResultState } from '../../../features/assessment/types'
import { cx } from '../cx'
import styles from './ResultSeal.module.css'

export interface ResultSealProps {
  result: AssessmentResult
  lifecycle: ResultState
  size?: 'sm' | 'lg'
  className?: string
}

const lifecycleText: Record<ResultState, string> = {
  NOT_ASSESSED: 'Not yet assessed',
  PROVISIONAL: 'Provisional — awaiting assessor review',
  CONFIRMED: 'Confirmed by assessor',
  OVERRIDDEN: 'Changed by assessor decision',
  VOID: 'Set aside by assessor decision',
}

// The formal result is text + icon + shape, never colour alone (D2 §14.4, AT24).
// PASS is solid (observed, confirmed treatment); INCOMPLETE is outlined and open —
// it means "evidence still needed", never failure (AT19). Red is never used here.
export function ResultSeal({ result, lifecycle, size = 'lg', className }: ResultSealProps) {
  if (result !== 'PASS' && result !== 'INCOMPLETE') {
    // AC19: PASS and INCOMPLETE are the only learner results. Never invent a third state.
    if (import.meta.env.DEV) {
      throw new Error(`ResultSeal received a non-learner result value: ${String(result)}`)
    }
    return null
  }
  const pass = result === 'PASS'
  const provisional = lifecycle === 'PROVISIONAL'
  return (
    <div
      className={cx(
        styles.seal,
        pass ? styles.pass : styles.incomplete,
        provisional && styles.provisional,
        size === 'sm' && styles.sm,
        className,
      )}
    >
      <span className={styles.icon} aria-hidden="true">
        {pass ? <CheckCircle2 /> : <CircleDot />}
      </span>
      <span className={styles.text}>
        <strong className={styles.result}>{pass ? 'Pass' : 'Incomplete'}</strong>
        <span className={styles.lifecycle}>{lifecycleText[lifecycle]}</span>
      </span>
    </div>
  )
}
