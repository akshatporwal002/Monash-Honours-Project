import type { ReactNode } from 'react'

import { cx } from '../cx'
import styles from './EmptyState.module.css'

export interface EmptyStateProps {
  title: string
  description?: ReactNode
  action?: ReactNode
  icon?: ReactNode
  className?: string
}

/** An empty screen is an invitation to act — always say what comes next. */
export function EmptyState({ title, description, action, icon, className }: EmptyStateProps) {
  return (
    <div role="status" className={cx(styles.empty, className)}>
      {icon ? (
        <span className={styles.icon} aria-hidden="true">
          {icon}
        </span>
      ) : null}
      <p className={styles.title}>{title}</p>
      {description ? <p className={styles.description}>{description}</p> : null}
      {action ? <div className={styles.action}>{action}</div> : null}
    </div>
  )
}
