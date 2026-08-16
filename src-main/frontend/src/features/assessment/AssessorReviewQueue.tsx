import { useEffect, useMemo, useRef, useState } from 'react'
import type { KeyboardEvent as ReactKeyboardEvent, MouseEvent } from 'react'
import { ApiError } from '../../app/api'
import type { ScopedRoleAssignment } from '../../app/types'
import { PageHeading, Panel, ScreenState } from '../../components/ScreenPrimitives'
import { assessmentApi } from './api'
import type { AssessmentResult, AssessmentReviewAction, AssessmentReviewDetail, ResultState } from './api'
import { assessmentResultValues, resultStateValues } from './types'
import './assessment.css'

type ReviewFilters = {
  courseId: string
  outcomeId: string
  result: '' | AssessmentResult
  resultState: '' | ResultState
  reviewFlag: string
  minimumAgeHours: string
}

type PendingAction = {
  action: AssessmentReviewAction
  detail: AssessmentReviewDetail
}

const actionLabels: Record<AssessmentReviewAction, string> = {
  CONFIRM: 'Confirm result',
  OVERRIDE: 'Override result',
  WITHHOLD: 'Withhold result',
  VOID: 'Void result',
  RETURN: 'Return for review',
}

function readable(value: string | null): string {
  return value ? value.toLowerCase().replaceAll('_', ' ') : 'Not set'
}

function detailError(error: unknown): string {
  if (!(error instanceof ApiError)) return 'The review service could not be reached. Your filters and typed reason remain available.'
  if (error.status === 403) return 'Your assessor permission no longer allows this action.'
  if (error.status === 404) return 'This review record is no longer available in your assigned course.'
  if (error.status === 422) return 'The review action could not be validated. Check the current record and reason.'
  return 'The review service could not complete the request. Your filters and typed reason remain available.'
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return 'Not recorded'
  if (typeof value === 'string' || typeof value === 'number') return String(value)
  return JSON.stringify(value)
}

export function AssessorReviewQueue({
  assignments,
  onCheckAccess,
  onAccessRevoked,
}: {
  assignments: ScopedRoleAssignment[]
  onCheckAccess: () => Promise<boolean>
  onAccessRevoked: () => void
}) {
  const assessorAssignments = assignments.filter((assignment) => assignment.role === 'assessor')
  const [filters, setFilters] = useState<ReviewFilters>({
    courseId: assessorAssignments[0]?.course_id ?? '', outcomeId: '', result: '', resultState: '', reviewFlag: '', minimumAgeHours: '',
  })
  const [records, setRecords] = useState<AssessmentReviewDetail[]>([])
  const [selected, setSelected] = useState<AssessmentReviewDetail | null>(null)
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null)
  const [reason, setReason] = useState('')
  const [overrideResult, setOverrideResult] = useState<AssessmentResult>('INCOMPLETE')
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [accessActive, setAccessActive] = useState(true)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')
  const [returnFocusAction, setReturnFocusAction] = useState<AssessmentReviewAction | null>(null)
  const triggerRef = useRef<HTMLButtonElement | null>(null)
  const reasonRef = useRef<HTMLTextAreaElement | null>(null)
  const overrideRef = useRef<HTMLSelectElement | null>(null)
  const submitRef = useRef<HTMLButtonElement | null>(null)

  const summaries = useMemo(() => resultStateValues.map((state) => ({
    state,
    count: records.filter((record) => record.result_state === state).length,
  })), [records])

  const updateFilters = <Key extends keyof ReviewFilters>(key: Key, value: ReviewFilters[Key]) => {
    setFilters((current) => ({ ...current, [key]: value }))
    setError('')
  }

  const refreshQueue = async () => {
    if (!filters.courseId) {
      setRecords([])
      setSelected(null)
      setError('Select an assigned course before loading review records.')
      return
    }
    if (!(await checkAccess())) return
    setLoading(true)
    setError('')
    try {
      const queue = await assessmentApi.reviewQueue(filters.courseId, {
        outcome_id: filters.outcomeId.trim() || undefined,
        result: filters.result || undefined,
        result_state: filters.resultState || undefined,
        review_flag: filters.reviewFlag.trim() || undefined,
        minimum_age_hours: filters.minimumAgeHours ? Number(filters.minimumAgeHours) : undefined,
      })
      setRecords(queue)
      setSelected((current) => queue.find((record) => record.decision_id === current?.decision_id) ?? queue[0] ?? null)
      setStatus(`${queue.length} review record${queue.length === 1 ? '' : 's'} loaded.`)
    } catch (caught) {
      setError(detailError(caught))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    let cancelled = false
    async function loadAssignedCourse() {
      await Promise.resolve()
      let active: boolean
      try {
        active = await onCheckAccess()
      } catch {
        if (!cancelled) setError('Assessor access could not be refreshed. No review records were loaded.')
        return
      }
      if (cancelled) return
      setAccessActive(active)
      if (!active) {
        setRecords([])
        setSelected(null)
        setStatus('Assessor access has expired. Review action controls were removed.')
        onAccessRevoked()
        return
      }
      setLoading(true)
      setError('')
      try {
        const queue = await assessmentApi.reviewQueue(filters.courseId, {})
        if (cancelled) return
        setRecords(queue)
        setSelected(queue[0] ?? null)
        setStatus(`${queue.length} review record${queue.length === 1 ? '' : 's'} loaded.`)
      } catch (caught) {
        if (!cancelled) setError(detailError(caught))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    if (filters.courseId) void loadAssignedCourse()
    return () => { cancelled = true }
  }, [filters.courseId, onCheckAccess, onAccessRevoked])

  useEffect(() => {
    if (!pendingAction) return
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
    ;(pendingAction.action === 'OVERRIDE' ? overrideRef.current : reasonRef.current)?.focus()
    return () => {
      ;(triggerRef.current ?? previousFocus)?.focus()
    }
  }, [pendingAction])

  const checkAccess = async (): Promise<boolean> => {
    try {
      const active = await onCheckAccess()
      setAccessActive(active)
      if (!active) {
        setPendingAction(null)
        setRecords([])
        setSelected(null)
        setStatus('Assessor access has expired. Review action controls were removed.')
        onAccessRevoked()
      }
      return active
    } catch {
      setError('Assessor access could not be refreshed. No review action was sent.')
      return false
    }
  }

  const closeDialogWithEscape = (event: ReactKeyboardEvent<HTMLElement>) => {
    if (event.key === 'Escape' && !busy) {
      event.preventDefault()
      setPendingAction(null)
    }
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

  const openAction = async (event: MouseEvent<HTMLButtonElement>, action: AssessmentReviewAction) => {
    if (!selected || !(await checkAccess())) return
    triggerRef.current = event.currentTarget
    setReturnFocusAction(action)
    setReason('')
    setOverrideResult(selected.result === 'PASS' ? 'INCOMPLETE' : 'PASS')
    setPendingAction({ action, detail: selected })
    setError('')
    setStatus('')
  }

  const reloadCurrentDetail = async (decisionId: string) => {
    const current = await assessmentApi.reviewDetail(decisionId)
    setSelected(current)
    setRecords((items) => items.map((item) => item.decision_id === current.decision_id ? current : item))
    return current
  }

  const submitAction = async () => {
    if (!pendingAction) return
    if (!reason.trim()) {
      setError('Record a reason before submitting this assessor action.')
      reasonRef.current?.focus()
      return
    }
    if (!(await checkAccess())) return
    setBusy(true)
    setError('')
    try {
      const response = await assessmentApi.reviewAction(pendingAction.detail.decision_id, {
        action: pendingAction.action,
        reason: reason.trim(),
        expected_result_state: pendingAction.detail.result_state,
        expected_review_revision: pendingAction.detail.review_revision,
        new_result: pendingAction.action === 'OVERRIDE' ? overrideResult : null,
      })
      await refreshQueue()
      await reloadCurrentDetail(response.decision_id)
      setPendingAction(null)
      setReason('')
      setStatus(`${actionLabels[pendingAction.action]} recorded. Current state: ${readable(response.result_state)}.`)
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 409) {
        try {
          const current = await reloadCurrentDetail(pendingAction.detail.decision_id)
          setPendingAction((existing) => existing && existing.detail.decision_id === current.decision_id
            ? { ...existing, detail: current }
            : existing)
          setStatus('This review changed elsewhere. Current history was reloaded. Your typed reason is still available.')
        } catch (reloadError) {
          setError(detailError(reloadError))
        }
      } else {
        setError(detailError(caught))
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="screen assessment-review">
      <PageHeading
        eyebrow="Assessor workspace"
        title="Assessment review queue"
        description="Inspect the learner response and evidence before recording an assessor action."
        actions={<button className="button button--secondary" onClick={() => void refreshQueue()} disabled={loading}>Reload queue</button>}
      />
      {error && <p className="form-error" role="alert">{error}</p>}
      {status && <p className="form-status" role="status">{status}</p>}
      <Panel title="Queue filters" eyebrow="Assigned course and review state">
        <div className="assessment-form-grid">
          <label className="field"><span>Assigned course</span><select aria-label="Assigned course" value={filters.courseId} onChange={(event) => updateFilters('courseId', event.target.value)}>{assessorAssignments.map((assignment) => <option key={assignment.id} value={assignment.course_id}>{assignment.course_id}</option>)}</select></label>
          <label className="field"><span>Outcome ID</span><input aria-label="Outcome ID" value={filters.outcomeId} onChange={(event) => updateFilters('outcomeId', event.target.value)} /></label>
          <label className="field"><span>Result</span><select aria-label="Result" value={filters.result} onChange={(event) => updateFilters('result', event.target.value as ReviewFilters['result'])}><option value="">All results</option>{assessmentResultValues.map((result) => <option key={result} value={result}>{readable(result)}</option>)}</select></label>
          <label className="field"><span>Result state</span><select aria-label="Result state" value={filters.resultState} onChange={(event) => updateFilters('resultState', event.target.value as ReviewFilters['resultState'])}><option value="">All result states</option>{resultStateValues.map((state) => <option key={state} value={state}>{readable(state)}</option>)}</select></label>
          <label className="field"><span>Review flag</span><input aria-label="Review flag" value={filters.reviewFlag} onChange={(event) => updateFilters('reviewFlag', event.target.value)} /></label>
          <label className="field"><span>Minimum age in hours</span><input aria-label="Minimum age in hours" type="number" min="0" value={filters.minimumAgeHours} onChange={(event) => updateFilters('minimumAgeHours', event.target.value)} /></label>
        </div>
        <div className="assessment-actions"><button className="button button--primary" onClick={() => void refreshQueue()} disabled={loading}>{loading ? 'Loading queue...' : 'Apply filters'}</button></div>
        <ul className="assessment-review-summary" aria-label="Result state summary">{summaries.map(({ state, count }) => <li key={state}><strong>{count}</strong><span>{readable(state)}</span></li>)}</ul>
      </Panel>
      {loading && <ScreenState kind="loading" title="Loading review queue" message="Retrieving the assigned course records." />}
      {!loading && records.length === 0 && !error && <ScreenState kind="empty" title="No review records" message="No records match the current filters." />}
      {!loading && selected && (
        <div className="assessment-review-layout">
          <Panel title="Review records" eyebrow="Select a learner response">
            <ul className="assessment-review-list">{records.map((record) => <li key={record.decision_id}><button className={record.decision_id === selected.decision_id ? 'active' : ''} aria-pressed={record.decision_id === selected.decision_id} onClick={() => setSelected(record)}><strong>{record.outcome_id}</strong><span>{readable(record.result_state)}. {readable(record.result)}</span><small>Revision {record.review_revision}</small></button></li>)}</ul>
          </Panel>
          <div className="assessment-review-detail">
            <Panel title="Response and evidence" eyebrow="Read before acting">
              <section className="assessment-evidence"><h3>System and Quality Review</h3><p><strong>System reason:</strong> {selected.system_reason}</p><p><strong>Quality Review:</strong> {readable(selected.quality_review_status)}</p></section>
              <section className="assessment-evidence"><h3>Original response</h3><p>{selected.response_text || 'No response text was recorded.'}</p></section>
              <section className="assessment-evidence"><h3>Response conditions</h3><p>{displayValue(selected.response_conditions)}</p></section>
              <section className="assessment-evidence"><h3>Criterion decisions</h3><ul>{selected.criteria.map((criterion) => <li key={criterion.criterion_version_id}><strong>{readable(criterion.decision)}</strong><span>{criterion.reason}</span><small>Evidence: {displayValue(criterion.evidence_references)}. Criterion version {criterion.criterion_version}.</small><small>Evaluator: {criterion.evaluator_reference}. Model: {displayValue(criterion.model_version)}. Prompt: {displayValue(criterion.prompt_version)}. Retrieval: {displayValue(criterion.retrieval_version)}.</small></li>)}</ul></section>
              <section className="assessment-evidence"><h3>Missing evidence</h3>{selected.missing_criterion_version_ids.length ? <ul>{selected.missing_criterion_version_ids.map((id) => <li key={id}>{id}</li>)}</ul> : <p>No missing criteria were recorded.</p>}</section>
              <section className="assessment-evidence"><h3>Versions</h3><dl>{Object.entries(selected.versions).map(([key, value]) => <div key={key}><dt>{readable(key)}</dt><dd>{displayValue(value)}</dd></div>)}</dl></section>
              <section className="assessment-evidence"><h3>Review history</h3>{selected.history.length ? <ol>{selected.history.map((item) => <li key={item.id}><strong>{readable(item.action)}</strong>, revision {item.review_revision}. {item.reason}</li>)}</ol> : <p>No assessor actions have been recorded.</p>}</section>
            </Panel>
            <Panel title="Assessor action" eyebrow="Record a reviewed decision">
              <p className="assessment-muted">Current result: {readable(selected.result)}. Current state: {readable(selected.result_state)}. Every action needs a recorded reason.</p>
              {accessActive ? <div className="assessment-actions assessment-actions--start">{(['CONFIRM', 'OVERRIDE', 'WITHHOLD', 'VOID', 'RETURN'] as AssessmentReviewAction[]).map((action) => <button key={action} ref={returnFocusAction === action ? triggerRef : undefined} className="button button--secondary" onClick={(event) => void openAction(event, action)}>{actionLabels[action]}</button>)}</div> : <p className="form-error" role="alert">Assessor access is no longer active. Action controls are unavailable.</p>}
            </Panel>
          </div>
        </div>
      )}
      {pendingAction && <div className="confirm-overlay" role="dialog" aria-modal="true" aria-labelledby="review-action-title" onKeyDownCapture={closeDialogWithEscape}><section className="confirm-dialog assessment-review-dialog"><p className="eyebrow">Assessor decision</p><h2 id="review-action-title">{actionLabels[pendingAction.action]}</h2><p>Record why this action is appropriate for the response and evidence shown above.</p>{pendingAction.action === 'OVERRIDE' && <label className="field"><span>Replacement result</span><select ref={overrideRef} aria-label="Replacement result" value={overrideResult} onKeyDown={wrapFromFirstControl} onChange={(event) => setOverrideResult(event.target.value as AssessmentResult)}>{assessmentResultValues.map((result) => <option key={result} value={result}>{readable(result)}</option>)}</select></label>}<label className="field"><span>Reason</span><textarea ref={reasonRef} aria-label="Reason" value={reason} onKeyDown={pendingAction.action === 'OVERRIDE' ? undefined : wrapFromFirstControl} onChange={(event) => setReason(event.target.value)} required /></label><div className="assessment-actions"><button className="button button--ghost" onClick={() => setPendingAction(null)} disabled={busy}>Cancel</button><button ref={submitRef} className="button button--primary" onKeyDown={wrapFromSubmit} onClick={() => void submitAction()} disabled={busy}>{busy ? 'Recording action...' : actionLabels[pendingAction.action]}</button></div></section></div>}
    </div>
  )
}
