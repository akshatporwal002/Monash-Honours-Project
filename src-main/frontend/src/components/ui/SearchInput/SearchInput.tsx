import { Search } from 'lucide-react'
import type { InputHTMLAttributes } from 'react'

import { cx } from '../cx'
import styles from './SearchInput.module.css'

export interface SearchInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  /** Accessible name — required; search inputs rarely have a visible label. */
  label: string
}

export function SearchInput({ label, className, ...rest }: SearchInputProps) {
  return (
    <div className={cx(styles.wrapper, className)}>
      <Search className={styles.icon} size={16} aria-hidden="true" />
      <input {...rest} type="search" aria-label={label} className={styles.input} />
    </div>
  )
}
