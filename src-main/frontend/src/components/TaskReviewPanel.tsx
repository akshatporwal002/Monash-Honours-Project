import { StructuredTaskEditor } from './StructuredTaskEditor'
import { useCallback, useEffect, useState } from 'react'

import { ApiError, api } from '../app/api'
import type { ApiSchemas } from '../api/generated'
import { TaskMarkingEditor } from './TaskMarkingEditor'
import { EpisodePlanEditor } from './EpisodePlanEditor'
import { PracticeRepresentationEditor } from '../features/practice-representations/PracticeRepresentationEditor'
import { Button, Field, Input, Select, Tag, Textarea } from './ui'
import styles from './TaskReviewPanel.module.css'
import { CategoryQualityReview } from './CategoryQualityReview'
import type { QualitySubmission } from './categoryQualityReviewTypes'

type Summary = ApiSchemas['TaskReviewSummary'] & { quality_review_required?: boolean }
type History = ApiSchemas['TaskReviewHistoryRead']
type Action = ApiSchemas['TaskReviewWrite']['state']

const labels: Record<Summary['state'], string> = {
  DRAFT: 'Draft', SUBMITTED: 'Awaiting review', APPROVED: 'Approved',
  REJECTED: 'Changes requested', WITHDRAWN: 'Withdrawn',
}

function text(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function message(error: unknown): string {
  return error instanceof ApiError ? error.message : 'The task review could not be loaded. Please try again.'
}

function RevisionReview({ taskId }: { taskId: string }) {
  const [summary, setSummary] = useState<Summary | null>(null)
  const [history, setHistory] = useState<History[]>([])
  const [form, setForm] = useState({ title: '', prompt: '', instructions: '', expected_answer: '', starter_code: '' })
  const [criteria, setCriteria] = useState<Record<string, unknown>>({})
  const [criteriaDirty, setCriteriaDirty] = useState(false)
  const [taskType, setTaskType] = useState('')
  const [reason, setReason] = useState('')
  const [dirty, setDirty] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [reload, setReload] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [quality, setQuality] = useState<QualitySubmission | null>(null)
  const [qualityReady, setQualityReady] = useState(false)
  const qualityChanged = useCallback((value: QualitySubmission | null, ready: boolean) => {
    setQuality(value); setQualityReady(ready)
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    void Promise.all([
      api.taskReview.summary(taskId, controller.signal),
      api.taskReview.history(taskId, 0, controller.signal),
    ]).then(([current, entries]) => {
      if (controller.signal.aborted) return
      const snapshot = entries[0]?.revision.snapshot ?? {}
      setSummary(current)
      setQuality(null); setQualityReady(false)
      setHistory(entries)
      setHasMore(entries.length === 20)
      setForm({
        title: text(snapshot.title), prompt: text(snapshot.description),
        instructions: text(snapshot.instructions), expected_answer: text(snapshot.expected_answer),
        starter_code: text(snapshot.starter_code),
      })
      setDirty(false)
      const marking = snapshot.marking_criteria
      setCriteria(marking !== null && typeof marking === 'object' && !Array.isArray(marking) ? marking as Record<string, unknown> : {})
      setCriteriaDirty(false)
      setTaskType(text(snapshot.task_type))
    }).catch((caught: unknown) => {
      if (!controller.signal.aborted) setError(message(caught))
    })
    return () => controller.abort()
  }, [taskId, reload])

  const edit = (field: keyof typeof form, value: string) => {
    setForm((current) => ({ ...current, [field]: value }))
    setDirty(true)
    setNotice('')
  }

  const save = async () => {
    if (!summary?.revision_id) return
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const markingCriteria = Object.fromEntries(Object.entries(criteria).map(([key, value]) => [key,
        ['required_keywords', 'required_terms', 'required_code_fragments', 'correct_answers', 'required_gates', 'allowed_gates'].includes(key) && Array.isArray(value)
          ? value.filter((item) => typeof item !== 'string' || item.trim()).map((item) => typeof item === 'string' ? item.trim() : item) : value,
      ]))
      await api.taskReview.edit(taskId, { ...form, ...(criteriaDirty ? { marking_criteria: markingCriteria } : {}), expected_revision_id: summary.revision_id })
      setSummary(null)
      setReason('')
      setReload((value) => value + 1)
      setNotice('Task saved. Review the saved revision before approving it.')
    } catch (caught) {
      setError(message(caught))
    } finally {
      setBusy(false)
    }
  }

  const record = async (state: Action) => {
    if (!summary?.revision_id || dirty) return
    if (state === 'APPROVED' && (summary.quality_review_required || history[0]?.revision.provenance === 'GENERATED') && !qualityReady) return
    setBusy(true)
    setError('')
    setNotice('')
    try {
      await api.taskReview.record(taskId, {
        expected_revision_id: summary.revision_id,
        expected_review_version: summary.review_version, state, reason,
        ...(quality && (state === 'APPROVED' || state === 'REJECTED') ? { quality_review: quality } : {}),
      })
      setSummary(null)
      setReason('')
      setReload((value) => value + 1)
      setNotice('Review action recorded.')
    } catch (caught) {
      setError(message(caught))
    } finally {
      setBusy(false)
    }
  }

  const moreHistory = async () => {
    setBusy(true)
    setError('')
    try {
      const entries = await api.taskReview.history(taskId, history.length)
      setHistory((current) => [...current, ...entries])
      setHasMore(entries.length === 20)
    } catch (caught) {
      setError(message(caught))
    } finally {
      setBusy(false)
    }
  }

  const actions: Array<{ state: Action; label: string }> = summary?.state === 'SUBMITTED'
    ? [{ state: 'APPROVED', label: 'Approve task' }, { state: 'REJECTED', label: 'Request changes' }, { state: 'WITHDRAWN', label: 'Withdraw review' }]
    : summary?.state === 'APPROVED'
      ? [{ state: 'WITHDRAWN', label: 'Withdraw approval' }]
      : [{ state: 'SUBMITTED', label: 'Submit for review' }]

  return <div className={styles.panel}>
    {error && <p role="alert">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    <Button variant="quiet" disabled={busy} onClick={() => { setError(''); setSummary(null); setReload((value) => value + 1) }}>
      Reload saved review
    </Button>
    {summary ? <>
      <p><Tag>{labels[summary.state]}</Tag> Revision {summary.revision}</p>
      {summary.issues.length > 0 && <ul>{summary.issues.map((issue) => <li key={issue}>{issue}</li>)}</ul>}
      <p>Approval applies to this saved task. Changes require a new review.</p>
      <Field label="Task title"><Input disabled={busy} value={form.title} onChange={(event) => edit('title', event.target.value)} /></Field>
      <Field label="Task prompt"><Textarea disabled={busy} value={form.prompt} onChange={(event) => edit('prompt', event.target.value)} /></Field>
      <Field label="Task instructions"><Textarea disabled={busy} value={form.instructions} onChange={(event) => edit('instructions', event.target.value)} /></Field>
      <Field label="Expected answer" help="Marking guidance is visible only to authorised reviewers.">
        <Textarea disabled={busy} value={form.expected_answer} onChange={(event) => edit('expected_answer', event.target.value)} />
      </Field>
      {form.starter_code && <Field label="Starter code"><Textarea disabled={busy} value={form.starter_code} onChange={(event) => edit('starter_code', event.target.value)} /></Field>}
      {(taskType === 'matching' || taskType === 'sequencing') && <StructuredTaskEditor type={taskType} value={criteria} answer={form.expected_answer} disabled={busy} onAnswer={answer => edit('expected_answer', answer)} onChange={next => { setCriteria(next); setCriteriaDirty(true); setDirty(true) }} />}
      <TaskMarkingEditor taskType={taskType} value={criteria} disabled={busy} onChange={(next) => { setCriteria(next); setCriteriaDirty(true); setDirty(true); setNotice('') }} />
      <EpisodePlanEditor value={criteria} disabled={busy} onChange={(next) => { setCriteria(next); setCriteriaDirty(true); setDirty(true); setNotice('') }} />
      <PracticeRepresentationEditor value={criteria} disabled={busy} onChange={(next) => { setCriteria(next); setCriteriaDirty(true); setDirty(true); setNotice('') }} />
      <Button onClick={() => void save()} disabled={busy || !dirty || !summary.revision_id}>Save task revision</Button>
      <Field label="Review reason" required><Textarea maxLength={2000} disabled={busy} value={reason} onChange={(event) => setReason(event.target.value)} /></Field>
      {summary.state === 'SUBMITTED' && summary.revision_id && (summary.quality_review_required || history[0]?.revision.provenance === 'GENERATED') && <CategoryQualityReview key={`${summary.revision_id}-${summary.review_version}`} taskId={taskId} revisionId={summary.revision_id} reviewVersion={summary.review_version} disabled={busy || dirty} onChange={qualityChanged} />}
      {dirty && <p>Save your edits before recording a review.</p>}
      <div className={styles.actions}>{actions.map((action) => <Button
        key={action.state} disabled={busy || dirty || !reason.trim() || !summary.revision_id || (action.state === 'APPROVED' && (summary.quality_review_required || history[0]?.revision.provenance === 'GENERATED') && !qualityReady)}
        onClick={() => void record(action.state)}
      >{action.label}</Button>)}</div>
      <details>
        <summary>Saved content and review history</summary>
        {history.map((entry) => <article key={entry.revision.id} className={styles.entry}>
          <h4>Revision {entry.revision.version}: {text(entry.revision.snapshot.title)}</h4>
          <p>{text(entry.revision.snapshot.description)}</p>
          <p>{text(entry.revision.snapshot.instructions)}</p>
          <p>Expected answer: {text(entry.revision.snapshot.expected_answer) || 'See marking criteria'}</p>
          <details><summary>Marking criteria and circuit settings</summary><pre>{JSON.stringify(entry.revision.snapshot.marking_criteria, null, 2)}</pre></details>
          <p>Source passages: {Array.isArray(entry.revision.snapshot.source_references) ? entry.revision.snapshot.source_references.map(String).join(', ') || 'Teacher-authored practice' : 'None'}</p>
          <p>Saved {new Date(entry.revision.created_at).toLocaleString()}</p>
          <ol>{entry.events.map((event) => <li key={event.id}>
            {labels[event.state]}: {event.reason} ({new Date(event.created_at).toLocaleString()})
          </li>)}</ol>
          {'quality_reviews' in entry && <details><summary>Saved quality findings</summary><pre>{JSON.stringify(entry.quality_reviews, null, 2)}</pre></details>}
        </article>)}
        {hasMore && <Button disabled={busy} onClick={() => void moreHistory()}>Load earlier revisions</Button>}
      </details>
    </> : !error && <p role="status">Loading task review...</p>}
  </div>
}

export function TaskReviewPanel({ courseId }: { courseId: string }) {
  const [tasks, setTasks] = useState<ApiSchemas['TaskRead'][]>([])
  const [taskId, setTaskId] = useState('')
  const [error, setError] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    void api.taskReview.tasks(courseId, controller.signal).then((saved) => {
      if (!controller.signal.aborted) setTasks(saved)
    }).catch((caught: unknown) => {
      if (!controller.signal.aborted) setError(message(caught))
    })
    return () => controller.abort()
  }, [courseId])

  return <section aria-label="Task review" className={styles.panel}>
    <h2>Review saved tasks</h2>
    {error && <p role="alert">{error}</p>}
    <Field label="Task to review"><Select value={taskId} onValueChange={setTaskId}
      options={tasks.map((task) => ({ value: task.id, label: task.title }))} placeholder="Choose a saved task" />
    </Field>
    {taskId && <RevisionReview key={taskId} taskId={taskId} />}
  </section>
}
