import styles from './CurriculumPanel.module.css'
import { useEffect, useState } from 'react'
import { api } from '../app/api'
import type { ApiSchemas } from '../api/generated'
import { curriculum } from '../app/curriculum'
import type { Pathway, PathwayPublish } from '../app/curriculum'
import { Button, Card } from './ui'

type Task = ApiSchemas['TaskRead']

export function PathwayEditor({ courseId }: { courseId: string }) {
  const [tasks, setTasks] = useState<Task[]>([])
  const [paths, setPaths] = useState<Pathway[]>([])
  const [error, setError] = useState('')
  const [selected, setSelected] = useState('')
  useEffect(() => {
    let active = true
    Promise.all([api.taskReview.tasks(courseId), curriculum.pathways(courseId)]).then(([rows, saved]) => {
      if (active) { setTasks(rows); setPaths(saved) }
    }).catch(e => { if (active) setError(e instanceof Error ? e.message : 'Could not load tasks') })
    return () => { active = false }
  }, [courseId])
  const outcomes = [...new Map(tasks.map(task => [task.learning_outcome_id, task])).values()]
  return <Card className={styles.panel} heading="Publish a learning pathway">
    <p>Choose an outcome with at least three approved, sourced tasks. Publication records your approval of the diagnostic and exit rules.</p>
    {error && <p role="alert">{error}</p>}
    <label>Outcome<select value={selected} onChange={event => setSelected(event.target.value)}>
      <option value="">Choose an outcome</option>{outcomes.map(task => <option key={task.learning_outcome_id} value={task.learning_outcome_id}>Outcome containing {task.title}</option>)}
    </select></label>
    {selected && <PathwayForm key={selected} tasks={tasks.filter(task => task.learning_outcome_id === selected).sort((a, b) => a.position - b.position)}
      existing={paths.find(path => path.outcome_id === selected)} onSaved={saved => setPaths(rows => [...rows.filter(path => path.outcome_id !== saved.outcome_id), saved])} />}
  </Card>
}

function PathwayForm({ tasks, existing, onSaved }: { tasks: Task[]; existing?: Pathway; onSaved: (path: Pathway) => void }) {
  const [draft, setDraft] = useState<PathwayPublish>(() => ({
    expected_version: existing?.version ?? 0, request_key: crypto.randomUUID(), title: existing?.title ?? '',
    steps: existing?.steps ?? tasks.map((task, index) => ({ task_id: task.id, concept: '', prerequisites: [...new Set([...(task.prerequisite_task_ids ?? []), ...(index ? [tasks[index - 1].id] : [])])],
      support_level: 'guided', faded_support_level: 'concept_cue', exit_rule: 'accepted_response', evidence_rule: '' })),
    diagnostic_task_id: existing?.diagnostic_task_id ?? tasks[0].id, diagnostic_prompt: existing?.diagnostic_prompt ?? '',
    independent_conditions: existing?.independent_conditions ?? '', reason: '',
  }))
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const save = async () => {
    setBusy(true); setError(''); setNotice('')
    try {
      const saved = await curriculum.publish(tasks[0].learning_outcome_id, draft)
      onSaved(saved); setDraft(current => ({ ...current, expected_version: saved.version, request_key: crypto.randomUUID() }))
      setNotice(`Pathway version ${saved.version} published.`)
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not publish pathway') } finally { setBusy(false) }
  }
  return <form onSubmit={event => { event.preventDefault(); void save() }}>
    {notice && <p role="status">{notice}</p>}{error && <p role="alert">{error} Your draft is retained.</p>}
    {error && <Button variant="secondary" disabled={busy} onClick={async () => {
      setBusy(true)
      try {
        const saved = (await curriculum.pathways(tasks[0].course_id)).find(path => path.outcome_id === tasks[0].learning_outcome_id)
        setDraft(current => ({ ...current, expected_version: saved?.version ?? 0, request_key: crypto.randomUUID() }))
        setNotice('Saved version refreshed. Review your retained draft before publishing.'); setError('')
      } catch (e) { setError(e instanceof Error ? e.message : 'Could not refresh the saved version') } finally { setBusy(false) }
    }}>Refresh saved version, keep draft</Button>}
    <fieldset disabled={busy}>
      <label>Pathway title<input required maxLength={200} value={draft.title} onChange={event => setDraft({ ...draft, title: event.target.value })} /></label>
      <ol>{draft.steps.map((step, index) => <li key={step.task_id}>
        <p>{tasks.find(task => task.id === step.task_id)?.title ?? 'Earlier task'}: an accepted response completes this step.</p>
        <label>Concept for step {index + 1}<input required maxLength={100} value={step.concept} onChange={event => setDraft({ ...draft, steps: draft.steps.map((item, position) => position === index ? { ...item, concept: event.target.value } : item) })} /></label>
        <label>Evidence guidance for step {index + 1}<textarea required maxLength={2000} value={step.evidence_rule} onChange={event => setDraft({ ...draft, steps: draft.steps.map((item, position) => position === index ? { ...item, evidence_rule: event.target.value } : item) })} /></label>
        {(['support_level', 'faded_support_level'] as const).map(field => <label key={field}>{field === 'support_level' ? 'Starting support' : 'Support after confirmed success'} for step {index + 1}
          <select value={step[field]} onChange={event => setDraft({ ...draft, steps: draft.steps.map((item, position) => position === index ? { ...item, [field]: event.target.value } : item) })}>
            <option value="guided">Guided</option><option value="concept_cue">Concept cue</option><option value="independent">Independent</option>
          </select></label>)}
      </li>)}</ol>
      <label>Diagnostic activity<select value={draft.diagnostic_task_id} onChange={event => setDraft({ ...draft, diagnostic_task_id: event.target.value })}>
        {tasks.filter(task => !task.assessment).map(task => <option key={task.id} value={task.id}>{task.title}</option>)}
      </select></label>
      <label>Approved diagnostic prompt<textarea required maxLength={2000} value={draft.diagnostic_prompt} onChange={event => setDraft({ ...draft, diagnostic_prompt: event.target.value })} /></label>
      <label>Independent conditions<textarea required maxLength={2000} value={draft.independent_conditions} onChange={event => setDraft({ ...draft, independent_conditions: event.target.value })} /></label>
      <label>Publication reason<textarea required maxLength={2000} value={draft.reason} onChange={event => setDraft({ ...draft, reason: event.target.value })} /></label>
      <Button type="submit" disabled={draft.steps.length < 3}>{busy ? 'Publishing...' : 'Approve and publish pathway'}</Button>
    </fieldset>
  </form>
}
