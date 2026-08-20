import type { InputHTMLAttributes } from 'react'

import { cx } from '../cx'
import styles from './Input.module.css'

export type InputProps = InputHTMLAttributes<HTMLInputElement>

export function Input({ className, ...rest }: InputProps) {
  return <input {...rest} className={cx(styles.input, className)} />
}
