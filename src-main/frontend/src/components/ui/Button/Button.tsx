import type { ButtonHTMLAttributes } from 'react'

import { cx } from '../cx'
import styles from './Button.module.css'

export type ButtonVariant = 'primary' | 'secondary' | 'quiet' | 'danger'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: 'sm' | 'md'
  loading?: boolean
}

export function Button({
  variant = 'secondary',
  size = 'md',
  loading = false,
  disabled,
  className,
  children,
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button
      {...rest}
      type={type}
      className={cx(styles.button, styles[variant], size === 'sm' && styles.sm, className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
    >
      {loading ? <span className={styles.spinner} aria-hidden="true" /> : null}
      <span className={styles.label}>{children}</span>
    </button>
  )
}
