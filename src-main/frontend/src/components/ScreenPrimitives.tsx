import { AlertTriangle, Sparkles } from 'lucide-react'
import type { ReactNode } from 'react'

import { cx } from './ui/cx'
import styles from './ScreenPrimitives.module.css'

/**
 * Loading / empty / error state block. The legacy Icon sprite, ProgressRing,
 * PageHeading, and Panel were removed in plan 006 Step 9; the ui/ system
 * (PageHeader, Card, Meter, lucide icons) replaced them.
 */
export function ScreenState({
  kind,
  title,
  message,
  action,
  fullscreen = false,
}: {
  kind: 'loading' | 'empty' | 'error'
  title: string
  message: string
  action?: ReactNode
  fullscreen?: boolean
}) {
  return (
    <div
      className={cx('ll-root', styles.state, fullscreen && styles.fullscreen)}
      role={kind === 'error' ? 'alert' : 'status'}
    >
      <span className={styles.icon} aria-hidden="true">
        {kind === 'loading' ? (
          <span className={styles.spinner} />
        ) : kind === 'error' ? (
          <AlertTriangle size={24} className={styles.errorIcon} />
        ) : (
          <Sparkles size={24} />
        )}
      </span>
      <h2 className={styles.title}>{title}</h2>
      <p className={styles.message}>{message}</p>
      {action ? <div className={styles.action}>{action}</div> : null}
    </div>
  )
}
