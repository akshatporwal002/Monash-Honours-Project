import type {
  KeyboardEvent as ReactKeyboardEvent,
  MouseEvent,
  RefObject,
} from 'react'

import type { ScopedRoleAssignment } from '../../app/types'
import { Panel } from '../../components/ScreenPrimitives'
import type {
  AssessmentResult,
  AssessmentReviewAction,
  AssessmentReviewDetail,
  ResultState,
} from './api'
import { actionLabels, readable } from './assessmentReviewPresentation'
import { assessmentResultValues, resultStateValues } from './types'

export type ReviewFilters = {
  courseId: string
  outcomeId: string
  result: '' | AssessmentResult
  resultState: '' | ResultState
  reviewFlag: string
  minimumAgeHours: string
}

export type PendingAction = {
  action: AssessmentReviewAction
  detail: AssessmentReviewDetail
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return 'Not recorded'
  if (typeof value === 'string' || typeof value === 'number') return String(value)
  return JSON.stringify(value)
}

export function ReviewFiltersPanel({
  assignments,
  filters,
  summaries,
  loading,
  onUpdate,
  onRefresh,
}: {
  assignments: ScopedRoleAssignment[]
  filters: ReviewFilters
  summaries: { state: ResultState, count: number }[]
  loading: boolean
  onUpdate: <Key extends keyof ReviewFilters>(key: Key, value: ReviewFilters[Key]) => void
  onRefresh: () => void
}) {
  return (
    <Panel title="Queue filters" eyebrow="Assigned course and review state">
      <div className="assessment-form-grid">
        <label className="field">
          <span>Assigned course</span>
          <select
            aria-label="Assigned course"
            value={filters.courseId}
            onChange={(event) => onUpdate('courseId', event.target.value)}
          >
            <option value="">Select an assigned course</option>
            {assignments.map((assignment) => (
              <option key={assignment.id} value={assignment.course_id}>
                {assignment.course_id}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Outcome ID</span>
          <input
            aria-label="Outcome ID"
            value={filters.outcomeId}
            onChange={(event) => onUpdate('outcomeId', event.target.value)}
          />
        </label>
        <label className="field">
          <span>Result</span>
          <select
            aria-label="Result"
            value={filters.result}
            onChange={(event) => (
              onUpdate('result', event.target.value as ReviewFilters['result'])
            )}
          >
            <option value="">All results</option>
            {assessmentResultValues.map((result) => (
              <option key={result} value={result}>{readable(result)}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Result state</span>
          <select
            aria-label="Result state"
            value={filters.resultState}
            onChange={(event) => (
              onUpdate('resultState', event.target.value as ReviewFilters['resultState'])
            )}
          >
            <option value="">All result states</option>
            {resultStateValues.map((state) => (
              <option key={state} value={state}>{readable(state)}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Review flag</span>
          <input
            aria-label="Review flag"
            value={filters.reviewFlag}
            onChange={(event) => onUpdate('reviewFlag', event.target.value)}
          />
        </label>
        <label className="field">
          <span>Minimum age in hours</span>
          <input
            aria-label="Minimum age in hours"
            type="number"
            min="0"
            value={filters.minimumAgeHours}
            onChange={(event) => onUpdate('minimumAgeHours', event.target.value)}
          />
        </label>
      </div>
      <div className="assessment-actions">
        <button className="button button--primary" onClick={onRefresh} disabled={loading}>
          {loading ? 'Loading queue...' : 'Apply filters'}
        </button>
      </div>
      <ul className="assessment-review-summary" aria-label="Result state summary">
        {summaries.map(({ state, count }) => (
          <li key={state}><strong>{count}</strong><span>{readable(state)}</span></li>
        ))}
      </ul>
    </Panel>
  )
}

function ReviewRecordList({
  records,
  selected,
  onSelect,
}: {
  records: AssessmentReviewDetail[]
  selected: AssessmentReviewDetail
  onSelect: (record: AssessmentReviewDetail) => void
}) {
  return (
    <ul className="assessment-review-list">
      {records.map((record) => (
        <li key={record.decision_id}>
          <button
            className={record.decision_id === selected.decision_id ? 'active' : ''}
            aria-pressed={record.decision_id === selected.decision_id}
            onClick={() => onSelect(record)}
          >
            <strong>{record.outcome_id}</strong>
            <span>{readable(record.result_state)}. {readable(record.result)}</span>
            <small>Revision {record.review_revision}</small>
          </button>
        </li>
      ))}
    </ul>
  )
}

function EvidenceDetail({ selected }: { selected: AssessmentReviewDetail }) {
  return (
    <Panel title="Response and evidence" eyebrow="Read before acting">
      <section className="assessment-evidence">
        <h3>System and Quality Review</h3>
        <p><strong>System reason:</strong> {selected.system_reason}</p>
        <p><strong>Quality Review:</strong> {readable(selected.quality_review_status)}</p>
      </section>
      <section className="assessment-evidence">
        <h3>Original response</h3>
        <p>{selected.response_text || 'No response text was recorded.'}</p>
      </section>
      <section className="assessment-evidence">
        <h3>Response conditions</h3>
        <p>{displayValue(selected.response_conditions)}</p>
      </section>
      <section className="assessment-evidence">
        <h3>Criterion decisions</h3>
        <ul>
          {selected.criteria.map((criterion) => (
            <li key={criterion.criterion_version_id}>
              <strong>{readable(criterion.decision)}</strong>
              <span>{criterion.reason}</span>
              <small>
                Evidence: {displayValue(criterion.evidence_references)}. Criterion version{' '}
                {criterion.criterion_version}.
              </small>
              <small>
                Evaluator: {criterion.evaluator_reference}. Model:{' '}
                {displayValue(criterion.model_version)}. Prompt:{' '}
                {displayValue(criterion.prompt_version)}. Retrieval:{' '}
                {displayValue(criterion.retrieval_version)}.
              </small>
            </li>
          ))}
        </ul>
      </section>
      <section className="assessment-evidence">
        <h3>Missing evidence</h3>
        {selected.missing_criterion_version_ids.length ? (
          <ul>
            {selected.missing_criterion_version_ids.map((id) => <li key={id}>{id}</li>)}
          </ul>
        ) : (
          <p>No missing criteria were recorded.</p>
        )}
      </section>
      <section className="assessment-evidence">
        <h3>Versions</h3>
        <dl>
          {Object.entries(selected.versions).map(([key, value]) => (
            <div key={key}><dt>{readable(key)}</dt><dd>{displayValue(value)}</dd></div>
          ))}
        </dl>
      </section>
      <section className="assessment-evidence">
        <h3>Review history</h3>
        {selected.history.length ? (
          <ol>
            {selected.history.map((item) => (
              <li key={item.id}>
                <strong>{readable(item.action)}</strong>, revision {item.review_revision}.{' '}
                {item.reason}
              </li>
            ))}
          </ol>
        ) : (
          <p>No assessor actions have been recorded.</p>
        )}
      </section>
    </Panel>
  )
}

function ReviewActions({
  selected,
  accessActive,
  returnFocusAction,
  triggerRef,
  onOpenAction,
}: {
  selected: AssessmentReviewDetail
  accessActive: boolean
  returnFocusAction: AssessmentReviewAction | null
  triggerRef: RefObject<HTMLButtonElement | null>
  onOpenAction: (event: MouseEvent<HTMLButtonElement>, action: AssessmentReviewAction) => void
}) {
  const actions: AssessmentReviewAction[] = [
    'CONFIRM',
    'OVERRIDE',
    'WITHHOLD',
    'VOID',
    'RETURN',
  ]
  return (
    <Panel title="Assessor action" eyebrow="Record a reviewed decision">
      <p className="assessment-muted">
        Current result: {readable(selected.result)}. Current state:{' '}
        {readable(selected.result_state)}. Every action needs a recorded reason.
      </p>
      {accessActive ? (
        <div className="assessment-actions assessment-actions--start">
          {actions.map((action) => (
            <button
              key={action}
              ref={returnFocusAction === action ? triggerRef : undefined}
              className="button button--secondary"
              onClick={(event) => onOpenAction(event, action)}
            >
              {actionLabels[action]}
            </button>
          ))}
        </div>
      ) : (
        <p className="form-error" role="alert">
          Assessor access is no longer active. Action controls are unavailable.
        </p>
      )}
    </Panel>
  )
}

export function ReviewWorkspace({
  records,
  selected,
  accessActive,
  returnFocusAction,
  triggerRef,
  onSelect,
  onOpenAction,
}: {
  records: AssessmentReviewDetail[]
  selected: AssessmentReviewDetail
  accessActive: boolean
  returnFocusAction: AssessmentReviewAction | null
  triggerRef: RefObject<HTMLButtonElement | null>
  onSelect: (record: AssessmentReviewDetail) => void
  onOpenAction: (event: MouseEvent<HTMLButtonElement>, action: AssessmentReviewAction) => void
}) {
  return (
    <div className="assessment-review-layout">
      <Panel title="Review records" eyebrow="Select a learner response">
        <ReviewRecordList records={records} selected={selected} onSelect={onSelect} />
      </Panel>
      <div className="assessment-review-detail">
        <EvidenceDetail selected={selected} />
        <ReviewActions
          selected={selected}
          accessActive={accessActive}
          returnFocusAction={returnFocusAction}
          triggerRef={triggerRef}
          onOpenAction={onOpenAction}
        />
      </div>
    </div>
  )
}

export function ReviewActionDialog({
  pendingAction,
  reason,
  overrideResult,
  busy,
  reasonRef,
  overrideRef,
  submitRef,
  onReasonChange,
  onOverrideChange,
  onClose,
  onSubmit,
  onKeyDown,
  onFirstControlKeyDown,
  onSubmitKeyDown,
}: {
  pendingAction: PendingAction
  reason: string
  overrideResult: AssessmentResult
  busy: boolean
  reasonRef: RefObject<HTMLTextAreaElement | null>
  overrideRef: RefObject<HTMLSelectElement | null>
  submitRef: RefObject<HTMLButtonElement | null>
  onReasonChange: (value: string) => void
  onOverrideChange: (value: AssessmentResult) => void
  onClose: () => void
  onSubmit: () => void
  onKeyDown: (event: ReactKeyboardEvent<HTMLElement>) => void
  onFirstControlKeyDown: (event: ReactKeyboardEvent<HTMLElement>) => void
  onSubmitKeyDown: (event: ReactKeyboardEvent<HTMLButtonElement>) => void
}) {
  return (
    <div
      className="confirm-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="review-action-title"
      onKeyDownCapture={onKeyDown}
    >
      <section className="confirm-dialog assessment-review-dialog">
        <p className="eyebrow">Assessor decision</p>
        <h2 id="review-action-title">{actionLabels[pendingAction.action]}</h2>
        <p>Record why this action is appropriate for the response and evidence shown above.</p>
        {pendingAction.action === 'OVERRIDE' && (
          <label className="field">
            <span>Replacement result</span>
            <select
              ref={overrideRef}
              aria-label="Replacement result"
              value={overrideResult}
              onKeyDown={onFirstControlKeyDown}
              onChange={(event) => onOverrideChange(event.target.value as AssessmentResult)}
            >
              {assessmentResultValues.map((result) => (
                <option key={result} value={result}>{readable(result)}</option>
              ))}
            </select>
          </label>
        )}
        <label className="field">
          <span>Reason</span>
          <textarea
            ref={reasonRef}
            aria-label="Reason"
            value={reason}
            onKeyDown={pendingAction.action === 'OVERRIDE' ? undefined : onFirstControlKeyDown}
            onChange={(event) => onReasonChange(event.target.value)}
            required
          />
        </label>
        <div className="assessment-actions">
          <button className="button button--ghost" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button
            ref={submitRef}
            className="button button--primary"
            onKeyDown={onSubmitKeyDown}
            onClick={onSubmit}
            disabled={busy}
          >
            {busy ? 'Recording action...' : actionLabels[pendingAction.action]}
          </button>
        </div>
      </section>
    </div>
  )
}
