import { useEffect, useRef, useState } from 'react'
import { ApiError, request } from '../../app/api'
import { Button, Card } from '../../components/ui'

type Status = { state: string; validation_id: string | null; fingerprint: string; reason: string; ai_activation: string }
type Row = { id: string; revision: number; state: string; reason: string; actor_id: number | null; created_at: string; expires_at: string | null; fingerprint: string; evidence: Record<string, unknown> }
type Governance = { status: Status; history: Row[]; forms: { id: string; title: string; version: number; approved: boolean }[] }
type ValidationFile = { expected_fingerprint: string; expires_at: string; evidence: Record<string, unknown> }
const releaseLabels = {
  authority_name: 'Release authority name', authority_role: 'Release authority role',
  approval_reference: 'Signed release reference', provider: 'Approved provider', model: 'Approved model',
  prompt_version: 'Approved prompt version', retrieval_version: 'Approved retrieval version',
}

export function EvaluatorGovernancePanel({ courseId }: { courseId: string }) {
  return <CourseGovernance key={courseId} courseId={courseId} />
}

function EvidenceValues({ value }: { value: unknown }) {
  if (Array.isArray(value)) return <ol>{value.map((item, index) => <li key={index}><EvidenceValues value={item} /></li>)}</ol>
  if (value !== null && typeof value === 'object') return <dl>{Object.entries(value).filter(([name]) => name !== 'request_digest').map(([name, item]) => <div key={name}><dt>{name.replaceAll('_', ' ')}</dt><dd><EvidenceValues value={item} /></dd></div>)}</dl>
  return <span>{String(value ?? 'Not recorded')}</span>
}

function CourseGovernance({ courseId }: { courseId: string }) {
  const [reload, setReload] = useState(0)
  const [data, setData] = useState<Governance | null>(null)
  const [file, setFile] = useState<ValidationFile | null>(null)
  const [fileName, setFileName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [release, setRelease] = useState<Record<string, string>>({})
  const [scope, setScope] = useState<string[]>([])
  const [reason, setReason] = useState('')
  const [authority, setAuthority] = useState('')
  const active = useRef(true)
  const generation = useRef(0)
  const keys = useRef(new Map<string, string>())
  const base = `/assessment/courses/${encodeURIComponent(courseId)}`
  useEffect(() => {
    active.current = true
    let alive = true
    const controller = new AbortController()
    void request<Governance>(`${base}/evaluator-governance`, { signal: controller.signal })
      .then(value => { if (alive) { setData(value); setError('') } })
      .catch(() => { if (alive) { setData(null); setError('Validation history could not be loaded. Administrator access is required.') } })
    return () => { alive = false; active.current = false; generation.current += 1; controller.abort() }
  }, [base, reload])
  async function submit(kind: string, payload: Record<string, unknown>) {
    const current = ++generation.current
    const exact = JSON.stringify({ kind, payload })
    if (!keys.current.has(exact)) keys.current.set(exact, crypto.randomUUID())
    setBusy(true); setError(''); setMessage('')
    try {
      await request(`${base}/evaluator-${kind}`, { method: 'POST', body: JSON.stringify({ ...payload, idempotency_key: keys.current.get(exact) }) })
      const next = await request<Governance>(`${base}/evaluator-governance`)
      if (active.current && current === generation.current) { setData(next); setMessage('Decision recorded. Review the current status below.'); setFile(null); setFileName('') }
    } catch (caught) {
      if (active.current && current === generation.current) {
        setError(caught instanceof Error ? caught.message : 'The decision could not be recorded.')
        if (caught instanceof ApiError && [403, 404].includes(caught.status)) { setData(null); setFile(null); setRelease({}); setScope([]) }
      }
    } finally { if (active.current && current === generation.current) setBusy(false) }
  }
  async function loadFile(selected: File | undefined) {
    const current = ++generation.current
    setFile(null); setFileName(''); setError('')
    if (!selected) return
    try {
      const parsed = JSON.parse(await selected.text()) as ValidationFile
      if (!parsed || typeof parsed.expected_fingerprint !== 'string' || !parsed.expires_at || !parsed.evidence || Array.isArray(parsed.evidence)) throw new Error('Choose a validation packet produced by the validation preparation tool.')
      if (active.current && current === generation.current) { setFile(parsed); setFileName(selected.name) }
    } catch { if (active.current && current === generation.current) setError('This file is not a readable validation packet. No decision was recorded.') }
  }
  return <Card heading="Evaluator validation and release">
    <p>Recording validation and releasing assessor suggestions are separate decisions. These controls do not call an AI provider or confirm learner results.</p>
    <Button variant="secondary" disabled={busy} onClick={() => { setData(null); setFile(null); setReload(value => value + 1) }}>Reload validation history</Button>
    {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    {data && <>
      <p role="status">Validation: {data.status.state}. Suggestions: {data.status.ai_activation}. {data.status.reason}</p>
      <label>Current dependency fingerprint<input readOnly value={data.status.fingerprint} /></label>
      <form onSubmit={event => { event.preventDefault(); if (file) void submit('validation', file) }}>
        <h3>Record completed validation</h3>
        <p>Import the prepared packet containing actual expert records, approved limits and measured errors. Its fingerprint must match the current system.</p>
        <label>Validation packet<input type="file" accept="application/json,.json" disabled={busy} onChange={event => void loadFile(event.target.files?.[0])} /></label>
        {file && <p>{fileName}: expires {file.expires_at}. {file.expected_fingerprint === data.status.fingerprint ? 'Fingerprint matches.' : 'Fingerprint differs; repeat validation before recording.'}</p>}
        <Button type="submit" disabled={busy || !file || file.expected_fingerprint !== data.status.fingerprint}>Record validation evidence</Button>
      </form>
      <details><summary>Record a signed release</summary>
        <form onSubmit={event => { event.preventDefault(); void submit('release', { ...release,
          validation_id: data.status.validation_id, expected_fingerprint: data.status.fingerprint,
          approved_at: new Date(release.approved_at).toISOString(), expires_at: new Date(release.expires_at).toISOString(), task_form_version_ids: scope,
        }) }}>
          <p>The current validation must contain independent expert, agreement, error, fairness, coverage, adjudication and revalidation evidence. Select only the forms covered by the signed approval.</p>
          {Object.entries(releaseLabels).map(([key, label]) => <label key={key} style={{ display: 'block' }}>{label}<input required maxLength={2000} value={release[key] ?? ''} onChange={event => setRelease(current => ({ ...current, [key]: event.target.value }))} /></label>)}
          <label>Release approved at<input type="datetime-local" required value={release.approved_at ?? ''} onChange={event => setRelease(current => ({ ...current, approved_at: event.target.value }))} /></label>
          <label>Release expires at<input type="datetime-local" required value={release.expires_at ?? ''} onChange={event => setRelease(current => ({ ...current, expires_at: event.target.value }))} /></label>
          <fieldset><legend>Approved task forms</legend>{data.forms.filter(form => form.approved).map(form => <label key={form.id} style={{ display: 'block' }}><input type="checkbox" checked={scope.includes(form.id)} onChange={event => setScope(current => event.target.checked ? [...current, form.id] : current.filter(id => id !== form.id))} />{form.title}, version {form.version}</label>)}</fieldset>
          <Button type="submit" disabled={busy || !scope.length || data.status.state !== 'VALIDATED' || data.status.ai_activation === 'RELEASED'}>Record signed release</Button>
        </form>
      </details>
      <details><summary>Revoke validation or release</summary><form onSubmit={event => { event.preventDefault(); void submit('revoke', { expected_validation_id: data.status.validation_id, reason, authority_reference: authority }) }}>
        <label>Revocation reason<textarea required value={reason} onChange={event => setReason(event.target.value)} /></label>
        <label>Revocation authority reference<input required value={authority} onChange={event => setAuthority(event.target.value)} /></label>
        <Button type="submit" disabled={busy || !data.status.validation_id}>Record revocation</Button>
      </form></details>
      <h3>Preserved decisions</h3>
      <ol>{data.history.map(row => <li key={row.id}><strong>Revision {row.revision}: {row.state}</strong> — {row.reason}<p>Recorded {row.created_at}; administrator {row.actor_id ?? 'system'}; expires {row.expires_at ?? 'not applicable'}.</p><details><summary>Evidence references</summary><EvidenceValues value={row.evidence} /></details></li>)}</ol>
    </>}
  </Card>
}
