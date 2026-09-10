import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import type { ApiSchemas } from '../../api/generated'
import { Button, Card, Field, Textarea } from '../../components/ui'
import { checksApi, stageName, stateName } from './api'
import type { Candidate, Check, Stage } from './api'
import styles from './Misconceptions.module.css'

export function MisconceptionChecks({ educator = false }: { educator?: boolean }) {
  const [checks, setChecks] = useState<Check[]>([])
  const [candidates, setCandidates] = useState<Candidate[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(0)
  const [candidatePage, setCandidatePage] = useState(0)
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    void Promise.all([checksApi.list(page, controller.signal), educator ? checksApi.candidates(candidatePage, controller.signal) : Promise.resolve([])])
      .then(([saved, available]) => { setChecks(saved); setCandidates(available); setError('') })
      .catch((caught: unknown) => { if (!controller.signal.aborted) setError(caught instanceof Error ? caught.message : 'Learning checks could not be loaded.') })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [educator, page, candidatePage, retry])
  const prefix = educator ? '/educator' : '/student'
  return <main className={styles.page}>
    <h1>{educator ? 'Misconception checks' : 'My learning checks'}</h1>
    <p>These checks test a possible explanation for a learning difficulty. They do not set assessment results.</p>
    {error && <p role="alert">{error}</p>}
    <Button variant="secondary" onClick={() => { setLoading(true); setRetry(value => value + 1) }}>Refresh checks</Button>
    {loading && <p role="status">Loading learning checks...</p>}
    {!loading && <Card heading="Saved checks">
      {!checks.length && <p>No learning checks on this page.</p>}
      <ul>{checks.map(check => <li key={check.id}>
        <Link to={`${prefix}/misconceptions/${check.id}`}>{check.hypothesis}</Link>
        <p>{check.closure ? 'Ended' : stateName[check.state]}{check.next_stage ? `, next: ${stageName[check.next_stage]}` : ''}</p>
      </li>)}</ul>
      <Button variant="secondary" disabled={page === 0} onClick={() => setPage(value => Math.max(0, value - 20))}>Previous checks</Button>
      <Button variant="secondary" disabled={checks.length < 20} onClick={() => setPage(value => value + 20)}>More checks</Button>
    </Card>}
    {educator && !loading && <>
      <OpenCheck key={candidatePage} candidates={candidates} />
      <div><Button variant="secondary" disabled={candidatePage === 0} onClick={() => setCandidatePage(value => Math.max(0, value - 20))}>Previous teaching records</Button>
        <Button variant="secondary" disabled={candidates.length < 20} onClick={() => setCandidatePage(value => value + 20)}>More teaching records</Button></div>
    </>}
  </main>
}

const fields = [
  ['hypothesis', 'Possible misconception'], ['probe', 'Short check question'],
  ['explanation', 'Alternate explanation'], ['fresh_question', 'Fresh question'],
  ['selection_reason', 'Why this check will help'], ['content_approval_reason', 'Source and teaching-content approval reason'],
] as const

function OpenCheck({ candidates }: { candidates: Candidate[] }) {
  const navigate = useNavigate()
  const [selected, setSelected] = useState('')
  const [draft, setDraft] = useState<Record<typeof fields[number][0], string>>({ hypothesis: '', probe: '', explanation: '', fresh_question: '', selection_reason: '', content_approval_reason: '' })
  const [evidence, setEvidence] = useState<string[]>([])
  const [stages, setStages] = useState<Stage[]>([])
  const [confidence, setConfidence] = useState('0.5')
  const [support, setSupport] = useState('2')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const key = useRef(crypto.randomUUID())
  const candidate = candidates.find(item => item.feedback_id === selected)
  const create = async () => {
    if (!candidate) return
    setBusy(true); setError('')
    try {
      const payload: ApiSchemas['MisconceptionOpen'] = { ...draft, explanation_support_level: Number(support) as ApiSchemas['MisconceptionOpen']['explanation_support_level'], confidence: Number(confidence), evidence_ids: evidence, persistence_stages: stages, feedback_id: candidate.feedback_id, request_key: key.current }
      const saved = await checksApi.open(payload)
      navigate(`/educator/misconceptions/${saved.id}`)
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'The check could not be saved. Your draft remains here.') }
    finally { setBusy(false) }
  }
  return <Card heading="Open a reviewed teaching check">
    <p>Select the learner's saved work, then approve the teaching content and evidence rule for this cycle.</p>
    <form className={styles.form} onSubmit={event => { event.preventDefault(); void create() }}>
      <Field label="Saved learner work"><select required value={selected} onChange={event => { setSelected(event.target.value); setEvidence([]); key.current = crypto.randomUUID() }}>
        <option value="">Choose a saved response</option>
        {candidates.map((item, index) => <option key={item.feedback_id} value={item.feedback_id}>{item.student_name}, {item.course_title}, {item.task_title} ({index + 1})</option>)}
      </select></Field>
      {candidate && <><p>{candidate.response}</p><fieldset><legend>Evidence behind the hypothesis</legend>
        {candidate.evidence.map((item, index) => <label key={item.id}><input type="checkbox" checked={evidence.includes(item.id)} onChange={event => setEvidence(current => event.target.checked ? [...current, item.id] : current.filter(id => id !== item.id))} />{item.kind.toLowerCase()} observation {index + 1}<pre className={styles.evidence}>{item.content}</pre></label>)}
      </fieldset></>}
      {fields.map(([name, label]) => <Field label={label} key={name}><Textarea required maxLength={2000} value={draft[name]} onChange={event => setDraft(current => ({ ...current, [name]: event.target.value }))} /></Field>)}
      <p>The fresh question must use a new example. Keep its answer out of the other prompts and reasons.</p>
      <Field label="Instructional help in the alternate explanation"><select value={support} onChange={event => setSupport(event.target.value)}><option value="1">Goal reminder</option><option value="2">Concept cue</option><option value="3">Narrowing hint</option><option value="4">Partial worked step</option><option value="5">Direct answer</option></select></Field>
      <Field label="Confidence in the initial hypothesis (0 to less than 1)"><input type="number" required min="0" max="0.99" step="0.01" value={confidence} onChange={event => setConfidence(event.target.value)} /></Field>
      <fieldset><legend>Stages that must support a persisted hypothesis</legend><p>Approve at least two stages. One response cannot establish persistence.</p>
        {(Object.keys(stageName) as Stage[]).map(stage => <label key={stage}><input type="checkbox" checked={stages.includes(stage)} onChange={event => setStages(current => event.target.checked ? [...current, stage] : current.filter(item => item !== stage))} />{stageName[stage]}</label>)}
      </fieldset>
      {error && <p role="alert">{error}</p>}
      <Button type="submit" disabled={busy || !candidate || evidence.length === 0 || stages.length < 2}>{busy ? 'Saving check...' : 'Approve and open check'}</Button>
    </form>
  </Card>
}
