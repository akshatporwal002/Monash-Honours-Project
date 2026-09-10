import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import type { ApiSchemas } from '../../api/generated'
import { request } from '../../app/api'
import { Card, ErrorState, PageHeader } from '../../components/ui'
import styles from './LearningProgress.module.css'

export function LearningEvidenceDetail({ role }: { role: 'student' | 'educator' }) {
  const { evidenceId = '' } = useParams()
  const [search] = useSearchParams()
  const course = search.get('course') ?? ''
  const [record, setRecord] = useState<{ id: string; course: string; data: ApiSchemas['ProgressEvidenceDetail'] } | null>(null)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const data = record?.id === evidenceId && record.course === course ? record.data : null
  useEffect(() => {
    const controller = new AbortController()
    request<ApiSchemas['ProgressEvidenceDetail']>(`/progress/${encodeURIComponent(course)}/evidence/${encodeURIComponent(evidenceId)}`, { signal: controller.signal })
      .then(data => { if (!controller.signal.aborted) { setRecord({ id: evidenceId, course, data }); setError('') } })
      .catch(error => { if (!controller.signal.aborted) { setRecord(null); setError(String(error)) } })
    return () => controller.abort()
  }, [course, evidenceId, retry])
  const back = `/${role}/${role === 'student' ? 'progress' : 'analytics'}?${new URLSearchParams({ course, ...(data ? { learner: String(data.learner_id) } : {}) })}`
  return <div className={styles.page}>
    <PageHeader title="Saved learning observation" description="Inspect the recorded work and its evidence links." />
    <Link to={back}>Back to learning progress</Link>
    {error && <ErrorState title="Observation unavailable" description={error} onRetry={() => setRetry(value => value + 1)} />}
    {!data && !error && <p role="status">Loading observation...</p>}
    {data && <Card heading={data.kind.toLowerCase().replaceAll('_', ' ')}>
      <p>{data.status}</p>
      <p>Recorded {new Date(data.occurred_at).toLocaleString()}. Instructional support level {data.support_level}.</p>
      <p>Evidence reference: {data.evidence_id}</p>
      {data.fields.map(field => <section key={field.label}><h3>{field.label}</h3><pre className={styles.observation}>{field.text}</pre></section>)}
      <h3>Related observations</h3>
      {!data.related_evidence_ids.length && <p>No earlier observation is linked to this record.</p>}
      <ul>{data.related_evidence_ids.map(id => <li key={id}><Link to={`/${role}/evidence/${encodeURIComponent(id)}?${new URLSearchParams({ course })}`}>Inspect {id}</Link></li>)}</ul>
    </Card>}
  </div>
}
