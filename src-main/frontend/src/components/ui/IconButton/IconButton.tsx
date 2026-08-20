import type { ButtonHTMLAttributes, ReactNode } from 'react'

import { cx } from '../cx'
import styles from './IconButton.module.css'

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Accessible name — required because the button has no visible text. */
  label: string
  children: ReactNode
  size?: 'sm' | 'md'
}

export function IconButton({ label, children, size = 'md', className, type = 'button', ...rest }: IconButtonProps) {
  return (
    <button
      {...rest}
      type={type}
      aria-label={label}
      className={cx(styles.iconButton, size === 'sm' && styles.sm, className)}
    >
      <span aria-hidden="true" className={styles.glyph}>
        {children}
      </span>
    </button>
  )
}
