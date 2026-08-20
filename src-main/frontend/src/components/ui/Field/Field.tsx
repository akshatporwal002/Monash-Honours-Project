import { cloneElement, isValidElement, useId } from 'react'
import type { ReactElement, ReactNode } from 'react'

import { cx } from '../cx'
import styles from './Field.module.css'

interface WireableProps {
  id?: string
  'aria-describedby'?: string
  'aria-invalid'?: boolean
  'aria-required'?: boolean
}

export interface FieldProps {
  label: string
  help?: ReactNode
  error?: ReactNode
  required?: boolean
  className?: string
  /** A single form control; Field wires id, aria-describedby, aria-invalid, aria-required onto it. */
  children: ReactElement<WireableProps>
}

export function Field({ label, help, error, required, className, children }: FieldProps) {
  const id = useId()
  const helpId = `${id}-help`
  const errorId = `${id}-error`
  const describedBy =
    [help ? helpId : null, error ? errorId : null].filter(Boolean).join(' ') || undefined

  if (!isValidElement(children)) throw new Error('Field requires a single form-control child')

  const control = cloneElement(children, {
    id,
    'aria-describedby': describedBy,
    'aria-invalid': error ? true : undefined,
    'aria-required': required || undefined,
  })

  return (
    <div className={cx(styles.field, className)}>
      <label className={styles.label} htmlFor={id}>
        {label}
        {required ? <span className={styles.required}> (required)</span> : null}
      </label>
      {control}
      {help ? (
        <p id={helpId} className={styles.help}>
          {help}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className={styles.error}>
          {error}
        </p>
      ) : null}
    </div>
  )
}
