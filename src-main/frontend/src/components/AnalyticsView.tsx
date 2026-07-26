import { useEffect, useMemo, useState } from 'react'
import { api } from '../app/api'
import type { EducatorDashboardData } from '../app/types'
import { Icon, PageHeading, Panel, ScreenState } from './ScreenPrimitives'

function TrendChart({ points }: { points: EducatorDashboardData['engagement'] }) {
  const maximum = Math.max(1, ...points.flatMap((point) => [point.active_students, point.submissions]))
  const coordinates = (key: 'active_students' | 'submissions') =>
    points.map((point, index) => {
      const x = points.length <= 1 ? 50 : (index / (points.length - 1)) * 100
      return `${x},${90 - (point[key] / maximum) * 72}`
    }).join(' ')

  if (points.length === 0) return <div className="inline-empty"><p>No cohort trend data is available for this period.</p></div>
  return (
    <figure className="analytics-trend">
      <figcaption><span><i className="violet" /> Active learners</span><span><i className="cyan" /> Submissions</span></figcaption>
      <svg viewBox="0 0 100 105" role="img" aria-label="Cohort activity trend">
        {[18, 36, 54, 72, 90].map((y) => <line key={y} x1="0" y1={y} x2="100" y2={y} className="chart-gridline" />)}
        <polyline points={coordinates('active_students')} className="chart-line chart-line--violet" />
        <polyline points={coordinates('submissions')} className="chart-line chart-line--cyan" />
        {points.map((point, index) => (
          <text key={point.label} x={points.length <= 1 ? 50 : (index / (points.length - 1)) * 100} y="103" textAnchor="middle">{point.label}</text>
        ))}
      </svg>
    </figure>
  )
}

function RadarChart({ values }: { values: NonNullable<EducatorDashboardData['concept_mastery']> }) {
  const center = 50
  const radius = 36
  const pointAt = (index: number, score = 100) => {
    const angle = -Math.PI / 2 + (index * Math.PI * 2) / values.length
    const scaled = radius * score / 100
    return {
      x: center + Math.cos(angle) * scaled,
      y: center + Math.sin(angle) * scaled,
    }
  }
  const polygon = values.map((item, index) => {
    const point = pointAt(index, item.score)
    return `${point.x},${point.y}`
  }).join(' ')

  if (values.length < 3) return <div className="inline-empty"><p>At least three assessed concepts are needed for a mastery radar.</p></div>
  return (
    <figure className="radar-chart">
      <svg viewBox="-8 -8 116 116" role="img" aria-label="Concept mastery radar">
        {[25, 50, 75, 100].map((score) => (
          <polygon key={score} points={values.map((_, index) => {
            const point = pointAt(index, score)
            return `${point.x},${point.y}`
          }).join(' ')} className="radar-grid" />
        ))}
        {values.map((item, index) => {
          const edge = pointAt(index)
          const label = pointAt(index, 127)
          return (
            <g key={item.label}>
              <line x1={center} y1={center} x2={edge.x} y2={edge.y} className="radar-axis" />
              <text x={label.x} y={label.y} textAnchor="middle">{item.label}</text>
            </g>
          )
        })}
        <polygon points={polygon} className="radar-value" />
        {values.map((item, index) => {
          const point = pointAt(index, item.score)
          return <circle key={item.label} cx={point.x} cy={point.y} r="1.7"><title>{item.label}: {item.score}%</title></circle>
        })}
      </svg>
    </figure>
  )
}

export function AnalyticsView() {
  const [data, setData] = useState<EducatorDashboardData | null>(null)
  const [error, setError] = useState('')

  const load = async (signal?: AbortSignal) => {
    try {
      setData(await api.educator.dashboard(signal))
      setError('')
    } catch (caught) {
      if (!signal?.aborted) setError(caught instanceof Error ? caught.message : 'Analytics could not be loaded.')
    }
  }

  useEffect(() => {
    const controller = new AbortController()
    async function loadInitialData() {
      try {
        setData(await api.educator.dashboard(controller.signal))
        setError('')
      } catch (caught) {
        if (!controller.signal.aborted) {
          setError(caught instanceof Error ? caught.message : 'Analytics could not be loaded.')
        }
      }
    }
    void loadInitialData()
    return () => controller.abort()
  }, [])

  const bestTaskType = useMemo(
    () => data?.task_type_performance?.reduce((best, item) => item.score > best.score ? item : best, { label: 'No data', score: 0 }),
    [data],
  )

  if (error) {
    return <div className="screen"><ScreenState kind="error" title="Analytics unavailable" message={error} action={<button className="button button--secondary" onClick={() => void load()}>Try again</button>} /></div>
  }
  if (!data) {
    return <div className="screen"><ScreenState kind="loading" title="Calculating cohort signals" message="Aggregating progress without exposing private student answers." /></div>
  }

  const performance = data.task_type_performance ?? []
  const mastery = data.concept_mastery ?? []
  const leaderboard = data.leaderboard ?? []

  return (
    <div className="screen">
      <PageHeading
        eyebrow="Privacy-aware analytics"
        title="Cohort analytics"
        description="Track engagement, activity performance and concept mastery across your authorised courses."
        actions={<span className="status-chip status-chip--cyan"><Icon name="analytics" size={15} /> Live aggregate</span>}
      />

      <section className="metric-grid metric-grid--three">
        <article className="metric-card">
          <span><Icon name="people" /></span><p>Enrolled learners</p><strong>{data.active_students}</strong><small>Current cohort</small>
        </article>
        <article className="metric-card">
          <span><Icon name="analytics" /></span><p>Average completion</p><strong>{data.average_completion}%</strong><small>Across course pathways</small>
        </article>
        <article className="metric-card">
          <span><Icon name="trophy" /></span><p>Strongest activity</p><strong className="metric-card__text">{bestTaskType?.label ?? 'No data'}</strong><small>{bestTaskType?.score ?? 0}% average</small>
        </article>
      </section>

      <div className="analytics-grid">
        <Panel eyebrow="Learning behaviour" title="Cohort trend" className="analytics-wide">
          <TrendChart points={data.engagement} />
        </Panel>

        <Panel eyebrow="Assessment formats" title="Task-type performance">
          {performance.length === 0 ? (
            <div className="inline-empty"><p>Task performance appears after submitted activities are scored.</p></div>
          ) : (
            <div className="performance-bars">
              {performance.map((item) => (
                <div key={item.label}>
                  <span>{item.label}</span>
                  <div><i style={{ width: `${item.score}%` }} /></div>
                  <strong>{item.score}%</strong>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel eyebrow="Learning outcomes" title="Concept mastery">
          <RadarChart values={mastery} />
        </Panel>

        <Panel eyebrow="Gamification" title="Leaderboard" className="analytics-wide">
          {leaderboard.length === 0 ? (
            <div className="inline-empty"><Icon name="trophy" /><p>The leaderboard starts after students earn their first points.</p></div>
          ) : (
            <ol className="leaderboard">
              {leaderboard.slice(0, 8).map((student, index) => (
                <li key={student.student_id}>
                  <span className={`rank rank--${index + 1}`}>{index + 1}</span>
                  <span className="avatar avatar--small">{student.display_name.split(' ').map((part) => part[0]).join('').slice(0, 2)}</span>
                  <div><strong>{student.display_name}</strong><small>{student.completed_tasks} activities completed</small></div>
                  <b>{student.points.toLocaleString()} XP</b>
                </li>
              ))}
            </ol>
          )}
        </Panel>
      </div>
    </div>
  )
}
