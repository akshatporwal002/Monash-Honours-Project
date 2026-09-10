import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import type { ApiSchemas } from '../../api/generated'
import { request } from '../../app/api'
import { Card, ErrorState, PageHeader } from '../../components/ui'
import styles from './LearningProgress.module.css'

export function ProgressRecordList({ role }: { role: 'student' | 'educator' }) {
  const [search, setSearch] = useSearchParams()
  const query = search.toString()
  const course = search.get('course') ?? ''
  const kind = search.get('kind') ?? ''
  const offset = Number(search.get('offset') ?? 0)
  const [saved, setSaved] = useState<{ query: string; data: ApiSchemas['ProgressTrendPage'] } | null>(null)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const data = saved?.query === query ? saved.data : null
  useEffect(() => {
    const controller = new AbortController()
    const params = new URLSearchParams(query)
    params.delete('course')
    request<ApiSchemas['ProgressTrendPage']>(`/progress/${encodeURIComponent(course)}/records?${params}`, { signal: controller.signal })
      .then(data => { if (!controller.signal.aborted) { setSaved({ query, data }); setError('') } })
      .catch(error => { if (!controller.signal.aborted) { setSaved(null); setError(String(error)) } })
    return () => controller.abort()
  }, [course, query, retry])
  const page = (offset: number) => { const params = new URLSearchParams(query); params.set('offset', String(offset)); setSearch(params) }
  return <div className={styles.page}>
    <PageHeader title="Contributing learning records" description={kind.toLowerCase().replaceAll('_', ' ').replaceAll(':', ': ')} />
    <Link to={`/${role}/${role === 'student' ? 'progress' : 'analytics'}?${new URLSearchParams({ course })}`}>Back to learning progress</Link>
    {error && <ErrorState title="Records unavailable" description={error} onRetry={() => setRetry(value => value + 1)} />}
    {!data && !error && <p role="status">Loading records...</p>}
    {data && <>
      {!data.items.length && <p>No records match this scope.</p>}
      {data.items.map(row => <Card key={`${row.kind}:${row.id}`} heading={row.learner_name}>
        <p>{new Date(row.occurred_at).toLocaleString()}. {row.kind.toLowerCase().replaceAll('_', ' ').replaceAll(':', ': ')}</p>
        {row.reason && <p>{row.reason}</p>}
        {row.uncertainty !== null && <p>Estimate uncertainty: {row.uncertainty}. This is an inference, not a formal result.</p>}
        <ul>{row.evidence_ids.map(id => <li key={id}><Link to={`/${role}/evidence/${encodeURIComponent(id)}?${new URLSearchParams({ course })}`}>Inspect contributing observation {id}</Link></li>)}</ul>
        {!row.evidence_ids.length && <p>No linked observation is available in this scope.</p>}
        {role === 'student' && row.task_id && <Link to={`/student/tasks/${encodeURIComponent(row.task_id)}`}>Open task response and result history</Link>}
        <p><Link to={`/${role}/learner-model?${new URLSearchParams({ course, learner: String(row.learner_id), outcome: row.outcome_id })}`}>Inspect estimate and correction history</Link></p>
      </Card>)}
      <nav aria-label="Contributing record pages">
        {offset > 0 && <button onClick={() => page(Math.max(0, offset - 25))}>Previous records</button>}
        {data.next_offset !== null && <button onClick={() => page(data.next_offset!)}>Next records</button>}
      </nav>
    </>}
  </div>
}
