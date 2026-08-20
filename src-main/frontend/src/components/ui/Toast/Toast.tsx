import * as RadixToast from '@radix-ui/react-toast'
import { useCallback, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import { cx } from '../cx'
import styles from './Toast.module.css'
import { ToastContext } from './toastContext'
import type { ToastOptions } from './toastContext'

interface ToastEntry extends ToastOptions {
  id: number
  message: string
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastEntry[]>([])

  const toast = useCallback((message: string, options?: ToastOptions) => {
    setToasts((current) => [...current, { id: Date.now() + Math.random(), message, ...options }])
  }, [])

  const value = useMemo(() => ({ toast }), [toast])

  return (
    <ToastContext.Provider value={value}>
      <RadixToast.Provider swipeDirection="right" duration={5000}>
        {children}
        {toasts.map((entry) => (
          <RadixToast.Root
            key={entry.id}
            className={cx(
              'll-root',
              styles.toast,
              entry.tone === 'affirm' && styles.affirm,
              entry.tone === 'fault' && styles.fault,
            )}
            onOpenChange={(open) => {
              if (!open) setToasts((current) => current.filter((toastEntry) => toastEntry.id !== entry.id))
            }}
          >
            <RadixToast.Description className={styles.message}>{entry.message}</RadixToast.Description>
          </RadixToast.Root>
        ))}
        <RadixToast.Viewport className={cx('ll-root', styles.viewport)} label="Notifications" />
      </RadixToast.Provider>
    </ToastContext.Provider>
  )
}
