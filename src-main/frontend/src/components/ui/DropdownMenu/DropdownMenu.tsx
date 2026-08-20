import * as RadixDropdown from '@radix-ui/react-dropdown-menu'
import type { ReactNode } from 'react'

import { cx } from '../cx'
import styles from './DropdownMenu.module.css'

export interface DropdownMenuItem {
  label: string
  onSelect: () => void
  danger?: boolean
  disabled?: boolean
}

export interface DropdownMenuProps {
  /** The trigger element; rendered as the menu button via asChild. */
  trigger: ReactNode
  items: DropdownMenuItem[]
  align?: 'start' | 'end'
}

export function DropdownMenu({ trigger, items, align = 'end' }: DropdownMenuProps) {
  return (
    <RadixDropdown.Root>
      <RadixDropdown.Trigger asChild>{trigger}</RadixDropdown.Trigger>
      <RadixDropdown.Portal>
        <RadixDropdown.Content className={cx('ll-root', styles.content)} align={align} sideOffset={4}>
          {items.map((item) => (
            <RadixDropdown.Item
              key={item.label}
              className={cx(styles.item, item.danger && styles.danger)}
              disabled={item.disabled}
              onSelect={item.onSelect}
            >
              {item.label}
            </RadixDropdown.Item>
          ))}
        </RadixDropdown.Content>
      </RadixDropdown.Portal>
    </RadixDropdown.Root>
  )
}
