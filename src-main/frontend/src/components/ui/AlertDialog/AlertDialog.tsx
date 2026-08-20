import * as RadixAlertDialog from '@radix-ui/react-alert-dialog'
import { useId, useState } from 'react'
import type { ReactNode } from 'react'

import { Button } from '../Button/Button'
import { cx } from '../cx'
import { Textarea } from '../Textarea/Textarea'
import styles from './AlertDialog.module.css'

export interface AlertDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description?: ReactNode
  tone?: 'default' | 'danger'
  confirmLabel: string
  cancelLabel?: string
  /**
   * When set, a required reason textarea appears and confirm stays disabled
   * until it has text. The reason is passed to onConfirm (assessor override,
   * void, and withhold actions require a recorded reason, per D2 section 14.2).
   */
  reasonLabel?: string
  confirmLoading?: boolean
  onConfirm: (reason?: string) => void
  children?: ReactNode
}

export function AlertDialog({
  open,
  onOpenChange,
  title,
  description,
  tone = 'default',
  confirmLabel,
  cancelLabel = 'Cancel',
  reasonLabel,
  confirmLoading = false,
  onConfirm,
  children,
}: AlertDialogProps) {
  const [reason, setReason] = useState('')
  const reasonId = useId()

  const needsReason = Boolean(reasonLabel)
  const confirmDisabled = needsReason && reason.trim() === ''

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) setReason('')
    onOpenChange(nextOpen)
  }

  return (
    <RadixAlertDialog.Root open={open} onOpenChange={handleOpenChange}>
      <RadixAlertDialog.Portal>
        <RadixAlertDialog.Overlay className={cx('ll-root', styles.overlay)} />
        <RadixAlertDialog.Content className={cx('ll-root', styles.content)}>
          <RadixAlertDialog.Title className={styles.title}>{title}</RadixAlertDialog.Title>
          {description ? (
            <RadixAlertDialog.Description className={styles.description}>{description}</RadixAlertDialog.Description>
          ) : null}
          {children}
          {needsReason ? (
            <div className={styles.reason}>
              <label className={styles.reasonLabel} htmlFor={reasonId}>
                {reasonLabel} <span className={styles.required}>(required)</span>
              </label>
              <Textarea
                id={reasonId}
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                rows={3}
              />
            </div>
          ) : null}
          <div className={styles.footer}>
            <RadixAlertDialog.Cancel asChild>
              <Button variant="quiet">{cancelLabel}</Button>
            </RadixAlertDialog.Cancel>
            <Button
              variant={tone === 'danger' ? 'danger' : 'primary'}
              disabled={confirmDisabled}
              loading={confirmLoading}
              onClick={() => onConfirm(needsReason ? reason.trim() : undefined)}
            >
              {confirmLabel}
            </Button>
          </div>
        </RadixAlertDialog.Content>
      </RadixAlertDialog.Portal>
    </RadixAlertDialog.Root>
  )
}
