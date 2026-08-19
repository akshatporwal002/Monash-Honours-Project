import { useCallback, useEffect, useRef } from 'react'
import type { KeyboardEvent as ReactKeyboardEvent } from 'react'

import type { PendingAction } from './AssessorReviewPanels'

export function useReviewDialogFocus(pendingAction: PendingAction | null, busy: boolean) {
  const triggerRef = useRef<HTMLButtonElement | null>(null)
  const reasonRef = useRef<HTMLTextAreaElement | null>(null)
  const overrideRef = useRef<HTMLSelectElement | null>(null)
  const submitRef = useRef<HTMLButtonElement | null>(null)
  const restoreTriggerFocus = useCallback((fallback: HTMLElement | null) => {
    ;(triggerRef.current ?? fallback)?.focus()
  }, [])

  useEffect(() => {
    if (!pendingAction) return
    const previousFocus = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null
    const firstControl = pendingAction.action === 'OVERRIDE'
      ? overrideRef.current
      : reasonRef.current
    firstControl?.focus()
    return () => {
      restoreTriggerFocus(previousFocus)
    }
  }, [pendingAction, restoreTriggerFocus])

  const captureTrigger = (element: HTMLButtonElement) => {
    triggerRef.current = element
  }

  const closeDialogWithEscape = (event: ReactKeyboardEvent<HTMLElement>) => {
    if (event.key !== 'Escape' || busy) return false
    event.preventDefault()
    return true
  }

  const wrapFromFirstControl = (event: ReactKeyboardEvent<HTMLElement>) => {
    if (event.key === 'Tab' && event.shiftKey) {
      event.preventDefault()
      submitRef.current?.focus()
    }
  }

  const wrapFromSubmit = (event: ReactKeyboardEvent<HTMLButtonElement>) => {
    if (event.key === 'Tab' && !event.shiftKey) {
      event.preventDefault()
      ;(overrideRef.current ?? reasonRef.current)?.focus()
    }
  }

  return {
    triggerRef,
    reasonRef,
    overrideRef,
    submitRef,
    captureTrigger,
    closeDialogWithEscape,
    wrapFromFirstControl,
    wrapFromSubmit,
  }
}
