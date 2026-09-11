import { useCallback, useEffect, useState } from 'react'
import { ApiError } from '../../app/api'
import type { ScopedRoleAssignment } from '../../app/types'
import { Button, Card, Checkbox, Field, Input, Textarea } from '../../components/ui'
import type { AssessmentDraft } from './api'
import { AssessorDefinitionFields } from './AssessorDefinitionFields'
import { DefinitionEditingError, definitionToDraft, validateDefinitionDraft } from './definitionEditing'
import type { AuthoringDefinition } from './definitionEditing'
import { definitionEditingApi } from './definitionEditingApi'
import styles from './assessment.module.css'

function errorMessage(error: unknown): string {
  if (error instanceof DefinitionEditingError) return error.message
  if (error instanceof ApiError) {
    if (error.status === 409) return 'This definition changed elsewhere. Reload history and compare before selecting a server version. Local edits are preserved.'
    if (error.status === 403 || error.status === 404) return 'This definition is unavailable or your course permission no longer allows this action.'
    if (error.status === 422) return 'The service rejected this definition. Check the criteria, policies and current task review before trying again.'
  }
  return 'The assessment service could not complete the request. Local edits are preserved.'
}

function permissionDenied(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 403 || error.status === 404)
}

export function AssessorDefinitionEditor({ assignments, initialDefinitionId = '', initialCourseId, autoLoad = false, onCheckAccess, onAccessRevoked }: {
  assignments: ScopedRoleAssignment[], initialDefinitionId?: string, initialCourseId?: string, autoLoad?: boolean,
  onCheckAccess: (courseId: string) => Promise<boolean>, onAccessRevoked: () => void,
}) {
  const courses = assignments.filter((assignment) => assignment.role === 'assessor')
  const canAutoLoad = Boolean(autoLoad && initialCourseId && initialDefinitionId
    && courses.some((assignment) => assignment.course_id === initialCourseId))
  const [courseId, setCourseId] = useState(initialCourseId ?? courses[0]?.course_id ?? '')
  const [definitionId, setDefinitionId] = useState(initialDefinitionId)
  const [definition, setDefinition] = useState<AuthoringDefinition | null>(null)
  const [draft, setDraft] = useState<AssessmentDraft | null>(null)
  const [history, setHistory] = useState<AuthoringDefinition[]>([])
  const [dirty, setDirty] = useState(false)
  const [editing, setEditing] = useState(false)
  const [busy, setBusy] = useState(canAutoLoad)
  const [stale, setStale] = useState(false)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')
  const [invalidFields, setInvalidFields] = useState<string[]>([])
  const [faults, setFaults] = useState<string[]>([])
  const [reason, setReason] = useState('')
  const [verified, setVerified] = useState(false)
  const [formRevision, setFormRevision] = useState(0)
  const [revoked, setRevoked] = useState(false)

  const clearPrivateState = useCallback(() => {
    setDefinition(null); setDraft(null); setHistory([]); setInvalidFields([]); setFaults([])
    setReason(''); setVerified(false); setEditing(false); setDirty(false); setStatus(''); setError('')
    setRevoked(true)
  }, [setDefinition, setDraft, setHistory, setInvalidFields, setFaults, setReason,
    setVerified, setEditing, setDirty, setStatus, setError, setRevoked])
  const handleFailure = (failure: unknown) => {
    if (permissionDenied(failure)) {
      clearPrivateState()
      onAccessRevoked()
    } else {
      setError(errorMessage(failure))
      if (failure instanceof ApiError && failure.status === 409) setStale(true)
    }
  }

  const adopt = useCallback((record: AuthoringDefinition) => {
    const editable = definitionToDraft(record)
    setDefinition(record); setDraft(editable); setDirty(false); setStale(false)
    setEditing(record.approval_state === 'DRAFT'); setVerified(false); setReason('')
    setInvalidFields([]); setFaults([]); setError(''); setFormRevision((revision) => revision + 1)
  }, [setDefinition, setDraft, setDirty, setStale, setEditing, setVerified, setReason,
    setInvalidFields, setFaults, setError, setFormRevision])
  useEffect(() => {
    if (revoked || !canAutoLoad || !initialCourseId || !initialDefinitionId) return
    let cancelled = false
    void definitionEditingApi.history(initialCourseId, initialDefinitionId).then((records) => {
      if (cancelled) return
      if (!records.length) throw new DefinitionEditingError('No definition versions are available.')
      const ordered = [...records].sort((left, right) => right.version - left.version)
      adopt(ordered[0]); setHistory(ordered); setStatus('Latest definition loaded.')
    }).catch((failure: unknown) => {
      if (cancelled) return
      if (permissionDenied(failure)) clearPrivateState()
      else setError(errorMessage(failure))
    })
      .finally(() => { if (!cancelled) setBusy(false) })
    return () => { cancelled = true }
  }, [adopt, canAutoLoad, clearPrivateState, initialCourseId, initialDefinitionId, revoked])
  const load = async () => {
    setBusy(true); setError(''); setStatus('')
    try {
      const records = await definitionEditingApi.history(courseId, definitionId.trim())
      if (!records.length) throw new DefinitionEditingError('No definition versions are available.')
      const ordered = [...records].sort((left, right) => right.version - left.version)
      setHistory(ordered)
      if (!definition) { adopt(ordered[0]); setStatus('Latest definition loaded.') }
      else setStatus('History reloaded. Local edits remain unchanged; select a version below to replace them.')
    } catch (failure) { handleFailure(failure) }
    finally { setBusy(false) }
  }
  const save = async () => {
    if (!definition || !draft || !editing || stale || busy) return
    const problems = [...invalidFields.map((label) => `Repair ${label}.`), ...validateDefinitionDraft(draft)]
    setFaults(problems)
    if (problems.length) return
    setBusy(true); setError(''); setStatus('')
    try {
      const saved = await definitionEditingApi.save(definition, draft)
      adopt(saved)
      setHistory((records) => [saved, ...records.filter((record) => record.id !== saved.id)])
      setStatus(`Draft version ${saved.version} saved. It has not been approved.`)
    } catch (failure) { handleFailure(failure) }
    finally { setBusy(false) }
  }
  const publish = async () => {
    if (!definition || !draft || definition.approval_state !== 'DRAFT' || dirty || busy || stale || !verified || !reason.trim()) return
    const problems = validateDefinitionDraft(draft)
    setFaults(problems)
    if (problems.length) return
    setBusy(true); setError(''); setStatus('')
    try {
      const approved = await definitionEditingApi.publish(definition, reason.trim())
      adopt(approved)
      setHistory((records) => [approved, ...records.filter((record) => record.id !== approved.id)])
      setStatus(`Version ${approved.version} approved and published.`)
    } catch (failure) { handleFailure(failure) }
    finally { setBusy(false) }
  }

  const checkAccess = async () => {
    if (busy || revoked) return
    setBusy(true); setError('')
    try {
      const active = await onCheckAccess(definition?.course_id ?? courseId)
      if (active) setStatus('Assessor access is still active for this course.')
      else {
        clearPrivateState()
        onAccessRevoked()
      }
    } catch (failure) {
      if (permissionDenied(failure)) handleFailure(failure)
      else setError('Assessor access could not be refreshed. Please try again.')
    }
    finally { setBusy(false) }
  }

  if (revoked) return <p role="alert">Assessor access is unavailable. Private definition content has been cleared.</p>

  return <div className={styles.form}>
    <Button variant="secondary" disabled={busy || !courseId} onClick={() => void checkAccess()}>Check assessor access</Button>
    <Card heading="Open an existing definition">
      <Field label="Definition course"><select value={courseId} disabled={busy || definition !== null} onChange={(event) => setCourseId(event.target.value)}>
        {courses.map((assignment) => <option key={assignment.id} value={assignment.course_id}>{assignment.course_id}</option>)}
      </select></Field>
      <Field label="Assessment definition ID"><Input value={definitionId} disabled={busy || definition !== null} onChange={(event) => setDefinitionId(event.target.value)} /></Field>
      <Button variant="secondary" disabled={busy || !definitionId.trim() || !courses.some((assignment) => assignment.course_id === courseId)} onClick={() => void load()}>
        {definition ? 'Reload definition history' : 'Load definition'}
      </Button>
    </Card>
    {error && <p role="alert" className={styles.alert}>{error}</p>}
    {status && <p role="status" className={styles.status}>{status}</p>}
    {faults.length > 0 && <ul role="alert">{faults.map((fault, index) => <li key={index}>{fault}</li>)}</ul>}
    {definition && draft && <>
      <Card heading="Version history">
        <p>Editing version {definition.version}. {definition.approval_state === 'DRAFT' ? 'Draft' : 'Frozen published version'}.</p>
        <p>Selecting a server version replaces the local form. Compare its contents first if you have unsaved changes.</p>
        {history.map((record) => <details key={record.id}><summary>Version {record.version} — {record.approval_state}</summary>
          <pre>{JSON.stringify(record, null, 2)}</pre>
          <Button variant="secondary" disabled={busy} onClick={() => {
            try { adopt(record); setStatus(`Loaded version ${record.version}.`) }
            catch (failure) { setError(errorMessage(failure)) }
          }}>Use version {record.version}{dirty ? ' and discard local edits' : ''}</Button>
        </details>)}
      </Card>
      {!editing && <Card heading="Published definition">
        <p>This version is frozen. Start a revision to edit a copy and save a new unapproved draft.</p>
        <Button variant="secondary" disabled={busy || stale} onClick={() => { setEditing(true); setDirty(true); setVerified(false) }}>Create draft from this version</Button>
      </Card>}
      <fieldset disabled={busy || !editing} className={styles.fieldset}>
        <legend>Definition content</legend>
        <AssessorDefinitionFields key={formRevision} draft={draft} reservedCriterionKeys={history.flatMap((record) => record.criteria.map((criterion) => criterion.stable_key))} onChange={(value) => {
          setDraft(value); setDirty(true); setVerified(false); setFaults([]); setStatus('')
        }} onValidity={(label, valid) => {
          setInvalidFields((fields) => valid ? fields.filter((field) => field !== label) : [...new Set([...fields, label])])
          if (!valid) { setDirty(true); setVerified(false) }
        }} />
        <Button variant="primary" disabled={busy || stale || invalidFields.length > 0} onClick={() => void save()}>Save new draft version</Button>
      </fieldset>
      <Card heading="Approve saved version">
        {dirty && <p>Save local changes before approval.</p>}
        <Field label="Version approval reason"><Textarea value={reason} disabled={busy || !editing} onChange={(event) => setReason(event.target.value)} /></Field>
        <Checkbox label="I reviewed every criterion, the pass rule, Bloom elicitation and access preservation for this saved version." checked={verified} disabled={busy || dirty || !editing} onChange={(event) => setVerified(event.target.checked)} />
        <Button variant="primary" disabled={busy || dirty || stale || !verified || !reason.trim() || definition.approval_state !== 'DRAFT'} onClick={() => void publish()}>Approve saved version</Button>
      </Card>
    </>}
  </div>
}
