import type { InputHTMLAttributes, ReactNode } from 'react'

import { cx } from '../cx'
import styles from './Checkbox.module.css'

export interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label: ReactNode
  help?: ReactNode
}

export function Checkbox({ label, help, className, ...rest }: CheckboxProps) {
  return (
    <label className={cx(styles.checkbox, className)}>
      <input {...rest} type="checkbox" className={styles.input} />
      <span className={styles.text}>
        <span className={styles.label}>{label}</span>
        {help ? <span className={styles.help}>{help}</span> : null}
      </span>
    </label>
  )
}
