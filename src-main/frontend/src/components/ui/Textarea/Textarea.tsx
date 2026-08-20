import type { TextareaHTMLAttributes } from 'react'

import { cx } from '../cx'
import styles from './Textarea.module.css'

export type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement>

export function Textarea({ className, rows = 4, ...rest }: TextareaProps) {
  return <textarea {...rest} rows={rows} className={cx(styles.textarea, className)} />
}
