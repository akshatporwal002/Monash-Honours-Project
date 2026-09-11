import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'

import { ApiError } from '../../app/api'
import { request } from '../../app/api'
import { Button, Card, CodeBlock } from '../../components/ui'
import { AssessorReviewResponse } from './AssessorReviewResponse'
import { AssessorSuggestionPanel } from './AssessorSuggestionPanel'
import { humanReviewApi } from './assessmentReviewApi'
import type { HumanAssessmentWrite, UnresolvedAssessment } from './assessmentReviewApi'
import { criterionDecisionLabels } from './assessmentReviewPresentation'
import type { CriterionDecision } from './types'
import styles from './assessment.module.css'

type Entry = { decision: '' | CriterionDecision; reason: string; evidenceIds: string[] }

export function AssessorReviewUnresolved({ courseId, reviewedAttemptId, onCheckAccess, onAccessRevoked, onFinalised, moderation }: {
  courseId: string
  reviewedAttemptId?: string
  onCheckAccess: (courseId: string) => Promise<boolean>
  onAccessRevoked: () => void
  onFinalised: () => void
  moderation?: { attemptId: string; stage: string }
}) {
  const fieldPrefix = moderation ? `moderation-${moderation.attemptId}` : 'human'
  const [records, setRecords] = useState<UnresolvedAssessment[]>([])
  const [selected, setSelected] = useState<UnresolvedAssessment | null>(null)
  const [entries, setEntries] = useState<Record<string, Entry>>({})
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')
  const [busy, setBusy] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const key = useRef<string | null>(null)
  const receiptRef = useRef<HTMLParagraphElement>(null)

  const deny = useCallback(() => {
    setRecords([])
    setSelected(null)
    setEntries({})
    setReason('')
    setError('Assessor access is no longer active. Review evidence was removed.')
    onAccessRevoked()
  }, [onAccessRevoked])

  const load = useCallback(async (append = false) => {
    if (moderation) return
    if (!courseId) return
    setBusy(true)
    try {
      if (!(await onCheckAccess(courseId))) { deny(); return }
      const rows = await humanReviewApi.queue(courseId, append ? records.length : 0)
      setRecords((current) => append ? [...current, ...rows] : rows)
      setHasMore(rows.length === 50)
      setError('')
    } catch (caught) {
      if (caught instanceof ApiError && [403, 404].includes(caught.status)) deny()
      else setError('Unresolved work could not be loaded. Reload to retry.')
    } finally { setBusy(false) }
  }, [courseId, deny, onCheckAccess, records.length, moderation])

  useEffect(() => {
    let active = true
    if (!courseId || moderation) return
    async function start() {
      try {
        const rows = await humanReviewApi.queue(courseId)
        if (active) { setRecords(rows); setHasMore(rows.length === 50) }
      } catch (caught) {
        if (!active) return
        if (caught instanceof ApiError && [403, 404].includes(caught.status)) deny()
        else setError('Unresolved work could not be loaded. Reload to retry.')
      }
    }
    void start()
    return () => { active = false }
  }, [courseId, deny, onCheckAccess, moderation])

  const inspect = async (attemptId: string) => {
    setBusy(true)
    try {
      if (!(await onCheckAccess(courseId))) { deny(); return }
      const detail = await humanReviewApi.detail(attemptId)
      setSelected(detail)
      setEntries(Object.fromEntries(detail.criteria.map((criterion) => [criterion.criterion_version_id, { decision: '', reason: '', evidenceIds: [] }])))
      setReason('')
      key.current = null
      setStatus('Frozen evidence loaded. Record a decision and reason for every criterion.')
      setError('')
    } catch (caught) {
      if (caught instanceof ApiError && [403, 404].includes(caught.status)) deny()
      else setError('This attempt could not be inspected. Reload the queue.')
    } finally { setBusy(false) }
  }

  const edit = (id: string, patch: Partial<Entry>) => {
    key.current = null
    setEntries((current) => ({ ...current, [id]: { ...current[id], ...patch } }))
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!selected || busy) return
    const criteria: HumanAssessmentWrite['criteria'] = []
    for (const criterion of selected.criteria) {
      const entry = entries[criterion.criterion_version_id]
      if (!entry?.decision || !entry.reason.trim() || !entry.evidenceIds.length) {
        setError('Each criterion needs a decision, a reason, and at least one approved evidence reference.')
        return
      }
      criteria.push({ criterion_version_id: criterion.criterion_version_id, decision: entry.decision, reason: entry.reason.trim(), evidence_ids: entry.evidenceIds })
    }
    if (!reason.trim()) { setError('Record a reason for confirming the formal result.'); return }
    setBusy(true)
    setError('')
    try {
      if (!(await onCheckAccess(courseId))) { deny(); return }
      key.current ??= crypto.randomUUID()
      const payload = {
        idempotency_key: key.current, expected_token: selected.expected_token, reason: reason.trim(), criteria,
      }
      if (moderation) {
        await request(`/assessment/attempts/${encodeURIComponent(moderation.attemptId)}/moderation/${moderation.stage}`, { method: 'POST', body: JSON.stringify(payload) })
        setStatus('Moderation decision saved. Formal confirmation remains a separate assessor action.')
      } else {
        const receipt = await humanReviewApi.finalise(selected.assessment_attempt_id, payload)
        setStatus(`Formal result ${receipt.result} ${receipt.result_state === 'OVERRIDDEN' ? 'corrected' : 'confirmed'}. Your criterion decisions and reasons are saved.`)
      }
      setSelected(null)
      setEntries({})
      setReason('')
      await load()
      onFinalised()
      receiptRef.current?.focus()
    } catch (caught) {
      if (caught instanceof ApiError && [403, 404].includes(caught.status)) deny()
      else if (caught instanceof ApiError && caught.status === 409) {
        try {
          const current = await humanReviewApi.detail(selected.assessment_attempt_id)
          setSelected(current)
          key.current = null
          setError(moderation ? 'Moderation state changed or another reviewer is required. Reload the moderation queue. Your entries remain available.' : 'This assessment changed or needs moderation. Inspect the refreshed evidence and assessment moderation before confirming again. Your entries remain available.')
        } catch (refreshError) {
          if (refreshError instanceof ApiError && [403, 404].includes(refreshError.status)) deny()
          else setError('The current review could not be refreshed. Your entries remain available. Reload before confirming.')
        }
      } else setError('The action could not be recorded. Your entries remain available. Retry this action.')
    } finally { setBusy(false) }
  }

  return <Card heading={moderation?.stage === 'CORRECTION' ? 'Proposed correction for independent review' : moderation ? 'Independent moderation decision' : 'Unresolved assessment attempts'} eyebrow="Human criterion decisions">
    <p>{moderation ? 'Inspect the frozen evidence and approved anchors. Record your own criterion decisions. This action does not confirm a formal result.' : 'These attempts have no formal decision. Technical faults remain under review without a learner penalty.'}</p>
    {moderation?.stage === 'CORRECTION' && <p>The existing formal result remains in place while a new moderation cycle reviews the proposed correction.</p>}
    {moderation ? <Button variant="secondary" onClick={() => void inspect(moderation.attemptId)} disabled={busy}>Inspect moderation evidence</Button> : <Button variant="secondary" onClick={() => void load()} disabled={busy || !courseId}>Reload unresolved work</Button>}
    {error && <p role="alert" className={styles.alert}>{error}</p>}
    <p role={status ? "status" : undefined} ref={receiptRef} tabIndex={-1}>{status}</p>
    {!moderation && !records.length && <p>No unresolved attempts are currently listed.</p>}
    <ul className={styles.recordList}>
      {records.map((record) => <li key={record.assessment_attempt_id}>
        <Button variant="secondary" disabled={busy} onClick={() => void inspect(record.assessment_attempt_id)}>
          Inspect attempt {record.assessment_attempt_id}, {record.failure_category ?? record.job_state ?? 'awaiting assessment'}
        </Button>
      </li>)}
    </ul>
    {hasMore && <Button variant="secondary" disabled={busy} onClick={() => void load(true)}>Load more unresolved attempts</Button>}
    {reviewedAttemptId && <Button variant="secondary" disabled={busy} onClick={() => void inspect(reviewedAttemptId)}>Record or correct criteria for the selected review record</Button>}
    {selected && <div className={styles.detail}>
      <AssessorSuggestionPanel key={selected.assessment_attempt_id} attemptId={selected.assessment_attempt_id} independent={!!moderation} />
      <AssessorReviewResponse response={selected.response} history={selected.response_history} historicalEvidence={selected.historical_evidence} frozenContext={selected.frozen_context} simulations={selected.simulations} issues={selected.issues} />
      <details><summary>Inspect frozen standard versions</summary><CodeBlock code={JSON.stringify(selected.versions, null, 2)} label="Frozen standard versions" /></details>
      {selected.history.length > 0 && <details open><summary>Earlier human decisions</summary><CodeBlock code={JSON.stringify(selected.history, null, 2)} label="Append-only human decision history" /></details>}
      <form onSubmit={(event) => void submit(event)}>
        {selected.criteria.map((criterion) => {
          const id = criterion.criterion_version_id
          const entry = entries[id] ?? { decision: '', reason: '', evidenceIds: [] }
          const references = [
            ...(selected.response && criterion.evidence_source_types.includes('learner_response') ? [{ id: selected.response.reference.evidence_id, label: 'Whole immutable learner response, including its recorded stages' }] : []),
            ...(criterion.evidence_source_types.includes('simulation_output') ? selected.simulations.filter((run) => run.status === 'completed').map((run) => ({ id: String(run.run_id), label: `Completed simulation ${String(run.run_id)}` })) : []),
          ]
          return <fieldset key={id} disabled={busy || !selected.can_finalise} className={styles.section}>
            <legend>{criterion.learner_description}{criterion.mandatory ? ' (required)' : ''}</legend>
            <p>{criterion.evidence_description}</p>
            <dl>
              <dt>Met</dt><dd>{criterion.met_rule}</dd>
              <dt>Not met</dt><dd>{criterion.not_met_rule}</dd>
              <dt>Not evaluable</dt><dd>{criterion.not_evaluable_rule}</dd>
            </dl>
            <details><summary>Approved anchors and critical error rules</summary><CodeBlock code={JSON.stringify({ anchors: criterion.approved_anchors, critical_errors: criterion.critical_error_rules }, null, 2)} label="Approved criterion rules" /></details>
            <label htmlFor={`${fieldPrefix}-decision-${id}`}>Criterion decision</label>
            <select id={`${fieldPrefix}-decision-${id}`} required value={entry.decision} onChange={(event) => edit(id, { decision: event.target.value as Entry['decision'] })}>
              <option value="">Choose a decision</option>
              {(['MET', 'NOT_MET', 'NOT_EVALUABLE'] as const).map((value) => <option key={value} value={value}>{criterionDecisionLabels[value]}</option>)}
            </select>
            <label htmlFor={`${fieldPrefix}-reason-${id}`}>Criterion reason, including the evidence field used</label>
            <textarea id={`${fieldPrefix}-reason-${id}`} required maxLength={2000} rows={4} value={entry.reason} onChange={(event) => edit(id, { reason: event.target.value })} />
            <fieldset><legend>Evidence used for this criterion</legend>
              {references.map((reference) => <label key={reference.id} style={{ display: 'block' }}>
                <input type="checkbox" checked={entry.evidenceIds.includes(reference.id)} onChange={(event) => edit(id, { evidenceIds: event.target.checked ? [...entry.evidenceIds, reference.id] : entry.evidenceIds.filter((value) => value !== reference.id) })} />
                {reference.label}
              </label>)}
              {!references.length && <p>No approved evidence is available. Keep this attempt under review.</p>}
            </fieldset>
          </fieldset>
        })}
        <label htmlFor={`${fieldPrefix}-confirmation-reason`}>{moderation ? 'Moderation reason' : 'Formal confirmation reason'}</label>
        <textarea id={`${fieldPrefix}-confirmation-reason`} required maxLength={2000} rows={3} value={reason} disabled={busy || !selected.can_finalise} onChange={(event) => { key.current = null; setReason(event.target.value) }} />
        <p>{moderation ? 'The saved pass rule calculates your moderation decision. A disagreement requires explicit resolution before anyone can confirm the result.' : 'The saved pass rule determines PASS or INCOMPLETE from these criterion decisions. This action confirms the result or records a reasoned correction. Earlier decisions remain in the history.'}</p>
        <Button type="submit" disabled={busy || !selected.can_finalise}>{busy ? 'Recording assessment...' : moderation ? 'Record moderation decision' : 'Apply frozen pass rule and confirm result'}</Button>
      </form>
    </div>}
  </Card>
}
