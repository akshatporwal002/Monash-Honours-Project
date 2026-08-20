import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  BookOpen,
  CheckCircle2,
  Plus,
  Users,
} from 'lucide-react'

import { api } from '../app/api'
import type { EducatorDashboardData, EducatorStudent } from '../app/types'
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  EstimateChip,
  LineChart,
  PageHeader,
  Skeleton,
} from './ui'
import styles from './EducatorDashboard.module.css'

function activityTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Recently'
  const minutes = Math.max(0, Math.round((Date.now() - date.getTime()) / 60_000))
  if (minutes < 1) return 'Just now'
  if (minutes < 60) return `${minutes}m ago`
  if (minutes < 1_440) return `${Math.floor(minutes / 60)}h ago`
  return `${Math.floor(minutes / 1_440)}d ago`
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
      <div className={styles.screen}>
        <ErrorState
          title="Educator dashboard unavailable"
          description={error}
          onRetry={() => void load()}
        />
      </div>
    )
  }
  if (!dashboard) {
    return (
      <div className={styles.screen}>
        <p role="status" className={styles.loading}>
          Preparing your course view: loading engagement, student support and course progress.
        </p>
        <Skeleton height="2.5rem" width="24rem" />
        <Skeleton height="9rem" />
        <Skeleton height="9rem" />
      </div>
    )
  }

  const metrics = [
    { label: 'Enrolled students', value: dashboard.active_students, detail: 'Across your courses', icon: <Users size={18} /> },
    { label: 'Average completion', value: `${dashboard.average_completion}%`, detail: 'All published pathways', icon: <BarChart3 size={18} /> },
    { label: 'Submissions this week', value: dashboard.submissions_this_week, detail: 'Learning attempts', icon: <BookOpen size={18} /> },
    { label: 'Need support', value: dashboard.at_risk_count, detail: 'Based on engagement', icon: <AlertTriangle size={18} /> },
  ]

  return (
    <div className={styles.screen}>
      <PageHeader
        eyebrow="Educator dashboard"
        title="Learning pulse"
        description="See what changed this week, then act on the signals that matter."
        actions={
          <Button variant="primary" onClick={onCreateCourse}>
            <Plus size={16} aria-hidden="true" /> Create course
          </Button>
        }
      />

      <section className={styles.metrics} aria-label="Course metrics">
        {metrics.map((metric) => (
          <Card key={metric.label} className={styles.metric}>
            <span className={styles.metricIcon} aria-hidden="true">{metric.icon}</span>
            <p className={styles.metricLabel}>{metric.label}</p>
            <p className={styles.metricValue}>{metric.value}</p>
            <p className={styles.metricDetail}>{metric.detail}</p>
          </Card>
        ))}
      </section>

      <div className={styles.grid}>
        <Card eyebrow="Last seven days" heading="Weekly engagement" className={styles.engagementPanel}>
          {dashboard.engagement.length === 0 ? (
            <EmptyState title="Engagement appears after students start learning activities." />
          ) : (
            <LineChart
              title="Weekly active students and submissions"
              labels={dashboard.engagement.map((point) => point.label)}
              series={[
                { label: 'Active students', values: dashboard.engagement.map((point) => point.active_students) },
                { label: 'Submissions', values: dashboard.engagement.map((point) => point.submissions) },
              ]}
            />
          )}
        </Card>

        <Card
          eyebrow="Early support"
          heading="At-risk alerts"
          className={styles.riskPanel}
          actions={
            <Button variant="quiet" size="sm" onClick={onViewStudents}>
              View all <ArrowRight size={14} aria-hidden="true" />
            </Button>
          }
        >
          {atRisk.length === 0 ? (
            <EmptyState
              icon={<CheckCircle2 size={20} />}
              title="No students currently meet the at-risk threshold."
            />
          ) : (
            <ul className={styles.riskList}>
              {atRisk.map((student) => (
                <li key={student.student_id} className={styles.riskRow}>
                  <div className={styles.riskBody}>
                    <p className={styles.riskName}>{student.display_name}</p>
                    <p className={styles.riskDetail}>
                      {student.completion_percent}% complete · {student.average_score}% average
                    </p>
                    <EstimateChip uncertainty="Estimate from completion activity">
                      At risk
                    </EstimateChip>
                  </div>
                  <Button variant="secondary" size="sm" onClick={() => void notify(student)}>
                    Check in
                  </Button>
                </li>
              ))}
            </ul>
          )}
          {notice && <p className={styles.notice} role="status">{notice}</p>}
        </Card>
      </div>

      <div className={styles.grid}>
        <Card eyebrow="Live course signal" heading="Recent activity">
          {dashboard.recent_activity.length === 0 ? (
            <EmptyState title="New submissions and milestones will appear here." />
          ) : (
            <ol className={styles.timeline}>
              {dashboard.recent_activity.slice(0, 6).map((item) => (
                <li key={item.id} className={styles.timelineItem}>
                  <span className={styles.timelineDot} aria-hidden="true" />
                  <div className={styles.timelineBody}>
                    <p className={styles.timelineActor}>{item.actor}</p>
                    <p className={styles.timelineAction}>{item.action}</p>
                  </div>
                  <time dateTime={item.occurred_at} className={styles.timelineTime}>
                    {activityTime(item.occurred_at)}
                  </time>
                </li>
              ))}
            </ol>
          )}
        </Card>

        <Card eyebrow="Published learning" heading="Course progress">
          {dashboard.courses.length === 0 ? (
            <EmptyState
              icon={<BookOpen size={20} />}
              title="Create your first course to begin building a pathway."
            />
          ) : (
            <ul className={styles.courseList}>
              {dashboard.courses.slice(0, 5).map((course) => (
                <li key={course.id} className={styles.courseRow}>
                  <div className={styles.courseText}>
                    <p className={styles.courseCode}>{course.code}</p>
                    <p className={styles.courseTitle}>{course.title}</p>
                    <p className={styles.courseMeta}>{course.enrolled_students ?? 0} students</p>
                  </div>
                  <span className={styles.courseTrack} aria-hidden="true">
                    <span style={{ width: `${course.completion_percent ?? 0}%` }} />
                  </span>
                  <span className={styles.courseValue}>{course.completion_percent ?? 0}%</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  )
}
