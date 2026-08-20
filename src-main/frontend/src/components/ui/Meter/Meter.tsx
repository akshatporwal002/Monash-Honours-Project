import { cx } from '../cx'
import styles from './Meter.module.css'

export interface MeterProps {
  /** Completed units (e.g. tasks finished). Never a formal-assessment score. */
  value: number
  max: number
  /** Visible label naming what is measured, e.g. "Tasks completed". */
  label: string
  className?: string
}

/**
 * Labelled, count-based progress for activity and evidence — non-formal data only.
 * Formal PASS/INCOMPLETE results are never aggregated into a meter (D2 §14.5).
 */
export function Meter({ value, max, label, className }: MeterProps) {
  const safeMax = Math.max(max, 1)
  const clamped = Math.min(Math.max(value, 0), safeMax)
  const valueText = `${clamped} of ${safeMax}`
  return (
    <div className={cx(styles.wrapper, className)}>
      <div className={styles.header}>
        <span className={styles.label}>{label}</span>
        <span className={styles.value}>{valueText}</span>
      </div>
      <div
        role="meter"
        aria-label={label}
        aria-valuenow={clamped}
        aria-valuemin={0}
        aria-valuemax={safeMax}
        aria-valuetext={valueText}
        className={styles.track}
      >
        <span className={styles.fill} style={{ width: `${(clamped / safeMax) * 100}%` }} />
      </div>
    </div>
  )
}
