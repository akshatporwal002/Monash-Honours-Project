import { Link } from 'react-router-dom'
import { useEffect, useId, useRef, useState } from 'react'
import { activityContinuation, type Activity, type ActivityAction } from '../app/activityContinuation'
import styles from './ActivityContinuation.module.css'

function Choice({ initial }: { initial: Activity }) {
  const [value, setValue] = useState(initial)
  const [selected, setSelected] = useState('')
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const pending = useRef<ActivityAction | null>(null)
  const label = useId()
  const enabled = value.options.length > 0
  async function refresh() {
    setBusy(true)
    try { setValue(await activityContinuation.read(value.workflow_id)); pending.current = null; setError('') }
    catch { setError('The suggestion could not be refreshed. Your work remains available.') }
    finally { setBusy(false) }
  }
  async function choose(action: ActivityAction['action']) {
    setBusy(true); setError('')
    const command = { action, expected_version: value.version, task_id: action === 'replace' || action === 'educator_override' ? selected : null, reason }
    if (!pending.current || JSON.stringify({ ...pending.current, request_key: undefined }) !== JSON.stringify(command)) {
      pending.current = { ...command, request_key: crypto.randomUUID() }
    }
    try { setValue(await activityContinuation.act(value.workflow_id, pending.current)); pending.current = null }
    catch { setError('Your choice was not confirmed. Retry it, or refresh the saved version. Your draft is retained.') }
    finally { setBusy(false) }
  }
  return <section className={styles.card} aria-labelledby={label}>
    <h3 id={label}>Next approved activity</h3>
    <p role="status">{value.reason}</p>
    {value.can_override && <p>Learner: {value.learner_label}</p>}
    <p>State: {value.state.replaceAll('_', ' ')}</p>
    {value.snapshot_id && <p>Learning success is uncertain. This record is not an assessment result.</p>}
    {value.next_task_id && <p>{value.options.find(option => option.task_id === value.next_task_id)?.title}</p>}
    <div className={styles.controls}>
      {!value.can_override && <>
        <button disabled={busy || !value.next_task_id || !enabled} onClick={() => void choose('accept')}>Accept suggestion</button>
        <button disabled={busy || !enabled} onClick={() => void choose('defer')}>Defer suggestion</button>
      </>}
      <label>Approved alternatives
        <select value={selected} disabled={busy || !enabled} onChange={event => setSelected(event.target.value)}>
          <option value="">Choose an activity</option>
          {value.options.map(option => <option key={option.task_id} value={option.task_id}>{option.title}</option>)}
        </select>
      </label>
      {value.can_override && <label>Reason for educator override
        <textarea value={reason} maxLength={1000} onChange={event => setReason(event.target.value)} disabled={busy} />
      </label>}
      <button disabled={busy || !selected || !enabled || (value.can_override && !reason.trim())} onClick={() => void choose(value.can_override ? 'educator_override' : 'replace')}>
        {value.can_override ? 'Save educator override' : 'Replace suggestion'}
      </button>
      <button disabled={busy} onClick={() => void refresh()}>Refresh saved suggestion</button>
    </div>
    {error && <p role="alert">{error}</p>}
    {value.next_task_id && ['accept', 'replace', 'educator_override'].includes(value.state) && !value.can_override && <Link to={`/student/tasks/${encodeURIComponent(value.next_task_id)}`}>Open chosen activity</Link>}
    <details><summary>Why this suggestion and choice history</summary>
      <p>Rule: {value.rule_version}. Preference version: {value.preference_version ?? 'unavailable'}.</p>
      <p>Model snapshot: {value.snapshot_id ?? 'No model update'}. Uncertainty: {value.uncertainty ?? 'unavailable'}.</p>
      <ul>{value.evidence_ids.map(id => <li key={id}>Evidence: {id}</li>)}</ul>
      <p>{value.evidence_ids.length} linked learning observations. Pathway: {value.pathway_id ?? 'unavailable'}.</p>
      {value.history.length === 0 ? <p>No choice has been saved.</p> : <ol>{value.history.map(item => <li key={item.version}>
        {item.educator ? 'Educator' : 'Learner'}: {item.action.replaceAll('_', ' ')}. {item.reason}
        {item.task_id && <> Activity: {item.task_id}.</>}
      </li>)}</ol>}
    </details>
  </section>
}

export function ActivityContinuation({ submissionId }: { submissionId: string }) {
  const [value, setValue] = useState<Activity | null>(null)
  const [error, setError] = useState(false)
  const [reload, setReload] = useState(0)
  useEffect(() => {
    let active = true
    let timer: ReturnType<typeof setTimeout>
    async function read() {
      try {
        const next = await activityContinuation.submission(submissionId)
        if (!active) return
        if (!next || typeof next.workflow_id !== 'string' || !Array.isArray(next.options) || !Array.isArray(next.history) || !Array.isArray(next.evidence_ids)) throw new Error('Invalid activity response')
        setValue(next); setError(false)
        if (next.state === 'processing') timer = setTimeout(() => void read(), 3000)
      } catch { if (active) setError(true) }
    }
    void read()
    return () => { active = false; clearTimeout(timer) }
  }, [submissionId, reload])
  if (error) return <section className={styles.card}><p>The next activity is unavailable. Your saved work and feedback remain available.</p><button onClick={() => setReload(value => value + 1)}>Retry activity suggestion</button></section>
  return value ? <Choice key={`${value.workflow_id}-${value.state}`} initial={value} /> : <p>Checking the next approved activity...</p>
}

export function CourseActivityContinuations({ courseId }: { courseId: string }) {
  const [values, setValues] = useState<Activity[]>([])
  const [error, setError] = useState('')
  const [offset, setOffset] = useState(0)
  useEffect(() => {
    let active = true
    void activityContinuation.course(courseId, offset).then(rows => { if (active) { setValues(rows); setError('') } }).catch(() => { if (active) setError('Activity suggestions could not be loaded.') })
    return () => { active = false }
  }, [courseId, offset])
  return <section aria-label="Learner activity suggestions">
    <h2>Learner activity suggestions</h2>
    {error && <p role="alert">{error}</p>}
    {!values.length && <p>No saved activity suggestions on this page.</p>}
    {values.map(value => <Choice key={value.workflow_id} initial={value} />)}
    <button disabled={offset === 0} onClick={() => setOffset(value => Math.max(0, value - 20))}>Previous suggestions</button>
    <button disabled={values.length < 20} onClick={() => setOffset(value => value + 20)}>More suggestions</button>
  </section>
}
