import { cx } from '../cx'
import styles from './CodeBlock.module.css'

export interface CodeBlockProps {
  /** Source text; whitespace and formatting are preserved exactly (FR13). */
  code: string
  /** Accessible name, e.g. "Qiskit starter code". */
  label?: string
  className?: string
}

export function CodeBlock({ code, label, className }: CodeBlockProps) {
  return (
    <pre className={cx(styles.block, className)} aria-label={label} tabIndex={0}>
      <code>{code}</code>
    </pre>
  )
}
