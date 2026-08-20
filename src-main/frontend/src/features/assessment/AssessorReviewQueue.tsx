import { useEffect, useRef } from 'react'

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
  const queue = useAssessorReviewQueue({ assignments, onCheckAccess, onAccessRevoked })
  /* The AlertDialog opens without a Radix trigger, so focus returns to the
     opening action button manually when the dialog closes (NFR4, AT24).
     A recorded action refreshes the queue, which unmounts and rebuilds the
     action buttons, so the trigger is re-found by action identity once the
     queue has settled rather than held as a (by then detached) node. */
  const screenRef = useRef<HTMLDivElement | null>(null)
  const returnFocusAction = useRef<string | null>(null)
  const dialogOpen = queue.pendingAction !== null

  useEffect(() => {
    const action = returnFocusAction.current
    if (dialogOpen || action === null || queue.loading) return
    const trigger = screenRef.current?.querySelector<HTMLButtonElement>(
      `[data-review-action="${action}"]`,
    )
    returnFocusAction.current = null
    trigger?.focus()
  }, [dialogOpen, queue.loading, queue.selected])

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
      {queue.error && <p className={styles.alert} role="alert">{queue.error}</p>}
      {queue.status && <p className={styles.status} role="status">{queue.status}</p>}
      <ReviewFiltersPanel
        assignments={queue.assessorAssignments}
        filters={queue.filters}
        summaries={queue.summaries}
        loading={queue.loading}
        onUpdate={queue.updateFilters}
        onRefresh={() => void queue.refreshQueue()}
      />
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
            returnFocusAction.current = action
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
    </div>
  )
}
