import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, request } from '../../app/api'
import { Button, Card, CodeBlock } from '../../components/ui'
import { AssessorReviewUnresolved } from './AssessorReviewUnresolved'

type ModerationRow = {
  attempt_id: string; task_family: string; sequence: number; policy_id: string
  drift_check: boolean; state: string; formal_state?: string | null; next_stage: string | null; history: unknown[]; history_withheld?: boolean
}
type Queue = { policy_status: string; records: ModerationRow[] }
type Validation = { state: string; reason: string; ai_activation: string }
const stages: Record<string, string> = {
  ORIGINAL_REQUIRED: 'Original review required', SECOND_REQUIRED: 'Independent second review required',
  DISAGREEMENT: 'Disagreement: third assessor resolution required', DRIFT_REQUIRED: 'Drift review required',
  DRIFT_DISAGREEMENT: 'Drift disagreement: third assessor resolution required',
  READY: 'Moderation complete; formal confirmation still required',
}

type PanelProps = {
  courseId: string; onCheckAccess: (courseId: string) => Promise<boolean>
  onAccessRevoked: () => void; onRecorded: () => void
}
const emptyPolicy = { initial_count: '', later_percent: '', drift_interval: '', approval_reference: '', training_reference: '', expires_at: '' }

export function AssessmentModerationPanel(props: PanelProps) {
  // Changing course discards all prior review selection and policy form state.
  return <CourseModerationPanel key={props.courseId} {...props} />
}

function CourseModerationPanel({ courseId, onCheckAccess, onAccessRevoked, onRecorded }: PanelProps) {
  const [queue, setQueue] = useState<Queue | null>(null)
  const [validation, setValidation] = useState<Validation | null>(null)
  const [selected, setSelected] = useState<ModerationRow | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(true)
  const [policy, setPolicy] = useState(emptyPolicy)
  const generation = useRef(0)
  const mounted = useRef(false)
  const base = `/assessment/courses/${encodeURIComponent(courseId)}`
  const deny = useCallback(() => {
    if (!mounted.current) return
    generation.current += 1
    setQueue(null); setSelected(null); setValidation(null); setPolicy(emptyPolicy); setBusy(false)
    setError('Moderation could not be loaded. Check assessor access and reload.')
    onAccessRevoked()
  }, [onAccessRevoked])
  const load = useCallback(async () => {
    const current = ++generation.current
    const isCurrent = () => mounted.current && current === generation.current
    try {
      const permitted = await onCheckAccess(courseId)
      if (!isCurrent()) return
      if (!permitted) throw new ApiError('Assessor access required', 403)
      const [nextQueue, nextValidation] = await Promise.all([
        request<Queue>(`${base}/moderation`), request<Validation>(`${base}/evaluator-validation`),
      ])
      if (!isCurrent()) return
      setQueue(nextQueue); setValidation(nextValidation); setSelected(null); setError('')
    } catch (caught) {
      if (!isCurrent()) return
      if (caught instanceof ApiError && [403, 404].includes(caught.status)) {
        deny()
        return
      }
      setError('Moderation could not be loaded. Check assessor access and reload.')
    } finally { if (isCurrent()) setBusy(false) }
  }, [base, courseId, deny, onCheckAccess])
  useEffect(() => {
    mounted.current = true
    let active = true
    void Promise.resolve().then(() => { if (active) return load() })
    return () => { active = false; mounted.current = false; generation.current += 1 }
  }, [load])
  const savePolicy = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setError('')
    const current = ++generation.current
    const isCurrent = () => mounted.current && current === generation.current
    try {
      await request(`${base}/moderation-policy`, { method: 'POST', body: JSON.stringify({
        ...policy, initial_count: Number(policy.initial_count), later_percent: Number(policy.later_percent),
        drift_interval: Number(policy.drift_interval), expires_at: new Date(policy.expires_at).toISOString(),
      }) })
      if (isCurrent()) await load()
    } catch (caught) {
      if (!isCurrent()) return
      if (caught instanceof ApiError && [403, 404].includes(caught.status)) deny()
      else setError('Policy was not saved. Supply the approved values, references and a future expiry.')
    } finally { if (isCurrent()) setBusy(false) }
  }
  return <Card heading="Assessment moderation" eyebrow="Independent review">
    <p>Sampling uses a recorded approved course policy. Learners see no provisional result. Independent review and disagreement resolution precede formal confirmation.</p>
    <Button variant="secondary" disabled={busy} onClick={() => { setBusy(true); void load() }}>Reload moderation</Button>
    {error && <p role="alert">{error}</p>}
    {queue?.policy_status === 'POLICY_REQUIRED' && <p role="status">Approved sampling policy required. Ordinary human confirmation remains available where no policy has been activated; it is not recorded as moderated acceptance. Existing selected attempts still require their reviews.</p>}
    {validation && <p>Evaluator validation: {validation.state}. {validation.reason}. AI activation: {validation.ai_activation}.</p>}
    <details><summary>Record an approved sampling policy</summary>
      <p>Enter values from the approved policy and link its approval and assessor training records. No proposed pilot numbers are preselected.</p>
      <form onSubmit={event => void savePolicy(event)}>
        {(['initial_count', 'later_percent', 'drift_interval'] as const).map(name => <label key={name} style={{ display: 'block' }}>
          {{ initial_count: 'First responses per task family to double review', later_percent: 'Later responses sampled (%)', drift_interval: 'Responses between drift reviews' }[name]}
          <input required type="number" min={name === 'drift_interval' ? 1 : 0} max={name === 'later_percent' ? 100 : 100000} value={policy[name]} onChange={event => setPolicy(current => ({ ...current, [name]: event.target.value }))} />
        </label>)}
        {(['approval_reference', 'training_reference'] as const).map(name => <label key={name} style={{ display: 'block' }}>
          {name === 'approval_reference' ? 'Sampling approval reference' : 'Assessor training and shared anchors reference'}
          <input required maxLength={2000} value={policy[name]} onChange={event => setPolicy(current => ({ ...current, [name]: event.target.value }))} />
        </label>)}
        <label>Policy expiry<input required type="datetime-local" value={policy.expires_at} onChange={event => setPolicy(current => ({ ...current, expires_at: event.target.value }))} /></label>
        <Button type="submit" disabled={busy}>Record approved policy</Button>
      </form>
    </details>
    <ul>{queue?.records.map(row => <li key={row.attempt_id}>
      <p>{row.task_family}, response {row.sequence}: {row.state === 'READY' && ['CONFIRMED', 'OVERRIDDEN'].includes(row.formal_state ?? '') ? 'Moderation complete; formal result confirmed' : stages[row.state] ?? row.state}</p>
      {row.next_stage && <Button variant="secondary" disabled={busy} onClick={() => setSelected(row)}>{row.next_stage === 'CORRECTION' ? 'Start correction review for' : 'Review'} {row.attempt_id}</Button>}
      {!row.next_stage && row.state !== 'READY' && <p>Another authorised assessor is required.</p>}
      {row.history_withheld ? <p>Prior judgements are withheld until the independent second review is recorded.</p> : <details><summary>Preserved moderation history</summary><CodeBlock code={JSON.stringify(row.history, null, 2)} label="Original, independent and resolved decisions" /></details>}
    </li>)}</ul>
    {selected?.next_stage && <AssessorReviewUnresolved key={`${selected.attempt_id}-${selected.next_stage}`} courseId={courseId} moderation={{ attemptId: selected.attempt_id, stage: selected.next_stage }} onCheckAccess={onCheckAccess} onAccessRevoked={deny} onFinalised={() => { if (mounted.current) { void load(); onRecorded() } }} />}
  </Card>
}
