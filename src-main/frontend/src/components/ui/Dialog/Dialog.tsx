import * as RadixDialog from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import type { ReactNode } from 'react'

import { cx } from '../cx'
import styles from './Dialog.module.css'

export interface DialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: ReactNode
  children?: ReactNode
  /** Optional footer, usually Buttons. */
  footer?: ReactNode
  /**
   * The element that opens the dialog, rendered via Radix Trigger so focus
   * returns to it on close. Prefer passing it here over a detached button.
   */
  trigger?: ReactNode
  size?: 'md' | 'lg'
  className?: string
}

/** Radix-backed modal: focus trap, Escape, scroll lock, and focus return come from the primitive. */
export function Dialog({ open, onOpenChange, title, description, children, footer, trigger, size = 'md', className }: DialogProps) {
  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      {trigger ? <RadixDialog.Trigger asChild>{trigger}</RadixDialog.Trigger> : null}
      <RadixDialog.Portal>
        <RadixDialog.Overlay className={cx('ll-root', styles.overlay)} />
        <RadixDialog.Content className={cx('ll-root', styles.content, size === 'lg' && styles.lg, className)}>
          <div className={styles.header}>
            <RadixDialog.Title className={styles.title}>{title}</RadixDialog.Title>
            <RadixDialog.Close className={styles.close} aria-label="Close dialog">
              <X size={18} aria-hidden="true" />
            </RadixDialog.Close>
          </div>
          {description ? (
            <RadixDialog.Description className={styles.description}>{description}</RadixDialog.Description>
          ) : null}
          {children}
          {footer ? <div className={styles.footer}>{footer}</div> : null}
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  )
}
