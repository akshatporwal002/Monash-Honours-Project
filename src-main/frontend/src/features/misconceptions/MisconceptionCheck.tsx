import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError } from '../../app/api'
import { Button, Card, Field, Textarea } from '../../components/ui'
import { checksApi, stageName, stateName } from './api'
import type { Check } from './api'
import styles from './Misconceptions.module.css'

export function MisconceptionCheck({ educator = false }: { educator?: boolean }) {
  const { identity = '' } = useParams()
  const [check, setCheck] = useState<Check | null>(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [retry, setRetry] = useState(0)
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => {
    const controller = new AbortController()
    void checksApi.read(identity, controller.signal).then(data => { setCheck(data); setError('') }).catch((caught: unknown) => {
      if (!controller.signal.aborted) { setCheck(null); setError(caught instanceof Error ? caught.message : 'The learning check could not be loaded.') }
    })
    return () => controller.abort()
  }, [identity, retry])
  const changed = (data: Check) => { setCheck(data); setError(''); setNotice('Your record was saved.'); heading.current?.focus() }
  const failed = (caught: unknown) => {
    if (caught instanceof ApiError && [401, 403, 404].includes(caught.status)) setCheck(null)
    setError(caught instanceof Error ? caught.message : 'The record could not be saved. Your draft remains here.')
  }
  return <main className={styles.page}>
    <Link to={educator ? '/educator/misconceptions' : '/student/misconceptions'}>Back to learning checks</Link>
    <h1 ref={heading} tabIndex={-1}>Learning check and review</h1>
    {error && <p role="alert">{error}</p>}
    <p role="status">{notice}</p>
    <Button variant="secondary" onClick={() => setRetry(value => value + 1)}>Refresh this check</Button>
    {!check && !error && <p>Loading the saved check...</p>}
    {check && <>
      <Card heading="Possible misconception">
        <p>{check.hypothesis}</p><p>Current state: {stateName[check.state]}. Confidence in this state: {check.confidence}.</p>
        <p>This is a scoped learning hypothesis. It does not set a formal assessment result.</p>
        <h3>Why this check was selected</h3><p>{check.selection_reason}</p>
        {check.closure && <p>Check ended: {check.closure.reason}. An educator can approve a new check with a fresh question.</p>}
        {!check.teaching_available && <p>Teaching details are paused during your assessed fresh application. You can leave this check below.</p>}
      </Card>
      {check.probe && <Card heading="Check question"><p>{check.probe}</p></Card>}
      {check.explanation && <Card heading="Alternate explanation"><p>{check.explanation}</p></Card>}
      {check.fresh_question && <Card heading="Fresh check"><p>{check.fresh_question}</p><p>Use your own reasoning. The check workspace has no instructional hints. Access support remains available.</p></Card>}
      {!educator && check.next_stage && check.teaching_available && <AnswerForm key={`${identity}:${check.next_stage}`} check={check} changed={changed} failed={failed} />}
      <CheckHistory check={check} />
      {educator && !check.next_stage && !check.closure && <ReviewForm key={`${identity}:${check.version}`} check={check} changed={changed} failed={failed} />}
      {!check.closure && check.next_stage && <ExitForm key={identity} educator={educator} check={check} changed={changed} failed={failed} />}
    </>}
  </main>
}

type Actions = { check: Check; changed: (check: Check) => void; failed: (error: unknown) => void }

function AnswerForm({ check, changed, failed }: Actions) {
  const [answer, setAnswer] = useState('')
  const [reasoning, setReasoning] = useState('')
  const [confidence, setConfidence] = useState('0.5')
  const [help, setHelp] = useState('')
  const [busy, setBusy] = useState(false)
  const key = useRef(crypto.randomUUID())
  const stage = check.next_stage!
  const submit = async () => {
    setBusy(true)
    try { changed(await checksApi.answer(check.id, { request_key: key.current, expected_version: check.version, stage, answer, reasoning, confidence: Number(confidence), help_used: help === 'used', start_fresh_check: stage === 'REVISION' })) }
    catch (error) { failed(error) }
    finally { setBusy(false) }
  }
  return <Card heading={`Your ${stageName[stage].toLowerCase()}`}><form className={styles.form} onSubmit={event => { event.preventDefault(); void submit() }}>
    <Field label="Your answer"><Textarea required maxLength={2000} value={answer} onChange={event => setAnswer(event.target.value)} /></Field>
    <Field label="Explain your reasoning"><Textarea required maxLength={2000} value={reasoning} onChange={event => setReasoning(event.target.value)} /></Field>
    <Field label="Confidence in your answer (0 to 1)"><input required type="number" min="0" max="1" step="0.01" value={confidence} onChange={event => setConfidence(event.target.value)} /></Field>
    <Field label="Instructional help used"><select required value={help} onChange={event => setHelp(event.target.value)}><option value="">Choose the conditions you used</option><option value="none">No extra instructional help</option><option value="used">I used instructional help</option></select></Field>
    <p>Screen readers, text size and other access support do not count as instructional help.</p>
    {stage === 'REVISION' && <p>Saving this revision starts the fresh check and hides the earlier explanation. You can leave without a penalty.</p>}
    <Button type="submit" disabled={busy}>{busy ? 'Saving response...' : stage === 'REVISION' ? 'Save revision and start fresh check' : 'Save response'}</Button>
  </form></Card>
}

function CheckHistory({ check }: { check: Check }) {
  const observations = evidenceOptions(check)
  const labels = (references: string[]) => references.map(id => observations.find(item => item.id === id)?.label ?? 'Saved observation').join(', ') || 'None'
  return <Card heading="Preserved history">
    {check.initial_evidence.map((item, index) => <section key={item.id}><h3>Initial observation {index + 1}</h3><pre className={styles.evidence}>{item.content}</pre></section>)}
    {!check.responses.length && <p>Earlier teaching is hidden during the fresh check, or no response has been saved yet.</p>}
    <ol className={styles.history}>{check.responses.map(item => <li key={item.id}><h3>{stageName[item.stage]}</h3><p>{item.answer}</p><p>{item.reasoning}</p><p>{item.help_used ? 'Extra instructional help reported.' : 'No extra instructional help reported.'} Confidence: {item.confidence}.</p><time>{new Date(item.created_at).toLocaleString()}</time></li>)}</ol>
    {check.reviews.map(review => <section key={review.id}><h3>Review {review.version - 3}: {stateName[review.state]}</h3><p>{review.reason}</p><p>Next action: {review.next_action}</p><p>Supporting observations: {labels(review.supports)}. Contradicting observations: {labels(review.contradicts)}.</p><p>Confidence: {review.confidence}. Reviewed {new Date(review.created_at).toLocaleString()}.</p>{review.escalation_id && <p>This unresolved check was sent to the human review queue.</p>}</section>)}
  </Card>
}

function evidenceOptions(check: Check) {
  return [
    ...check.initial_evidence.map((item, index) => ({ id: item.id, label: `Initial observation ${index + 1}` })),
    ...check.responses.map(item => ({ id: item.evidence_id, label: stageName[item.stage] })),
  ]
}

function ReviewForm({ check, changed, failed }: Actions) {
  const [state, setState] = useState<Check['state']>('UNCERTAIN')
  const [relations, setRelations] = useState<Record<string, string>>({})
  const [confidence, setConfidence] = useState('0.5')
  const [reason, setReason] = useState('')
  const [next, setNext] = useState('')
  const [busy, setBusy] = useState(false)
  const key = useRef(crypto.randomUUID())
  const submit = async () => {
    setBusy(true)
    try { changed(await checksApi.review(check.id, { request_key: key.current, expected_version: check.version, state, confidence: Number(confidence), supports: Object.keys(relations).filter(id => relations[id] === 'supports'), contradicts: Object.keys(relations).filter(id => relations[id] === 'contradicts'), reason, next_action: next })) }
    catch (error) { failed(error) }
    finally { setBusy(false) }
  }
  return <Card heading="Educator review"><form className={styles.form} onSubmit={event => { event.preventDefault(); void submit() }}>
    <p>Approved persistence rule: {check.persistence_stages.map(stage => stageName[stage]).join(', ')} must support the hypothesis.</p>
    <p>Correction requires contradicting evidence from an unaided fresh check. Record uncertainty when evidence is insufficient or conflicting.</p>
    {evidenceOptions(check).map(item => <Field key={item.id} label={`${item.label} evidence`}><select value={relations[item.id] ?? ''} onChange={event => setRelations(current => ({ ...current, [item.id]: event.target.value }))}><option value="">Leave out of this review</option><option value="supports">Supports the hypothesis</option><option value="contradicts">Contradicts the hypothesis</option></select></Field>)}
    <Field label="Reviewed state"><select value={state} onChange={event => setState(event.target.value as Check['state'])}>{(Object.keys(stateName) as Check['state'][]).map(value => <option key={value} value={value}>{stateName[value]}</option>)}</select></Field>
    <Field label="Confidence in this review (0 to less than 1)"><input required type="number" min="0" max="0.99" step="0.01" value={confidence} onChange={event => setConfidence(event.target.value)} /></Field>
    <Field label="Evidence and review reason"><Textarea required maxLength={2000} value={reason} onChange={event => setReason(event.target.value)} /></Field>
    <Field label="Next teaching action and reason"><Textarea required maxLength={2000} value={next} onChange={event => setNext(event.target.value)} /></Field>
    <Button type="submit" disabled={busy || !Object.values(relations).some(Boolean)}>{busy ? 'Saving review...' : 'Record educator review'}</Button>
  </form></Card>
}

function ExitForm({ check, educator, changed, failed }: Actions & { educator: boolean }) {
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const key = useRef(crypto.randomUUID())
  const leave = async () => {
    setBusy(true)
    try { changed(await checksApi.exit(check.id, { request_key: key.current, expected_version: check.version, reason, disposition: educator ? 'INVALIDATED' : 'DEFERRED' })) }
    catch (error) { failed(error) }
    finally { setBusy(false) }
  }
  return <Card heading={educator ? 'Retire this check' : 'Leave this check'}><form className={styles.form} onSubmit={event => { event.preventDefault(); void leave() }}>
    <p>Your saved work stays in history. Task help becomes available again when this check ends. Restarting needs a new approved fresh question.</p>
    <Field label="Reason for ending this check"><Textarea required maxLength={2000} value={reason} onChange={event => setReason(event.target.value)} /></Field>
    <Button type="submit" variant="secondary" disabled={busy}>{busy ? 'Saving...' : educator ? 'Retire check' : 'Save reason and leave check'}</Button>
  </form></Card>
}
