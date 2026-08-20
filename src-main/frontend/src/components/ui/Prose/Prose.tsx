import type { HTMLAttributes } from 'react'

import { cx } from '../cx'
import styles from './Prose.module.css'

export type ProseProps = HTMLAttributes<HTMLDivElement>

/** Reading container for rendered markdown and long-form feedback — serif, measured line length. */
export function Prose({ className, children, ...rest }: ProseProps) {
  return (
    <div {...rest} className={cx(styles.prose, className)}>
      {children}
    </div>
  )
}
