import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { request } from '../../app/api'

export type ProgressIndicator = {
  id: string; kind: string; explanation: string; evidence_ids: string[]
  occurred_at: string; uncertainty: number; rule_version: string
}

type Props = {
  course: string; learner: number; outcome: string; version: number
  evidence: Array<{ evidence_id: string; kind: string }>; onSaved: () => void
}

const dimensions = ['USEFUL_EXPLANATION_FORM', 'SUCCESSFUL_STRATEGY', 'UNSUCCESSFUL_STRATEGY', 'SUPPORT_NEEDS', 'FEEDBACK_USE', 'TRANSFER', 'CONFIDENCE_CALIBRATION', 'REASONING_STRENGTH', 'REASONING_GAP']
const label = (value: string) => value.toLowerCase().replaceAll('_', ' ')

export function ProfileReview({ course, learner, outcome, version, evidence, onSaved }: Props) {
  const [dimension, setDimension] = useState(dimensions[0])
  const [status, setStatus] = useState('UNCERTAIN')
  const [uncertainty, setUncertainty] = useState('0.5')
  const [reason, setReason] = useState('')
  const [selected, setSelected] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const attempt = useRef<{ digest: string; key: string } | null>(null)
  const save = async () => {
    const body = { expected_version: version, dimension, status, uncertainty: Number(uncertainty), reason, evidence: Object.entries(selected).map(([evidence_id, relation]) => ({ evidence_id, relation })) }
    const digest = JSON.stringify(body)
    if (attempt.current?.digest !== digest) attempt.current = { digest, key: crypto.randomUUID() }
    setBusy(true); setError('')
    try {
      await request(`/progress/${encodeURIComponent(course)}/learners/${learner}/outcomes/${encodeURIComponent(outcome)}/reviews`, { method: 'POST', body: JSON.stringify({ ...body, idempotency_key: attempt.current.key }) })
      onSaved()
    } catch (error) { setError(error instanceof Error ? error.message : 'Review could not be saved') }
    finally { setBusy(false) }
  }
  return <details><summary>Record an educator interpretation</summary>
    <p>Describe the strategy, explanation form or support need shown by these observations. Include counterevidence. This records your outcome-specific interpretation and does not change assessment results.</p>
    <label>Learning area<select value={dimension} onChange={event => setDimension(event.target.value)}>{dimensions.map(value => <option key={value} value={value}>{label(value)}</option>)}</select></label>
    <label>Evidence interpretation<select value={status} onChange={event => setStatus(event.target.value)}>{['UNCERTAIN', 'SUPPORTED', 'CONTRADICTED', 'NEEDS_REVIEW'].map(value => <option key={value} value={value}>{label(value)}</option>)}</select></label>
    <label>Uncertainty (0 to 1)<input type="number" min="0" max="1" step="0.1" value={uncertainty} onChange={event => setUncertainty(event.target.value)} /></label>
    <label>Reason and observed strategy or explanation form<textarea minLength={10} maxLength={500} value={reason} onChange={event => setReason(event.target.value)} /></label>
    <fieldset><legend>Contributing observations</legend>{evidence.map(row => <div key={row.evidence_id}>
      <Link to={`/educator/evidence/${encodeURIComponent(row.evidence_id)}?course=${encodeURIComponent(course)}`}>Inspect {label(row.kind)} {row.evidence_id}</Link>
      <label>Relationship for {row.evidence_id}<select value={selected[row.evidence_id] ?? ''} onChange={event => setSelected(prior => { const next = { ...prior }; if (event.target.value) next[row.evidence_id] = event.target.value; else delete next[row.evidence_id]; return next })}><option value="">Not selected</option><option value="SUPPORTS">Supports interpretation</option><option value="CONTRADICTS">Contradicts interpretation</option></select></label>
    </div>)}</fieldset>
    {error && <p role="alert">{error}</p>}
    <button disabled={busy || reason.trim().length < 10 || !Object.keys(selected).length || uncertainty === '' || Number(uncertainty) < 0 || Number(uncertainty) > 1} onClick={() => void save()}>{busy ? 'Recording…' : 'Record interpretation'}</button>
  </details>
}
