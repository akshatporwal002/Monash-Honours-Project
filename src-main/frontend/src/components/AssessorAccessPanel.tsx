import { useEffect, useState } from 'react'

import { ApiError, api } from '../app/api'
import type { ApiSchemas } from '../api/generated'
import { Button, Field, Input, Select, Tag, Textarea } from './ui'
import styles from './TaskReviewPanel.module.css'

type Candidate = ApiSchemas['AssessorCandidateRead']
type Eligibility = ApiSchemas['AssessorEligibilityRead']
type Grant = ApiSchemas['ScopedRoleAssignmentHistoryRead']

export function AssessorAccessPanel({ courseId, administrator = false }: { courseId: string; administrator?: boolean }) {
  const [candidates, setCandidates] = useState<Candidate[]>([])
  const [eligibility, setEligibility] = useState<Eligibility[]>([])
  const [grants, setGrants] = useState<Grant[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [reason, setReason] = useState('')
  const [endDate, setEndDate] = useState('')
  const [candidateOffset, setCandidateOffset] = useState(0)
  const [historyOffset, setHistoryOffset] = useState(0)
  const [reload, setReload] = useState(0)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const selected = candidates.find((row) => String(row.subject_user_id) === selectedId)

  useEffect(() => {
    const controller = new AbortController()
    void Promise.all([
      api.assessorAccess.candidates(courseId, candidateOffset, controller.signal),
      api.assessorAccess.eligibilityHistory(courseId, historyOffset, controller.signal),
      administrator ? api.assessorAccess.grantHistory(courseId, historyOffset, controller.signal) : Promise.resolve([] as Grant[]),
    ]).then(([people, approvals, appointments]) => {
      if (controller.signal.aborted) return
      setCandidates(people)
      setEligibility(approvals)
      setGrants(appointments)
      setSelectedId((current) => people.some((person) => String(person.subject_user_id) === current) ? current : people[0] ? String(people[0].subject_user_id) : '')
      setLoading(false)
    }).catch((caught: unknown) => {
      if (controller.signal.aborted) return
      setError(caught instanceof ApiError ? caught.message : 'Assessor access could not be loaded.')
      setLoading(false)
    })
    return () => controller.abort()
  }, [courseId, administrator, candidateOffset, historyOffset, reload])

  const refresh = () => { setLoading(true); setError(''); setReload((value) => value + 1) }
  const record = async (action: 'APPROVED' | 'WITHDRAWN' | 'GRANT' | 'REVOKE', assignmentId?: string) => {
    if (busy || loading || error || !reason.trim() || (action !== 'REVOKE' && !selected)) return
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const validUntil = endDate ? new Date(endDate).toISOString() : null
      if (action === 'REVOKE' && assignmentId) {
        await api.assessorAccess.revoke(assignmentId, reason)
      } else if (action === 'GRANT' && selected) {
        await api.assessorAccess.grant(courseId, { subject_user_id: selected.subject_user_id, role: 'assessor', reason, valid_until: validUntil })
      } else if ((action === 'APPROVED' || action === 'WITHDRAWN') && selected) {
        await api.assessorAccess.recordEligibility(courseId, {
          subject_user_id: selected.subject_user_id, state: action,
          expected_version: selected.latest_approval?.version ?? 0, reason,
          valid_until: action === 'APPROVED' ? validUntil : null,
        })
      }
      setReason('')
      setEndDate('')
      refresh()
      setNotice(action === 'APPROVED' ? 'Eligibility approved. An administrator must record a separate assessor grant.' : action === 'GRANT' ? 'Assessor grant recorded.' : action === 'REVOKE' ? 'Assessor grant revoked.' : 'Eligibility withdrawn. Grants linked to that approval no longer provide access.')
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'The access change could not be recorded.')
    } finally {
      setBusy(false)
    }
  }

  const disabled = busy || loading || Boolean(error)
  return <section className={styles.panel} aria-label={administrator ? 'Assessor grants' : 'Assessor eligibility'}>
    <h2>{administrator ? 'Manage assessor grants' : 'Approve assessor eligibility'}</h2>
    <p>{administrator ? 'Grant course access only after the course lead approves teaching eligibility.' : 'Confirm teaching eligibility for this course. An administrator records the separate access grant.'}</p>
    {error && <p role="alert">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    <Button variant="quiet" disabled={busy} onClick={refresh}>Reload assessor access</Button>
    {loading ? <p role="status">Loading assessor access...</p> : !error && <>
      {candidates.length === 0 ? <p>No active teaching accounts on this page.</p> : <Field label="Teaching account">
        <Select value={selectedId} disabled={busy} onValueChange={(value) => { setSelectedId(value); setReason(''); setEndDate(''); setNotice('') }} options={candidates.map((person) => ({ value: String(person.subject_user_id), label: `${person.full_name} (staff ${person.subject_user_id})` }))} />
      </Field>}
      <div className={styles.actions}>
        <Button variant="quiet" disabled={busy || candidateOffset === 0} onClick={() => { setLoading(true); setCandidateOffset((value) => Math.max(0, value - 20)) }}>Previous staff</Button>
        <Button variant="quiet" disabled={busy || candidates.length < 20} onClick={() => { setLoading(true); setCandidateOffset((value) => value + 20) }}>Next staff</Button>
      </div>
      {selected && <p><Tag>{selected.currently_eligible ? 'Currently eligible' : 'No current eligibility approval'}</Tag>{selected.latest_approval && <> Latest decision: {selected.latest_approval.reason}</>}</p>}
      <Field label="Access change reason" required><Textarea value={reason} disabled={busy} maxLength={2000} onChange={(event) => setReason(event.target.value)} /></Field>
      <Field label="Optional end date (local time)"><Input type="datetime-local" value={endDate} disabled={busy} onChange={(event) => setEndDate(event.target.value)} /></Field>
      <div className={styles.actions}>
        {administrator ? <Button disabled={disabled || !reason.trim() || !selected?.currently_eligible} onClick={() => void record('GRANT')}>Grant assessor access</Button> : <>
          <Button disabled={disabled || !reason.trim() || !selected} onClick={() => void record('APPROVED')}>Approve teaching eligibility</Button>
          <Button disabled={disabled || !reason.trim() || selected?.latest_approval?.state !== 'APPROVED'} onClick={() => void record('WITHDRAWN')}>Withdraw teaching eligibility</Button>
        </>}
      </div>
      <h3>Eligibility history</h3>
      {eligibility.length === 0 ? <p>No eligibility decisions on this page.</p> : <ol>{eligibility.map((row) => <li key={row.id}>
        Staff {row.subject_user_id}, version {row.version}: {row.state}. {row.reason} Recorded by staff {row.actor_user_id} at {new Date(row.created_at).toLocaleString()}.
        {row.valid_until && <> Ends {new Date(row.valid_until).toLocaleString()}.</>}
      </li>)}</ol>}
      {administrator && <><h3>Grant history</h3>{grants.length === 0 ? <p>No grants on this page.</p> : <ol>{grants.map((grant) => <li key={grant.id} className={styles.entry}>
        <p>Staff {grant.subject_user_id}, {grant.role}, version {grant.version}: <Tag>{grant.currently_active ? 'Active' : 'Inactive'}</Tag></p>
        <p>{grant.reason} Recorded by staff {grant.assigned_by_user_id} at {new Date(grant.assigned_at).toLocaleString()}.</p>
        <p>Starts {new Date(grant.valid_from).toLocaleString()}{grant.valid_until && <>, ends {new Date(grant.valid_until).toLocaleString()}</>}.</p>
        {grant.revocation_reason && <p>Revoked: {grant.revocation_reason}</p>}
        {!grant.revoked_at && <Button variant="quiet" disabled={disabled || !reason.trim()} onClick={() => void record('REVOKE', grant.id)}>Revoke grant for staff {grant.subject_user_id}, version {grant.version}</Button>}
      </li>)}</ol>}</>}
      <div className={styles.actions}>
        <Button variant="quiet" disabled={busy || historyOffset === 0} onClick={() => { setLoading(true); setHistoryOffset((value) => Math.max(0, value - 20)) }}>Newer access history</Button>
        <Button variant="quiet" disabled={busy || (eligibility.length < 20 && grants.length < 20)} onClick={() => { setLoading(true); setHistoryOffset((value) => value + 20) }}>Older access history</Button>
      </div>
    </>}
  </section>
}
