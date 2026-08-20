import { useState } from 'react'

import { ApiError } from '../../app/api'
import type { ScopedRoleAssignment } from '../../app/types'
import { assessmentApi } from './api'
import type { AssessmentResult, AssessmentReviewAction } from './api'
import type { PendingAction } from './AssessorReviewPanels'
import { actionLabels, lifecycleLabels } from './assessmentReviewPresentation'
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
  const [overrideResult, setOverrideResult] = useState<AssessmentResult>('INCOMPLETE')
  const [busy, setBusy] = useState(false)

  /* Dialog focus management (trap, Escape, focus return) now comes from the
     ui AlertDialog primitive; the typed reason lives inside the dialog and is
     handed to submitAction on confirm (plan 006 Step 7). */
  const openAction = async (action: AssessmentReviewAction) => {
    if (!data.selected || !(await data.checkAccess())) {
      setPendingAction(null)
      return
    }
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

  const recordAction = async (action: PendingAction, reason: string) => {
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
    data.setStatus(
      `${actionLabels[action.action]} recorded. Current state: ${lifecycleLabels[response.result_state]}.`,
    )
  }

  const submitAction = async (reason: string) => {
    if (!pendingAction) return
    if (!reason.trim()) {
      data.setError('Record a reason before submitting this assessor action.')
      return
    }
    if (!(await data.checkAccess())) {
      setPendingAction(null)
      return
    }
    setBusy(true)
    data.setError('')
    try {
      await recordAction(pendingAction, reason)
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

  return {
    assessorAssignments,
    ...data,
    pendingAction,
    overrideResult,
    busy,
    setOverrideResult,
    setPendingAction,
    openAction,
    submitAction,
  }
}
