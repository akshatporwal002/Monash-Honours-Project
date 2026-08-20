import { cx } from '../cx'
import styles from './BarList.module.css'

export interface BarListItem {
  label: string
  /** The magnitude that sets the bar length. */
  value: number
  /** Visible value text; defaults to the raw value (e.g. pass "62%" for percentages). */
  display?: string
}

export interface BarListProps {
  items: BarListItem[]
  /** Scale maximum; defaults to the largest item value. A minimum of 1 keeps all-zero series rendering. */
  max?: number
  className?: string
}

/**
 * Labelled horizontal bars with visible values — the value is always text in the
 * DOM, so the bar itself carries no meaning alone. Non-formal counts and
 * aggregates only; never PASS/INCOMPLETE averages (D2 section 14.5).
 */
export function BarList({ items, max, className }: BarListProps) {
  const scale = Math.max(1, max ?? Math.max(0, ...items.map((item) => item.value)))
  return (
    <ul className={cx(styles.list, className)}>
      {items.map((item) => {
        const clamped = Math.min(Math.max(item.value, 0), scale)
        return (
          <li key={item.label} className={styles.row}>
            <span className={styles.label}>{item.label}</span>
            <span className={styles.track} aria-hidden="true">
              <span className={styles.fill} style={{ width: `${(clamped / scale) * 100}%` }} />
            </span>
            <span className={styles.value}>{item.display ?? String(item.value)}</span>
          </li>
        )
      })}
    </ul>
  )
}
