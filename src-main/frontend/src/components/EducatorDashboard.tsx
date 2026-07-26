import { useEffect, useMemo, useState } from 'react'
import { api } from '../app/api'
import type { EducatorDashboardData, EducatorStudent } from '../app/types'
import { Icon, PageHeading, Panel, ScreenState } from './ScreenPrimitives'

function activityTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Recently'
  const minutes = Math.max(0, Math.round((Date.now() - date.getTime()) / 60_000))
  if (minutes < 1) return 'Just now'
  if (minutes < 60) return `${minutes}m ago`
  if (minutes < 1_440) return `${Math.floor(minutes / 60)}h ago`
  return `${Math.floor(minutes / 1_440)}d ago`
}

function WeeklyChart({ points }: { points: EducatorDashboardData['engagement'] }) {
  const maximum = Math.max(1, ...points.flatMap((point) => [point.active_students, point.submissions]))
  const makePoints = (key: 'active_students' | 'submissions') =>
    points.map((point, index) => {
      const x = points.length === 1 ? 50 : (index / (points.length - 1)) * 100
      const y = 94 - (point[key] / maximum) * 80
      return `${x},${y}`
    }).join(' ')

  if (points.length === 0) {
    return <div className="inline-empty"><p>Engagement appears after students start learning activities.</p></div>
  }

  return (
    <figure className="line-chart" aria-label="Weekly active students and submissions">
      <div className="chart-legend"><span><i className="violet" /> Active students</span><span><i className="cyan" /> Submissions</span></div>
      <svg viewBox="0 0 100 100" role="img">
        <title>Weekly engagement</title>
        {[20, 40, 60, 80].map((line) => <line key={line} x1="0" y1={line} x2="100" y2={line} className="chart-gridline" />)}
        <polyline points={makePoints('active_students')} className="chart-line chart-line--violet" />
        <polyline points={makePoints('submissions')} className="chart-line chart-line--cyan" />
        {points.map((point, index) => {
          const x = points.length === 1 ? 50 : (index / (points.length - 1)) * 100
          return <text key={point.label} x={x} y="99" textAnchor="middle">{point.label}</text>
        })}
      </svg>
    </figure>
  )
}

export function EducatorDashboard({ onCreateCourse, onViewStudents }: {
  onCreateCourse: () => void
  onViewStudents: () => void
}) {
  const [dashboard, setDashboard] = useState<EducatorDashboardData | null>(null)
  const [students, setStudents] = useState<EducatorStudent[]>([])
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const load = async (signal?: AbortSignal) => {
    try {
      const [dashboardData, studentData] = await Promise.all([
        api.educator.dashboard(signal),
        api.educator.students(signal),
      ])
      setDashboard(dashboardData)
      setStudents(studentData)
      setError('')
    } catch (caught) {
      if (signal?.aborted) return
      setError(caught instanceof Error ? caught.message : 'The educator dashboard is unavailable.')
    }
  }

  useEffect(() => {
    const controller = new AbortController()
    async function loadInitialData() {
      try {
        const [dashboardData, studentData] = await Promise.all([
          api.educator.dashboard(controller.signal),
          api.educator.students(controller.signal),
        ])
        setDashboard(dashboardData)
        setStudents(studentData)
        setError('')
      } catch (caught) {
        if (!controller.signal.aborted) {
          setError(caught instanceof Error ? caught.message : 'The educator dashboard is unavailable.')
        }
      }
    }
    void loadInitialData()
    return () => controller.abort()
  }, [])

  const atRisk = useMemo(
    () => students.filter((student) => student.risk === 'at_risk').slice(0, 4),
    [students],
  )

  const notify = async (student: EducatorStudent) => {
    setNotice('')
    try {
      await api.educator.notifyStudents(
        [student.student_id],
        'A quick check-in from your educator: review your recommended activity when you can.',
      )
      setNotice(`Check-in sent to ${student.display_name}.`)
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : 'The check-in could not be sent.')
    }
  }

  if (error) {
    return (
      <div className="screen">
        <ScreenState
          kind="error"
          title="Educator dashboard unavailable"
          message={error}
          action={<button className="button button--secondary" onClick={() => void load()}>Try again</button>}
        />
      </div>
    )
  }
  if (!dashboard) {
    return <div className="screen"><ScreenState kind="loading" title="Preparing your course view" message="Loading engagement, student support and course progress." /></div>
  }

  return (
    <div className="screen">
      <PageHeading
        eyebrow="Educator dashboard"
        title="Learning pulse"
        description="See what changed this week, then act on the signals that matter."
        actions={<button className="button button--primary" onClick={onCreateCourse}><Icon name="course" size={18} /> Create course</button>}
      />

      <section className="metric-grid">
        {[
          ['Enrolled students', dashboard.active_students, 'Across your courses'],
          ['Average completion', `${dashboard.average_completion}%`, 'All published pathways'],
          ['Submissions this week', dashboard.submissions_this_week, 'Learning attempts'],
          ['Need support', dashboard.at_risk_count, 'Based on engagement'],
        ].map(([label, value, detail], index) => (
          <article className={index === 3 && Number(value) > 0 ? 'metric-card metric-card--warning' : 'metric-card'} key={label}>
            <span><Icon name={index === 3 ? 'warning' : index === 2 ? 'book' : index === 1 ? 'analytics' : 'people'} /></span>
            <p>{label}</p>
            <strong>{value}</strong>
            <small>{detail}</small>
          </article>
        ))}
      </section>

      <div className="educator-grid">
        <Panel eyebrow="Last seven days" title="Weekly engagement" className="engagement-panel">
          <WeeklyChart points={dashboard.engagement} />
        </Panel>

        <Panel
          eyebrow="Early support"
          title="At-risk alerts"
          className="risk-panel"
          action={<button className="text-button" onClick={onViewStudents}>View all <Icon name="arrow" size={15} /></button>}
        >
          {atRisk.length === 0 ? (
            <div className="inline-empty"><Icon name="check" /><p>No students currently meet the at-risk threshold.</p></div>
          ) : (
            <div className="risk-list">
              {atRisk.map((student) => (
                <article key={student.student_id}>
                  <span className="avatar avatar--small">{student.display_name.split(' ').map((part) => part[0]).join('').slice(0, 2)}</span>
                  <div><strong>{student.display_name}</strong><small>{student.completion_percent}% complete · {student.average_score}% average</small></div>
                  <button className="button button--ghost" onClick={() => void notify(student)}>Check in</button>
                </article>
              ))}
            </div>
          )}
          {notice && <p className="form-status" role="status">{notice}</p>}
        </Panel>
      </div>

      <div className="educator-lower-grid">
        <Panel eyebrow="Live course signal" title="Recent activity">
          {dashboard.recent_activity.length === 0 ? (
            <div className="inline-empty"><p>New submissions and milestones will appear here.</p></div>
          ) : (
            <ol className="activity-feed">
              {dashboard.recent_activity.slice(0, 6).map((item) => (
                <li key={item.id}>
                  <i />
                  <div><strong>{item.actor}</strong><p>{item.action}</p></div>
                  <time dateTime={item.occurred_at}>{activityTime(item.occurred_at)}</time>
                </li>
              ))}
            </ol>
          )}
        </Panel>

        <Panel eyebrow="Published learning" title="Course progress">
          {dashboard.courses.length === 0 ? (
            <div className="inline-empty"><Icon name="course" /><p>Create your first course to begin building a pathway.</p></div>
          ) : (
            <div className="course-progress-list">
              {dashboard.courses.slice(0, 5).map((course) => (
                <article key={course.id}>
                  <div><span>{course.code}</span><strong>{course.title}</strong><small>{course.enrolled_students ?? 0} students</small></div>
                  <div className="meter"><i style={{ width: `${course.completion_percent ?? 0}%` }} /></div>
                  <b>{course.completion_percent ?? 0}%</b>
                </article>
              ))}
            </div>
          )}
        </Panel>
      </div>
    </div>
  )
}
