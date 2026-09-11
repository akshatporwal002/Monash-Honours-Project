import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import type { ApiSchemas } from '../../api/generated'
import { request } from '../../app/api'
import { Card, EmptyState, ErrorState, PageHeader } from '../../components/ui'
import styles from './LearningProgress.module.css'
import { ProfileReview } from './ProfileReview'
import type { ProgressIndicator } from './ProfileReview'

type Scope = ApiSchemas['LearningProgressPage']['items'][number] & { snapshot_version?: number; indicators?: ProgressIndicator[]; indicator_evidence_truncated?: boolean }
type Page = Omit<ApiSchemas['LearningProgressPage'], 'items'> & { items: Scope[] }
const label = (value: string) => value.toLowerCase().replaceAll('_', ' ')
const when = (value: string) => new Date(value).toLocaleString()

export function LearningProgress({ role }: { role: 'student' | 'educator' }) {
  const [search, setSearch] = useSearchParams()
  const course = search.get('course') ?? ''
  const learner = search.get('learner') ?? ''
  const parsedOffset = Number(search.get('offset') ?? 0)
  const offset = Number.isSafeInteger(parsedOffset) && parsedOffset >= 0 ? parsedOffset : 0
  const scopeKey = `${course}:${learner}:${offset}`
  const [courses, setCourses] = useState<Array<{ id: string; title: string }>>([])
  const [saved, setSaved] = useState<{ scope: string; page: Page } | null>(null)
  const data = saved?.scope === scopeKey ? saved.page : null
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    request<Array<{ id: string; title: string }>>('/courses', { signal: controller.signal })
      .then(setCourses).catch(error => { if (!controller.signal.aborted) setError(String(error)) })
    return () => controller.abort()
  }, [retry])
  useEffect(() => {
    if (!course) return
    const controller = new AbortController()
    const query = new URLSearchParams({ offset: String(offset) })
    if (learner) query.set('learner_id', learner)
    request<Page>(`/progress/${encodeURIComponent(course)}?${query}`, { signal: controller.signal })
      .then(value => { if (!controller.signal.aborted) { setSaved({ scope: scopeKey, page: value }); setError('') } })
      .catch(error => { if (!controller.signal.aborted) { setSaved(null); setError(String(error)) } })
    return () => controller.abort()
  }, [course, learner, offset, retry, scopeKey])
  const choose = (values: Record<string, string>) => { setSaved(null); setError(''); setSearch(values) }
  const history = (item: Scope) => `/${role}/learner-model?${new URLSearchParams({ course, learner: String(item.learner_id), outcome: item.outcome_id })}`
  const evidenceLink = (id: string) => `/${role}/evidence/${encodeURIComponent(id)}?${new URLSearchParams({ course })}`
  const recordsLink = (kind: string, week?: string, item?: Scope, responseId?: string) => `/${role}/progress/records?${new URLSearchParams({ course, kind, ...(responseId ? { response_id: responseId } : {}), ...(week ? { week } : {}), ...(item ? { learner_id: String(item.learner_id), outcome_id: item.outcome_id } : learner ? { learner_id: learner } : {}) })}`
  return <div className={styles.page}>
    <PageHeader title={role === 'student' ? 'My learning progress' : 'Cohort learning progress'} description="Inspect activity, recorded evidence, uncertain estimates and released assessment results." />
    <div><label htmlFor="progress-course">Course</label><select id="progress-course" value={course} onChange={event => choose({ course: event.target.value })}><option value="">Choose a course</option>{courses.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select></div>
    {learner && role === 'educator' && <button onClick={() => choose({ course })}>Show the whole cohort</button>}
    {error && <ErrorState title="Progress unavailable" description={error} onRetry={() => setRetry(value => value + 1)} />}
    {!course && !error && <EmptyState title="Choose a course to inspect its learning history." />}
    {course && !data && !error && <p role="status">Loading learning history…</p>}
    {data && <>
      <Card heading="Recorded activity and evidence">
        <p>Counts describe saved observations from active enrolled learners. More observations do not prove stronger understanding.</p>
        <dl className={styles.counts}>{Object.entries(data.cohort_observations).map(([kind, count]) => <div key={kind}><dt>{label(kind)}</dt><dd><Link to={recordsLink(`observation:${kind}`)}>{count}</Link></dd></div>)}</dl>
        {!Object.keys(data.cohort_observations).length && <p>No learning evidence has been recorded in this scope.</p>}
        <details><summary>Observation counts by week</summary><div className={styles.scroll}><table><caption>Weeks start on Monday. Counts cover all selected learners.</caption><thead><tr><th>Week</th><th>Recorded observations</th></tr></thead><tbody>{Object.entries(data.cohort_weekly_observations).map(([week, counts]) => <tr key={week}><th>{week}</th><td>{Object.entries(counts ?? {}).map(([kind, count]) => `${label(kind)}: ${count}`).join('; ')}</td></tr>)}</tbody></table></div></details>
      </Card>
      <Card heading="Changes across the selected learners">
        <p>Weekly counts keep observations, support use, model estimates, misconception reviews and adaptation choices separate. These are records, not rankings or ability scores.</p>
        <p>Result counts show each response's currently released result, grouped by its submission week. Pending, withheld and void work stays unreleased. Earlier decisions remain in result history.</p>
        <details><summary>Inspect weekly trends and their records</summary><div className={styles.scroll}><table><thead><tr><th>Week starting</th><th>Recorded change</th><th>Count and evidence</th></tr></thead><tbody>{Object.entries(data.cohort_weekly_trends).flatMap(([week, counts]) => Object.entries(counts ?? {}).map(([kind, count]) => <tr key={`${week}:${kind}`}><td>{week}</td><td>{label(kind).replaceAll(':', ': ')}</td><td><Link to={recordsLink(kind, week)}>{count} records</Link></td></tr>))}</tbody></table></div></details>
      </Card>
      <div id="progress-records" className={styles.scopes}>
        {!data.items.length && <EmptyState title="No learner and outcome records are available in this scope." />}
        {data.items.map(item => <Card key={`${item.learner_id}:${item.outcome_id}`} heading={`${item.learner_name}: ${item.outcome_title}`}>
          {role === 'educator' && !learner && <button onClick={() => choose({ course, learner: String(item.learner_id) })}>Focus on {item.learner_name}</button>}
          <p><Link to={history(item)}>Inspect estimate and correction history</Link></p>
          <h3>Observed work</h3><p>Responses, revisions and transfer observations: {item.independent_responses} without recorded instructional help; {item.supported_responses} with help.</p>
          <p>Access support is separate. These counts do not determine a formal result.</p>
          <dl className={styles.counts}>{Object.entries(item.observations).map(([kind, count]) => <div key={kind}><dt>{label(kind)}</dt><dd><Link to={recordsLink(`observation:${kind}`, undefined, item)}>{count}</Link></dd></div>)}</dl>
          <details><summary>Inspect recent observations</summary><p>Up to {data.history_limit} recent observations. Counts open every contributing record. Estimate, result, adaptation and check lists each show their most recent 20 records.</p><ol>{item.recent_evidence.map(row => <li key={row.evidence_id}>{label(row.kind)}, {when(row.occurred_at)}. Instructional support level {row.support_level}.{row.confidence !== null && row.confidence !== undefined && <> Learner confidence: {String(row.confidence)}.</>}<p><Link to={evidenceLink(row.evidence_id)}>Inspect this observation</Link></p>{role === 'student' && <Link to={`/student/tasks/${encodeURIComponent(row.task_id)}`}>Open saved task work</Link>}</li>)}</ol></details>
          <details><summary>Uncertain learning estimates</summary><p>These are evidence-linked inferences. Each change retains its prior snapshot and uncertainty, from 0 to 1.</p>{!item.estimates.length && <p>No estimate has been recorded. Missing evidence does not mean low ability.</p>}<div className={styles.scroll}><table><thead><tr><th>Recorded</th><th>Dimension</th><th>Inference</th><th>Uncertainty</th><th>Reason and evidence</th></tr></thead><tbody>{item.estimates.map(estimate => <tr key={estimate.estimate_id}><td>{when(estimate.occurred_at)}</td><td>{label(estimate.dimension)}</td><td>{label(estimate.status)}</td><td>{estimate.uncertainty}</td><td>{label(estimate.reason)}<ul>{estimate.evidence.map(link => <li key={`${link.evidence_id}:${link.relation}`}><Link to={evidenceLink(link.evidence_id)}>{label(link.relation)}: {link.evidence_id}</Link></li>)}</ul></td></tr>)}</tbody></table></div></details>
          <details><summary>Feedback and question review indicators</summary><p>These cues link observations in time; usefulness and question clarity require inspection. No causal improvement claim is made.</p>{item.indicator_evidence_truncated && <p>Indicators use the latest 200 observations in this outcome. Older evidence remains available through the observation counts.</p>}{!item.indicators?.length && <p>No linked feedback sequence or clarification cue was found in the inspected observations. Absence of a cue does not establish effectiveness.</p>}<ol>{item.indicators?.map(indicator => <li key={indicator.id}>{when(indicator.occurred_at)}: {indicator.explanation} Uncertainty {indicator.uncertainty}.<ul>{indicator.evidence_ids.map(id => <li key={id}><Link to={evidenceLink(id)}>Inspect contributing observation {id}</Link></li>)}</ul></li>)}</ol></details>
          {role === 'educator' && <ProfileReview key={`${scopeKey}:${item.learner_id}:${item.outcome_id}:${item.snapshot_version ?? 0}`} course={course} learner={item.learner_id} outcome={item.outcome_id} version={item.snapshot_version ?? 0} evidence={item.recent_evidence} onSaved={() => { setSaved(null); setRetry(value => value + 1) }} />}
          <h3>Formal assessment results</h3>{!item.results.length && <p>No declared assessment response is available for this outcome.</p>}<ul>{item.results.map(result => <li key={result.response_id}>{result.result ?? 'Result not released'}: {result.status}. {when(result.occurred_at)}. <Link to={recordsLink("result", undefined, item, result.response_id)}>Inspect this response and its evidence</Link></li>)}</ul>
          <h3>Outcome results under published rules</h3>{!item.outcome_results.length && <p>No outcome result is available.</p>}<ul>{item.outcome_results.map(outcome => <li key={outcome.definition_version_id}>{outcome.result ?? 'Result not released'}: {outcome.status}. {outcome.explanation}<ul>{outcome.evidence_response_ids.map(id => <li key={id}>Response {id}. <Link to={recordsLink("result", undefined, item, id)}>Inspect this response evidence</Link></li>)}</ul></li>)}</ul>
          <details><summary>Adaptation and learner choices</summary>{!item.adaptations.length && <p>No adaptation has been recorded.</p>}<ol>{item.adaptations.map(adaptation => <li key={adaptation.workflow_id}>{when(adaptation.occurred_at)}: {label(adaptation.state)}. {adaptation.reason} Uncertainty {adaptation.uncertainty}.<ul>{adaptation.evidence_ids.map(id => <li key={id}><Link to={evidenceLink(id)}>Inspect trigger observation {id}</Link></li>)}</ul><details><summary>Preserved choices</summary><ol>{adaptation.choices.map(choice => <li key={choice.version}>{when(choice.created_at)}: {choice.educator ? 'Educator' : 'Learner'} chose {label(choice.action)}. {choice.reason}{role === 'student' && choice.task_id && <Link to={`/student/tasks/${encodeURIComponent(choice.task_id)}`}>Inspect chosen activity</Link>}</li>)}</ol></details></li>)}</ol></details>
          <h3>Misconception checks and corrections</h3>{!item.misconception_ids.length ? <p>No misconception hypothesis has been recorded.</p> : <ul>{item.misconception_ids.map((id, index) => <li key={id}><Link to={`/${role}/misconceptions/${encodeURIComponent(id)}`}>Inspect check {index + 1}, confidence, evidence and review states</Link></li>)}</ul>}
        </Card>)}
      </div>
      <nav aria-label="Progress pages">{offset > 0 && <button onClick={() => choose({ course, ...(learner ? { learner } : {}), offset: String(Math.max(0, offset - 10)) })}>Previous records</button>}{data.next_offset !== null && <button onClick={() => choose({ course, ...(learner ? { learner } : {}), offset: String(data.next_offset) })}>Next records</button>}</nav>
    </>}
  </div>
}
