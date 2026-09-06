import { useEffect, useState } from 'react'

import { ApiError, api } from '../app/api'
import type { ApiSchemas } from '../api/generated'
import { Button, Field, Input, Select, Tag, Textarea } from './ui'
import styles from './TaskReviewPanel.module.css'

type Summary = ApiSchemas['TaskReviewSummary']
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
  const [reason, setReason] = useState('')
  const [dirty, setDirty] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [reload, setReload] = useState(0)
  const [hasMore, setHasMore] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    void Promise.all([
      api.taskReview.summary(taskId, controller.signal),
      api.taskReview.history(taskId, 0, controller.signal),
    ]).then(([current, entries]) => {
      if (controller.signal.aborted) return
      const snapshot = entries[0]?.revision.snapshot ?? {}
      setSummary(current)
      setHistory(entries)
      setHasMore(entries.length === 20)
      setForm({
        title: text(snapshot.title), prompt: text(snapshot.description),
        instructions: text(snapshot.instructions), expected_answer: text(snapshot.expected_answer),
        starter_code: text(snapshot.starter_code),
      })
      setDirty(false)
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
      await api.taskReview.edit(taskId, { ...form, expected_revision_id: summary.revision_id })
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
    setBusy(true)
    setError('')
    setNotice('')
    try {
      await api.taskReview.record(taskId, {
        expected_revision_id: summary.revision_id,
        expected_review_version: summary.review_version, state, reason,
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
      <Button onClick={() => void save()} disabled={busy || !dirty || !summary.revision_id}>Save task revision</Button>
      <Field label="Review reason" required><Textarea maxLength={2000} disabled={busy} value={reason} onChange={(event) => setReason(event.target.value)} /></Field>
      {dirty && <p>Save your edits before recording a review.</p>}
      <div className={styles.actions}>{actions.map((action) => <Button
        key={action.state} disabled={busy || dirty || !reason.trim() || !summary.revision_id}
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
    <h3>Review saved tasks</h3>
    {error && <p role="alert">{error}</p>}
    <Field label="Task to review"><Select value={taskId} onValueChange={setTaskId}
      options={tasks.map((task) => ({ value: task.id, label: task.title }))} placeholder="Choose a saved task" />
    </Field>
    {taskId && <RevisionReview key={taskId} taskId={taskId} />}
  </section>
}
