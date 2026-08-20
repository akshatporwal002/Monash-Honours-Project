import type { HTMLAttributes, ReactNode } from 'react'

import { cx } from '../cx'
import styles from './Card.module.css'

export interface CardProps extends HTMLAttributes<HTMLElement> {
  eyebrow?: string
  heading?: ReactNode
  actions?: ReactNode
  padding?: 'md' | 'none'
}

export function Card({ eyebrow, heading, actions, padding = 'md', className, children, ...rest }: CardProps) {
  const hasHeader = Boolean(eyebrow || heading || actions)
  return (
    <section {...rest} className={cx(styles.card, padding === 'none' && styles.flush, className)}>
      {hasHeader ? (
        <header className={styles.header}>
          <div>
            {eyebrow ? <p className={styles.eyebrow}>{eyebrow}</p> : null}
            {heading ? <h2 className={styles.heading}>{heading}</h2> : null}
          </div>
          {actions ? <div className={styles.actions}>{actions}</div> : null}
        </header>
      ) : null}
      {children}
    </section>
  )
}
