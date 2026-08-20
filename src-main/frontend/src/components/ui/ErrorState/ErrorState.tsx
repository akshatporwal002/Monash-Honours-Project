import { AlertTriangle } from 'lucide-react'
import type { ReactNode } from 'react'

import { Button } from '../Button/Button'
import { cx } from '../cx'
import styles from './ErrorState.module.css'

export interface ErrorStateProps {
  title: string
  description?: ReactNode
  onRetry?: () => void
  retryLabel?: string
  className?: string
}

/** Errors say what went wrong and what to do next. They do not apologise. */
export function ErrorState({ title, description, onRetry, retryLabel = 'Try again', className }: ErrorStateProps) {
  return (
    <div role="alert" className={cx(styles.error, className)}>
      <AlertTriangle size={20} aria-hidden="true" className={styles.icon} />
      <p className={styles.title}>{title}</p>
      {description ? <p className={styles.description}>{description}</p> : null}
      {onRetry ? (
        <div className={styles.action}>
          <Button variant="secondary" onClick={onRetry}>
            {retryLabel}
          </Button>
        </div>
      ) : null}
    </div>
  )
}
