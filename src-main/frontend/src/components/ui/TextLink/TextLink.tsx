import type { AnchorHTMLAttributes } from 'react'

import { cx } from '../cx'
import styles from './TextLink.module.css'

export type TextLinkProps = AnchorHTMLAttributes<HTMLAnchorElement>

export function TextLink({ className, children, ...rest }: TextLinkProps) {
  return (
    <a {...rest} className={cx(styles.link, className)}>
      {children}
    </a>
  )
}
