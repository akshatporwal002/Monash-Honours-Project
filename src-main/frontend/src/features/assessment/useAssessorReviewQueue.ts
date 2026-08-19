import { useState } from 'react'
import type { KeyboardEvent as ReactKeyboardEvent, MouseEvent } from 'react'

import { ApiError } from '../../app/api'
import type { ScopedRoleAssignment } from '../../app/types'
import { assessmentApi } from './api'
import type { AssessmentResult, AssessmentReviewAction } from './api'
import type { PendingAction } from './AssessorReviewPanels'
import { actionLabels, readable } from './assessmentReviewPresentation'
import { useReviewDialogFocus } from './useReviewDialogFocus'
import { reviewErrorMessage, useReviewQueueData } from './useReviewQueueData'

export function useAssessorReviewQueue({
  assignments,
  onCheckAccess,
  onAccessRevoked,
}: {
  assignments: ScopedRoleAssignment[]
  onCheckAccess: (courseId: string) => Promise<boolean>
  onAccessRevoked: () => void
}) {
  const assessorAssignments = assignments.filter((assignment) => assignment.role === 'assessor')
  const data = useReviewQueueData({
    initialCourseId: assessorAssignments[0]?.course_id ?? '',
    onCheckAccess,
    onAccessRevoked,
  })
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null)
  const [reason, setReason] = useState('')
  const [overrideResult, setOverrideResult] = useState<AssessmentResult>('INCOMPLETE')
  const [busy, setBusy] = useState(false)
  const [returnFocusAction, setReturnFocusAction] = useState<AssessmentReviewAction | null>(null)
  const focus = useReviewDialogFocus(pendingAction, busy)

  const openAction = async (
    event: MouseEvent<HTMLButtonElement>,
    action: AssessmentReviewAction,
  ) => {
    if (!data.selected || !(await data.checkAccess())) {
      setPendingAction(null)
      return
    }
    focus.captureTrigger(event.currentTarget)
    setReturnFocusAction(action)
    setReason('')
    setOverrideResult(data.selected.result === 'PASS' ? 'INCOMPLETE' : 'PASS')
    setPendingAction({ action, detail: data.selected })
    data.setError('')
    data.setStatus('')
  }

  const reloadAfterConflict = async (action: PendingAction) => {
    try {
      const current = await data.reloadCurrentDetail(action.detail.decision_id)
      setPendingAction((existing) => (
        existing?.detail.decision_id === current.decision_id
          ? { ...existing, detail: current }
          : existing
      ))
      data.setStatus(
        'This review changed elsewhere. Current history was reloaded. Your typed reason is still available.',
      )
    } catch (reloadError) {
      data.setError(reviewErrorMessage(reloadError))
    }
  }

  const recordAction = async (action: PendingAction) => {
    const response = await assessmentApi.reviewAction(action.detail.decision_id, {
      action: action.action,
      reason: reason.trim(),
      expected_result_state: action.detail.result_state,
      expected_review_revision: action.detail.review_revision,
      new_result: action.action === 'OVERRIDE' ? overrideResult : null,
    })
    await data.refreshQueue()
    await data.reloadCurrentDetail(response.decision_id)
    setPendingAction(null)
    setReason('')
    data.setStatus(
      `${actionLabels[action.action]} recorded. Current state: ${readable(response.result_state)}.`,
    )
  }

  const submitAction = async () => {
    if (!pendingAction) return
    if (!reason.trim()) {
      data.setError('Record a reason before submitting this assessor action.')
      focus.reasonRef.current?.focus()
      return
    }
    if (!(await data.checkAccess())) {
      setPendingAction(null)
      return
    }
    setBusy(true)
    data.setError('')
    try {
      await recordAction(pendingAction)
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 409) {
        await reloadAfterConflict(pendingAction)
      } else {
        data.setError(reviewErrorMessage(caught))
      }
    } finally {
      setBusy(false)
    }
  }

  const closeDialogWithEscape = (event: ReactKeyboardEvent<HTMLElement>) => {
    if (focus.closeDialogWithEscape(event)) setPendingAction(null)
  }

  return {
    assessorAssignments,
    ...data,
    pendingAction,
    reason,
    overrideResult,
    busy,
    returnFocusAction,
    triggerRef: focus.triggerRef,
    reasonRef: focus.reasonRef,
    overrideRef: focus.overrideRef,
    submitRef: focus.submitRef,
    setReason,
    setOverrideResult,
    setPendingAction,
    openAction,
    submitAction,
    closeDialogWithEscape,
    wrapFromFirstControl: focus.wrapFromFirstControl,
    wrapFromSubmit: focus.wrapFromSubmit,
  }
}
