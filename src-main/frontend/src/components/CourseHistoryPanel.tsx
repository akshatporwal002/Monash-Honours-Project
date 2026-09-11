import { useEffect, useState } from 'react'
import { request } from '../app/api'
import { Button, Card, Field, Textarea } from './ui'

type Revision = {
  id: string
  version: number
  metadata_snapshot: { code: string; title: string; description: string; state: string; enrollment_open: boolean; time_zone: string }
  context_snapshot: {
    modules: { id: string; title: string; description: string; position: number }[]
    enrollments: { id: string; student_id: number; status: string }[]
    sources: { material_id: string; revision_id: string | null; content_hash: string; retired: boolean }[]
  }
  actor_id: string | null
  action: string
  reason: string
  restored_from_id: string | null
  created_at: string
}

export function CourseHistoryPanel({ courseId, onRestored }: { courseId: string; onRestored: () => Promise<void> }) {
  const [history, setHistory] = useState<Revision[]>([])
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    request<Revision[]>(`/courses/${courseId}/revisions`, { signal: controller.signal })
      .then(setHistory).catch((caught: unknown) => {
        if (!controller.signal.aborted) setError(caught instanceof Error ? caught.message : 'History could not be loaded.')
      })
    return () => controller.abort()
  }, [courseId])
  async function restore(revision: Revision) {
    setBusy(true); setError(''); setMessage('')
    try {
      await request(`/courses/${courseId}/revisions/${revision.id}/restore`, {
        method: 'POST', body: JSON.stringify({ expected_version: history[0].version, reason }),
      })
      setHistory(await request<Revision[]>(`/courses/${courseId}/revisions`))
      await onRestored()
      setMessage(`Course details restored from revision ${revision.version}.`)
      setReason('')
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Restoration could not be completed.') }
    finally { setBusy(false) }
  }
  return <Card>
    <h2>Course history</h2>
    <p>Restore the course title, description, code, state, enrolment setting and time zone. Modules, learner records and source approvals keep their current values. Their historical context is available below.</p>
    <Field label="Reason for restoration">
      <Textarea id="course-restore-reason" value={reason} maxLength={2000} onChange={event => setReason(event.target.value)} />
    </Field>
    {error && <p role="alert">{error}</p>}
    {message && <p role="status">{message}</p>}
    {!history.length && <p>No revisions are recorded yet.</p>}
    {history.map(revision => <details key={revision.id}>
      <summary>Revision {revision.version}: {revision.metadata_snapshot.title} — {revision.metadata_snapshot.state}</summary>
      <p>{revision.metadata_snapshot.description}</p>
      <p>Code: {revision.metadata_snapshot.code}. Enrolment: {revision.metadata_snapshot.enrollment_open ? 'open' : 'closed'}. Time zone: {revision.metadata_snapshot.time_zone}.</p>
      <p>{revision.action} · {new Date(revision.created_at).toLocaleString()} · Actor: {revision.actor_id ?? 'unknown (legacy snapshot)'}</p>
      {revision.reason && <p>{revision.reason}</p>}
      {revision.restored_from_id && <p>Restored from record {revision.restored_from_id}</p>}
      <h3>Modules at this revision</h3>
      <ul>{revision.context_snapshot.modules.map(module => <li key={module.id}>{module.position}. {module.title}: {module.description}</li>)}</ul>
      <h3>Enrolment context</h3>
      <ul>{revision.context_snapshot.enrollments.map(enrolment => <li key={enrolment.id}>Learner {enrolment.student_id}: {enrolment.status}</li>)}</ul>
      <h3>Source context</h3>
      <ul>{revision.context_snapshot.sources.map(source => <li key={source.material_id}>Material {source.material_id}: revision {source.revision_id ?? 'not extracted'}, {source.retired ? 'retired' : 'active'}</li>)}</ul>
      <Button disabled={busy || !reason.trim() || revision.id === history[0]?.id} onClick={() => void restore(revision)}>Restore revision {revision.version}</Button>
    </details>)}
  </Card>
}
