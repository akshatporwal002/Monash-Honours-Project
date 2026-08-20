import * as RadixTooltip from '@radix-ui/react-tooltip'
import type { ReactNode } from 'react'

import { cx } from '../cx'
import styles from './Tooltip.module.css'

export interface TooltipProps {
  content: string
  /** Trigger element — must be focusable (Radix renders it asChild). */
  children: ReactNode
}

/** Supplementary hints only — never the sole carrier of required information. */
export function Tooltip({ content, children }: TooltipProps) {
  return (
    <RadixTooltip.Provider delayDuration={300}>
      <RadixTooltip.Root>
        <RadixTooltip.Trigger asChild>{children}</RadixTooltip.Trigger>
        <RadixTooltip.Portal>
          <RadixTooltip.Content className={cx('ll-root', styles.content)} sideOffset={6}>
            {content}
            <RadixTooltip.Arrow className={styles.arrow} />
          </RadixTooltip.Content>
        </RadixTooltip.Portal>
      </RadixTooltip.Root>
    </RadixTooltip.Provider>
  )
}
