import type { HTMLAttributes } from 'react'

import { cx } from '../cx'
import styles from './Tag.module.css'

export interface TagProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: 'neutral' | 'accent'
}

/**
 * A small neutral label for non-status metadata (task type, role, "AI-generated").
 * Formal-result, lifecycle, judge, and execution statuses have their own
 * dedicated components — never a Tag (D3 §5.2 namespace separation).
 */
export function Tag({ tone = 'neutral', className, children, ...rest }: TagProps) {
  return (
    <span {...rest} className={cx(styles.tag, tone === 'accent' && styles.accent, className)}>
      {children}
    </span>
  )
}
