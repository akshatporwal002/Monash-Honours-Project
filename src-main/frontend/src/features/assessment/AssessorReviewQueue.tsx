import type { ScopedRoleAssignment } from '../../app/types'
import { PageHeading, ScreenState } from '../../components/ScreenPrimitives'
import {
  ReviewActionDialog,
  ReviewFiltersPanel,
  ReviewWorkspace,
} from './AssessorReviewPanels'
import { useAssessorReviewQueue } from './useAssessorReviewQueue'
import './assessment.css'

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

  return (
    <div className="screen assessment-review">
      <PageHeading
        eyebrow="Assessor workspace"
        title="Assessment review queue"
        description="Inspect the learner response and evidence before recording an assessor action."
        actions={
          <button
            className="button button--secondary"
            onClick={() => void queue.refreshQueue()}
            disabled={queue.loading}
          >
            Reload queue
          </button>
        }
      />
      {queue.error && <p className="form-error" role="alert">{queue.error}</p>}
      {queue.status && <p className="form-status" role="status">{queue.status}</p>}
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
        <ScreenState
          kind="empty"
          title="No review records"
          message="No records match the current filters."
        />
      )}
      {!queue.loading && queue.selected && (
        <ReviewWorkspace
          records={queue.records}
          selected={queue.selected}
          accessActive={queue.accessActive}
          returnFocusAction={queue.returnFocusAction}
          triggerRef={queue.triggerRef}
          onSelect={queue.setSelected}
          onOpenAction={(event, action) => void queue.openAction(event, action)}
        />
      )}
      {queue.pendingAction && <ReviewActionDialog
        pendingAction={queue.pendingAction}
        reason={queue.reason}
        overrideResult={queue.overrideResult}
        busy={queue.busy}
        reasonRef={queue.reasonRef}
        overrideRef={queue.overrideRef}
        submitRef={queue.submitRef}
        onReasonChange={queue.setReason}
        onOverrideChange={queue.setOverrideResult}
        onClose={() => queue.setPendingAction(null)}
        onSubmit={() => void queue.submitAction()}
        onKeyDown={queue.closeDialogWithEscape}
        onFirstControlKeyDown={queue.wrapFromFirstControl}
        onSubmitKeyDown={queue.wrapFromSubmit}
      />}
    </div>
  )
}
