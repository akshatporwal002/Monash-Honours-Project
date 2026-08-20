import type { ReactNode } from 'react'

import { cx } from '../cx'
import styles from './DescriptionList.module.css'

export interface DescriptionItem {
  term: string
  description: ReactNode
}

export interface DescriptionListProps {
  items: DescriptionItem[]
  className?: string
}

/** Key–value pairs. Values always wrap in full — truncating conditions or criteria is a correctness bug. */
export function DescriptionList({ items, className }: DescriptionListProps) {
  return (
    <dl className={cx(styles.list, className)}>
      {items.map((item) => (
        <div key={item.term} className={styles.row}>
          <dt className={styles.term}>{item.term}</dt>
          <dd className={styles.description}>{item.description}</dd>
        </div>
      ))}
    </dl>
  )
}
