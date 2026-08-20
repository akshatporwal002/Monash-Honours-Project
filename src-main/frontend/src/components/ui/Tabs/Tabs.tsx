import * as RadixTabs from '@radix-ui/react-tabs'
import type { ReactNode } from 'react'

import { cx } from '../cx'
import styles from './Tabs.module.css'

export interface TabItem {
  value: string
  label: string
  content: ReactNode
}

export interface TabsProps {
  tabs: TabItem[]
  value: string
  onValueChange: (value: string) => void
  /** Accessible name for the tab list. */
  label: string
  className?: string
}

export function Tabs({ tabs, value, onValueChange, label, className }: TabsProps) {
  return (
    <RadixTabs.Root value={value} onValueChange={onValueChange} className={className}>
      <RadixTabs.List className={styles.list} aria-label={label}>
        {tabs.map((tab) => (
          <RadixTabs.Trigger key={tab.value} value={tab.value} className={styles.trigger}>
            {tab.label}
          </RadixTabs.Trigger>
        ))}
      </RadixTabs.List>
      {tabs.map((tab) => (
        <RadixTabs.Content key={tab.value} value={tab.value} className={cx(styles.panel)}>
          {tab.content}
        </RadixTabs.Content>
      ))}
    </RadixTabs.Root>
  )
}
