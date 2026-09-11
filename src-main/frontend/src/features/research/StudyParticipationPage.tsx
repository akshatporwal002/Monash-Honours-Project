import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Button, Card, Field } from '../../components/ui'
import type { AuthUser } from '../../app/types'
import { studyApi, key, type Assignment, type Answer, type Participation, type Form, type Stage } from './api'

function InstrumentResponse({ study, course, userId, assignment, stage, form }: { study: string; course: string; userId: number; assignment: string; stage: Stage; form: Form }) {
  const [answers, setAnswers] = useState<Record<string, Answer>>({})
  const [links, setLinks] = useState({ outcome_id: '', task_id: '', response_id: '' })
  const [status, setStatus] = useState('')
  const [busy, setBusy] = useState(false)
  const [requestKey, setRequestKey] = useState(key)
  const [correction, setCorrection] = useState({ supersedes_id: '', correction_reason_code: '' })
  const answer = (id: string, value: Answer) => { setAnswers(current => ({ ...current, [id]: value })); setRequestKey(key()); setStatus('') }
  async function submit() {
    setBusy(true)
    try {
      const result = await studyApi.submit(study, course, { allocation_id: assignment, record: {
        request_key: requestKey, subject_user_id: userId, form_version_id: form.id, sequence_key: assignment, stage, kind: 'response',
        answers: form.definition.items.map(item => answers[item.item_id]), ...(correction.supersedes_id ? correction : {}), links: Object.fromEntries(Object.entries(links).filter(([, value]) => value)),
      } })
      setStatus(`Response saved. Receipt: ${result.id}`)
    } catch { setStatus('Response could not be saved. Your answers are still here; check consent and try again.') }
    finally { setBusy(false) }
  }
  return <Card heading={`${form.definition.title} — ${stage}`}>
    <p>Version {form.version}. Synthetic validation only. This does not create a formal assessment result.</p>
    <form onSubmit={e => { e.preventDefault(); void submit() }}>
      {form.definition.items.map(item => <fieldset key={item.item_id} disabled={busy}>
        <legend>{item.prompt}</legend>
        <Field label="Response status"><select value={answers[item.item_id]?.missing_reason ?? ''} onChange={e => answer(item.item_id, e.target.value ? { item_id: item.item_id, missing_reason: e.target.value as Answer['missing_reason'] } : { item_id: item.item_id })}>
          <option value="">Provide an answer</option><option value="participant_skipped">Prefer to skip</option><option value="technical_failure">Technical problem</option><option value="not_applicable">Not applicable</option>
        </select></Field>
        {!answers[item.item_id]?.missing_reason && <Field label="Your answer">
          {item.response_type === 'choice' ? <select required value={answers[item.item_id]?.choice_code ?? ''} onChange={e => answer(item.item_id, { item_id: item.item_id, choice_code: e.target.value })}><option value="">Choose…</option>{item.choices?.map(choice => <option key={choice}>{choice}</option>)}</select>
            : item.response_type === 'integer' ? <input required type="number" min={item.minimum ?? undefined} max={item.maximum ?? undefined} value={answers[item.item_id]?.integer_value ?? ''} onChange={e => answer(item.item_id, { item_id: item.item_id, integer_value: e.target.value === '' ? null : Number(e.target.value) })} />
              : <textarea required maxLength={item.max_characters ?? undefined} value={answers[item.item_id]?.response_text ?? ''} onChange={e => answer(item.item_id, { item_id: item.item_id, response_text: e.target.value })} />}
        </Field>}
      </fieldset>)}
      <details><summary>Correct an earlier response</summary><Field label="Earlier response receipt"><input value={correction.supersedes_id} onChange={e => { setCorrection({ ...correction, supersedes_id: e.target.value }); setRequestKey(key()) }} /></Field><Field label="Correction reason"><select value={correction.correction_reason_code} onChange={e => { setCorrection({ ...correction, correction_reason_code: e.target.value }); setRequestKey(key()) }}><option value="">Choose supplied reason…</option>{form.definition.event_reason_codes?.map(reason => <option key={reason}>{reason}</option>)}</select></Field></details>
      <details><summary>Learning evidence references</summary><p>Use the references supplied for this activity. Formal stages require the task and submitted response.</p>
        {Object.entries(links).map(([name, value]) => <Field key={name} label={name.replace('_id', ' reference')}><input value={value} onChange={e => { setLinks({ ...links, [name]: e.target.value }); setRequestKey(key()) }} /></Field>)}
      </details>
      <Button type="submit" disabled={busy || (!!correction.supersedes_id && !correction.correction_reason_code) || form.definition.items.some(item => !answers[item.item_id])}>{busy ? 'Saving…' : 'Submit study response'}</Button>
      <p role="status">{status}</p>
    </form>
  </Card>
}

function StudyParticipationPageContent({ user }: { user: AuthUser }) {
  const { studyId = '', courseId = '' } = useParams()
  const [participation, setParticipation] = useState<Participation | null>(null)
  const [forms, setForms] = useState<Assignment[]>([])
  const [fields, setFields] = useState<string[]>([])
  const [acknowledged, setAcknowledged] = useState(false)
  const [operationalConsent, setOperationalConsent] = useState(false)
  const [status, setStatus] = useState('')
  const [busy, setBusy] = useState(false)
  const [reload, setReload] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    void studyApi.participation(studyId, courseId, controller.signal).then(value => { if (!controller.signal.aborted) setParticipation(value) }).catch(() => { if (!controller.signal.aborted) setStatus('Participation details are unavailable.') })
    void studyApi.forms(studyId, courseId, controller.signal).then(value => { if (!controller.signal.aborted) setForms(value) }).catch(() => { if (!controller.signal.aborted) setForms([]) })
    return () => controller.abort()
  }, [studyId, courseId, reload])
  async function decide(decision: 'consented' | 'declined' | 'withdrawn') {
    if (!participation) return
    setBusy(true)
    try {
      await studyApi.governance(studyId, { request_key: key(), expected_revision: participation.revision, reason: 'participant-self-decision', decision: {
        kind: 'consent', scope_id: participation.scope_id, course_id: courseId, subject_user_id: Number(user.id), decision,
        consent_version: participation.scope.consent_version, fields: decision === 'consented' ? fields : [], purposes: decision === 'consented' ? ['study_instruments', ...(operationalConsent ? ['study_operational_evidence'] : [])] : [],
      } })
      setForms([]); setAcknowledged(false); setStatus(`Participation decision recorded: ${decision}.`); setReload(n => n + 1)
    } catch { setStatus('Decision could not be saved. Reload current details before trying again.') }
    finally { setBusy(false) }
  }
  return <section aria-label="Study participation"><h1>Study participation</h1>
    <p>Production research remains closed. Participation decisions do not affect course access, learning support or assessment results.</p>
    <p role="status">{status}</p>
    <Button onClick={() => { setForms([]); setParticipation(null); setReload(n => n + 1) }}>Reload study details</Button>
    {participation && <Card heading="Your participation choice">
      <p>Consent version: {participation.scope.consent_version}. Current choice: {participation.consent?.decision ?? 'No decision recorded'}.</p>
      <p>Read the information sheet supplied by the study team before choosing. A saved choice does not activate a study.</p>
      <fieldset disabled={busy}><legend>Fields you permit for study use</legend>{participation.scope.fields.filter(f => !f.startsWith('processing.') && !['define', 'prepare', 'allocate', 'collect', 'read', 'export', 'packet', 'rate', 'outcome'].some(op => f.endsWith(`.${op}`))).map(field => <label key={field} style={{ display: 'block' }}><input type="checkbox" checked={fields.includes(field)} onChange={e => setFields(current => e.target.checked ? [...current, field] : current.filter(f => f !== field))} /> {field}</label>)}</fieldset>
      {participation.scope.purposes.some(p => String(p) === 'study_operational_evidence') && <label><input type="checkbox" checked={operationalConsent} onChange={e => setOperationalConsent(e.target.checked)} /> Allow the selected operational evidence to be used for this study</label>}
      <label><input type="checkbox" checked={acknowledged} onChange={e => setAcknowledged(e.target.checked)} /> I have read the supplied information and consent version and choose the fields above.</label>
      <div><Button disabled={busy || !acknowledged || !fields.length} onClick={() => void decide('consented')}>Record consent</Button>
        <Button disabled={busy} onClick={() => void decide('declined')}>Decline participation</Button>
        <Button disabled={busy} onClick={() => void decide('withdrawn')}>Withdraw participation</Button></div>
    </Card>}
    {!forms.length && <p>No study forms are currently available under your consent, allocation and the research release controls.</p>}
    {forms.flatMap(assignment => assignment.stages.map(({ stage, form }) => <InstrumentResponse key={`${assignment.allocation_id}:${stage}`} study={studyId} course={courseId} userId={Number(user.id)} assignment={assignment.allocation_id} stage={stage} form={form} />))}
  </section>
}

export function StudyParticipationPage({ user }: { user: AuthUser }) {
  const { studyId, courseId } = useParams()
  return <StudyParticipationPageContent key={`${studyId}:${courseId}`} user={user} />
}
