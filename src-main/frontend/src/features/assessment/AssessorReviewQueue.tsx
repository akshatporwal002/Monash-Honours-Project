import { useEffect, useRef, useState } from 'react'
import { CurriculumPanel } from '../../components/CurriculumPanel'

import type { ScopedRoleAssignment } from '../../app/types'
import { ScreenState } from '../../components/ScreenPrimitives'
import { Button, EmptyState, PageHeader } from '../../components/ui'
import {
  ReviewActionDialog,
  ReviewFiltersPanel,
  ReviewWorkspace,
} from './AssessorReviewPanels'
import type { ReviewFilters } from './AssessorReviewPanels'
import { lifecycleLabels, resultLabels } from './assessmentReviewPresentation'
import { useAssessorReviewQueue } from './useAssessorReviewQueue'
import { AssessorReviewUnresolved } from './AssessorReviewUnresolved'
import { AssessorAppeals } from './AssessorAppeals'
import { ReassessmentPanel } from './ReassessmentPanel'
import { AssessmentModerationPanel } from './AssessmentModerationPanel'
import styles from './assessment.module.css'

function activeFilterSummary(filters: ReviewFilters): string {
  const parts = [
    filters.courseId ? `course ${filters.courseId}` : null,
    filters.outcomeId.trim() ? `outcome ${filters.outcomeId.trim()}` : null,
    filters.result ? `result ${resultLabels[filters.result]}` : null,
    filters.resultState ? `result state ${lifecycleLabels[filters.resultState]}` : null,
    filters.reviewFlag.trim() ? `review flag ${filters.reviewFlag.trim()}` : null,
    filters.minimumAgeHours ? `minimum age ${filters.minimumAgeHours} hours` : null,
  ].filter((part): part is string => part !== null)
  return parts.length
    ? `Active filters: ${parts.join(', ')}.`
    : 'No filters are active.'
}

export function AssessorReviewQueue({
  assignments,
  onCheckAccess,
  onAccessRevoked,
}: {
  assignments: ScopedRoleAssignment[]
  onCheckAccess: (courseId: string) => Promise<boolean>
  onAccessRevoked: () => void
}) {
  const [diagnosticsOpen, setDiagnosticsOpen] = useState(false)
  const [moderationOpen, setModerationOpen] = useState(false)
  const queue = useAssessorReviewQueue({ assignments, onCheckAccess, onAccessRevoked })
  /* The AlertDialog opens without a Radix trigger, so focus returns to the
     opening action button manually when the dialog closes (NFR4, AT24).
     A recorded action refreshes the queue, which unmounts and rebuilds the
     action buttons, so the trigger is re-found by action identity once the
     queue has settled rather than held as a (by then detached) node. */
  const screenRef = useRef<HTMLDivElement | null>(null)
  const returnFocusAction = useRef<string | null>(null)
  const dialogAction = queue.pendingAction?.action ?? null

  useEffect(() => {
    // Access checks can overlap evidence reads. Record the return target only
    // after the dialog opens so an earlier detail refresh cannot consume it.
    if (dialogAction !== null) {
      returnFocusAction.current = dialogAction
      return
    }
    const action = returnFocusAction.current
    if (action === null || queue.loading) return
    const trigger = screenRef.current?.querySelector<HTMLButtonElement>(
      `[data-review-action="${action}"]`,
    )
    returnFocusAction.current = null
    trigger?.focus()
  }, [dialogAction, queue.loading, queue.selected])

  return (
    <div className={styles.screen} ref={screenRef}>
      <PageHeader
        eyebrow="Assessor workspace"
        title="Assessment review queue"
        description="Inspect the learner response and evidence before recording an assessor action."
        actions={
          <Button
            variant="secondary"
            onClick={() => void queue.refreshQueue()}
            disabled={queue.loading}
          >
            Reload queue
          </Button>
        }
      />
      {queue.filters.courseId && <>
        <Button variant="secondary" onClick={() => setDiagnosticsOpen(value => !value)}>{diagnosticsOpen ? 'Close diagnostic reviews' : 'Review learning diagnostics'}</Button>
        {diagnosticsOpen && <CurriculumPanel key={queue.filters.courseId} courseId={queue.filters.courseId} staff />}
      </>}
      {queue.error && <p className={styles.alert} role="alert">{queue.error}</p>}
      {queue.accessReady && queue.filters.courseId && <>
        <Button variant="secondary" onClick={() => setModerationOpen(value => !value)}>{moderationOpen ? 'Close assessment moderation' : 'Open assessment moderation'}</Button>
        {moderationOpen && <AssessmentModerationPanel key={queue.filters.courseId} courseId={queue.filters.courseId} onCheckAccess={onCheckAccess} onAccessRevoked={onAccessRevoked} onRecorded={() => void queue.refreshQueue()} />}
      </>}
      {queue.accessReady && queue.filters.courseId && <AssessorAppeals key={`appeals-${queue.filters.courseId}`} courseId={queue.filters.courseId} onOpenDecision={queue.reloadCurrentDetail} />}
      {queue.status && <p className={styles.status} role="status">{queue.status}</p>}
      <ReviewFiltersPanel
        assignments={queue.assessorAssignments}
        filters={queue.filters}
        summaries={queue.summaries}
        loading={queue.loading}
        onUpdate={queue.updateFilters}
        onRefresh={() => void queue.refreshQueue()}
      />
      {queue.accessActive && queue.status && queue.filters.courseId && <AssessorReviewUnresolved
        key={queue.filters.courseId}
        courseId={queue.filters.courseId}
        reviewedAttemptId={queue.selected?.response?.reference.assessment.assessment_attempt_id}
        onCheckAccess={onCheckAccess}
        onAccessRevoked={onAccessRevoked}
        onFinalised={() => void queue.refreshQueue()}
      />}
      {queue.loading && <ScreenState kind="loading" title="Loading review queue" message="Retrieving the assigned course records." />}
      {!queue.loading && queue.records.length === 0 && !queue.error && (
        <EmptyState
          title="No review records"
          description={`No records match the current filters. ${activeFilterSummary(queue.filters)}`}
        />
      )}
      {!queue.loading && queue.selected && (
        <ReviewWorkspace
          records={queue.records}
          selected={queue.selected}
          accessActive={queue.accessActive}
          onSelect={queue.setSelected}
          onOpenAction={(action) => {
            void queue.openAction(action)
          }}
        />
      )}
      {queue.pendingAction && <ReviewActionDialog
        pendingAction={queue.pendingAction}
        overrideResult={queue.overrideResult}
        busy={queue.busy}
        error={queue.error}
        status={queue.status}
        onOverrideChange={queue.setOverrideResult}
        onClose={() => queue.setPendingAction(null)}
        onSubmit={(reason) => void queue.submitAction(reason)}
      />}
      {queue.accessReady && queue.selected && <ReassessmentPanel key={`${queue.selected.decision_id}-${queue.selected.review_revision}`} decisionId={queue.selected.decision_id} revision={queue.selected.review_revision} />}
    </div>
  )
}
