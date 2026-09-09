import styles from './CurriculumPanel.module.css'
import { useEffect, useState } from 'react'
import { api } from '../app/api'
import type { CourseSummary } from '../app/types'
import { curriculum } from '../app/curriculum'
import type { Diagnostic, DiagnosticResponse, Pathway } from '../app/curriculum'
import { Button, Card } from './ui'

const message = (error: unknown) => error instanceof Error ? error.message : 'The pathway could not be loaded.'

export function CurriculumPanel({ courseId, staff = false }: { courseId?: string; staff?: boolean }) {
  const [courses, setCourses] = useState<CourseSummary[]>([])
  const [selected, setSelected] = useState(courseId ?? '')
  const [error, setError] = useState('')
  useEffect(() => {
    if (courseId) return
    let active = true
    api.courses.list().then(rows => { if (active) setCourses(rows) }).catch(e => { if (active) setError(message(e)) })
    return () => { active = false }
  }, [courseId])
  return <Card className={styles.panel} heading="Learning pathways">
    {error && <p role="alert">{error}</p>}
    {!courseId && <label>Course <select value={selected} onChange={event => setSelected(event.target.value)}>
      <option value="">Choose a course</option>{courses.map(course => <option key={course.id} value={course.id}>{course.title}</option>)}
    </select></label>}
    {selected && <CoursePathways key={selected} courseId={selected} staff={staff} />}
  </Card>
}

function CoursePathways({ courseId, staff }: { courseId: string; staff: boolean }) {
  const [paths, setPaths] = useState<Pathway[]>([])
  const [records, setRecords] = useState<Diagnostic[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [offset, setOffset] = useState(0)
  const [startKeys] = useState(() => new Map<string, string>())
  const load = async (page = offset) => {
    setBusy(true)
    try {
      const [approved, history] = await Promise.all([curriculum.pathways(courseId), curriculum.diagnostics(courseId, page)])
      setPaths(approved); setRecords(history); setOffset(page); setError('')
    } catch (error) { setError(message(error)) } finally { setBusy(false) }
  }
  useEffect(() => {
    let active = true
    Promise.all([curriculum.pathways(courseId), curriculum.diagnostics(courseId)]).then(([approved, history]) => {
      if (active) { setPaths(approved); setRecords(history) }
    }).catch(e => { if (active) setError(message(e)) })
    return () => { active = false }
  }, [courseId])
  const start = async (path: Pathway, target: string, purpose: 'initial' | 'prior_mastery') => {
    setBusy(true); setError('')
    const slot = `${path.id}:${target}:${purpose}`
    const key = startKeys.get(slot) ?? crypto.randomUUID()
    startKeys.set(slot, key)
    try {
      const record = await curriculum.start({ request_key: key, pathway_id: path.id, target_task_id: target, purpose })
      setRecords(current => [record, ...current.filter(item => item.id !== record.id)])
      startKeys.delete(slot)
    } catch (error) { setError(message(error)) } finally { setBusy(false) }
  }
  return <>
    <p>Diagnostics record learning evidence. They do not award a formal result. A course assessor must confirm any practice bypass.</p>
    <Button variant="secondary" disabled={busy} onClick={() => void load()}>Refresh pathways</Button>
    {error && <p role="alert">{error}</p>}
    {!paths.length && !error && <p>No approved pathway is available for this course.</p>}
    {paths.map(path => <section key={path.id} aria-label={path.title}>
      <h3>{path.title} (version {path.version})</h3>
      <ol>{path.steps.map(step => <li key={step.task_id}>
        <strong>{path.bindings[step.task_id]?.title ?? step.concept}</strong> ({step.concept}): {step.support_level.replaceAll('_', ' ')} support.
        <p>{step.evidence_rule}</p>
      </li>)}</ol>
      {!staff && <>
        <Button disabled={busy} onClick={() => void start(path, path.steps[0].task_id, 'initial')}>Try initial diagnostic</Button>
        <label>Prior-mastery target <select id={`target-${path.id}`} defaultValue={path.steps[0].task_id}>
          {path.steps.map((step, index) => <option key={step.task_id} value={step.task_id}>Step {index + 1}: {path.bindings[step.task_id]?.title ?? step.concept}</option>)}
        </select></label>
        <Button variant="secondary" disabled={busy} onClick={() => {
          const selector = document.getElementById(`target-${path.id}`) as HTMLSelectElement
          void start(path, selector.value, 'prior_mastery')
        }}>Request prior-mastery check</Button>
      </>}
    </section>)}
    <h3>Diagnostic history</h3>
    {records.map(record => <DiagnosticCard key={record.id} record={record} staff={staff} onSaved={saved => setRecords(rows => rows.map(row => row.id === saved.id ? saved : row))} />)}
    <Button variant="quiet" disabled={busy || offset === 0} onClick={() => void load(Math.max(0, offset - 20))}>Previous diagnostics</Button>
    <Button variant="quiet" disabled={busy || records.length < 20} onClick={() => void load(offset + 20)}>More diagnostics</Button>
  </>
}

export function DiagnosticCard({ record, staff, onSaved }: { record: Diagnostic; staff: boolean; onSaved: (saved: Diagnostic) => void }) {
  const [draft, setDraft] = useState<DiagnosticResponse>(() => ({ request_key: crypto.randomUUID(), prior_knowledge: '', reasoning: '', confidence: 'unsure', concept_uncertainty: 'unsure', requested_support: 'none', independent_conditions_met: false }))
  const [reason, setReason] = useState('')
  const [verified, setVerified] = useState(false)
  const [decision, setDecision] = useState<'retain' | 'advance'>('retain')
  const [reviewKey] = useState(() => crypto.randomUUID())
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const save = async () => {
    setBusy(true); setError('')
    try {
      onSaved(staff ? await curriculum.confirm(record.id, { request_key: reviewKey, reason, independent_verified: verified, decision }) : await curriculum.submit(record.id, draft))
    } catch (error) { setError(message(error)) } finally { setBusy(false) }
  }
  return <Card className={styles.panel} heading={record.purpose === 'initial' ? 'Initial diagnostic' : 'Prior-mastery check'}>
    <p role="status">{record.state.replaceAll('_', ' ')}</p>
    {staff && <p>Learner: {record.learner_name}</p>}
    <p>Requested target: {record.target_title}</p>
    <p>{record.prompt}</p><p>{record.independent_conditions}</p>
    {record.reason && <p>Assessor reason: {record.reason}</p>}
    {!staff && record.state === 'advance' && <p><a href={`/student/tasks/${encodeURIComponent(record.target_task_id)}`}>Open approved practice: {record.target_title}</a></p>}
    {record.response && <dl><dt>Prior knowledge</dt><dd>{record.response.prior_knowledge}</dd><dt>Reasoning</dt><dd>{record.response.reasoning}</dd>
      <dt>Confidence</dt><dd>{record.response.confidence}</dd><dt>Concept uncertainty</dt><dd>{record.response.concept_uncertainty}</dd>
      <dt>Requested support</dt><dd>{record.response.requested_support}</dd><dt>Independent conditions declared</dt><dd>{record.response.independent_conditions_met ? 'Yes' : 'No'}</dd></dl>}
    {error && <p role="alert">{error} Your entries are retained.</p>}
    {((!staff && record.state === 'started') || (staff && record.state === 'needs_review')) && <form onSubmit={event => { event.preventDefault(); void save() }}>
      <fieldset disabled={busy}>
        {!staff ? <>
          <label>Prior knowledge<textarea required maxLength={2000} value={draft.prior_knowledge} onChange={event => setDraft({ ...draft, prior_knowledge: event.target.value })} /></label>
          <label>Reasoning<textarea required maxLength={2000} value={draft.reasoning} onChange={event => setDraft({ ...draft, reasoning: event.target.value })} /></label>
          <label>Confidence<select value={draft.confidence} onChange={event => setDraft({ ...draft, confidence: event.target.value as DiagnosticResponse['confidence'] })}><option value="unsure">Unsure</option><option value="somewhat_sure">Somewhat sure</option><option value="sure">Sure</option></select></label>
          <label>Concept uncertainty<select value={draft.concept_uncertainty} onChange={event => setDraft({ ...draft, concept_uncertainty: event.target.value as DiagnosticResponse['concept_uncertainty'] })}><option value="unsure">Unsure</option><option value="needs_checking">Needs checking</option><option value="none_reported">None reported</option></select></label>
          <label>Requested support<select value={draft.requested_support} onChange={event => setDraft({ ...draft, requested_support: event.target.value as DiagnosticResponse['requested_support'] })}><option value="none">None</option><option value="concept_cue">Concept cue</option><option value="guided">Guided</option></select></label>
          <label><input type="checkbox" checked={draft.independent_conditions_met} onChange={event => setDraft({ ...draft, independent_conditions_met: event.target.checked })} />I met the stated independent conditions</label>
        </> : <>
          <p>Confirm only evidence you have checked against the approved pathway criteria. A general teaching role does not grant assessor access.</p>
          <label>Pathway decision<select value={decision} onChange={event => setDecision(event.target.value as 'retain' | 'advance')}><option value="retain">Retain current path</option><option value="advance">Allow practice bypass to requested target</option></select></label>
          <label><input type="checkbox" checked={verified} onChange={event => setVerified(event.target.checked)} />Independent conditions verified</label>
          <label>Assessor reason<textarea required maxLength={2000} value={reason} onChange={event => setReason(event.target.value)} /></label>
        </>}
        <Button type="submit">{busy ? 'Saving...' : staff ? 'Confirm pathway decision' : 'Save diagnostic evidence'}</Button>
      </fieldset>
    </form>}
  </Card>
}
