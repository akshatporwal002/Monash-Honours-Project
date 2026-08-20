import { useEffect, useMemo, useState } from 'react'
import { BarChart3, Trophy, Users } from 'lucide-react'

import { api } from '../app/api'
import type { EducatorDashboardData } from '../app/types'
import {
  BarList,
  Card,
  EmptyState,
  ErrorState,
  EstimateChip,
  LineChart,
  PageHeader,
  Skeleton,
  Tag,
} from './ui'
import styles from './AnalyticsView.module.css'

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
    return (
      <div className={styles.screen}>
        <ErrorState title="Analytics unavailable" description={error} onRetry={() => void load()} />
      </div>
    )
  }
  if (!data) {
    return (
      <div className={styles.screen}>
        <p role="status" className={styles.loading}>
          Calculating cohort signals: aggregating progress without exposing private student answers.
        </p>
        <Skeleton height="2.5rem" width="24rem" />
        <Skeleton height="9rem" />
        <Skeleton height="9rem" />
      </div>
    )
  }

  const performance = data.task_type_performance ?? []
  const mastery = data.concept_mastery ?? []
  const leaderboard = data.leaderboard ?? []

  const metrics = [
    { label: 'Enrolled learners', value: data.active_students, detail: 'Current cohort', icon: <Users size={18} /> },
    { label: 'Average completion', value: `${data.average_completion}%`, detail: 'Across course pathways', icon: <BarChart3 size={18} /> },
    { label: 'Strongest activity', value: bestTaskType?.label ?? 'No data', detail: `${bestTaskType?.score ?? 0}% average`, icon: <Trophy size={18} /> },
  ]

  return (
    <div className={styles.screen}>
      <PageHeader
        eyebrow="Privacy-aware analytics"
        title="Cohort analytics"
        description="Track engagement, activity performance and concept mastery across your authorised courses."
        actions={<Tag tone="accent">Live aggregate</Tag>}
      />

      <section className={styles.metrics} aria-label="Cohort metrics">
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
        <Card eyebrow="Learning behaviour" heading="Cohort trend" className={styles.wide}>
          {data.engagement.length === 0 ? (
            <EmptyState title="No cohort trend data is available for this period." />
          ) : (
            <LineChart
              title="Cohort activity trend"
              labels={data.engagement.map((point) => point.label)}
              series={[
                { label: 'Active learners', values: data.engagement.map((point) => point.active_students) },
                { label: 'Submissions', values: data.engagement.map((point) => point.submissions) },
              ]}
            />
          )}
        </Card>

        <Card eyebrow="Assessment formats" heading="Task-type performance">
          {performance.length === 0 ? (
            <EmptyState title="Task performance appears after submitted activities are scored." />
          ) : (
            <BarList
              max={100}
              items={performance.map((item) => ({
                label: item.label,
                value: item.score,
                display: `${item.score}%`,
              }))}
            />
          )}
        </Card>

        <Card eyebrow="Learning outcomes" heading="Concept mastery">
          {mastery.length === 0 ? (
            <EmptyState title="Concept estimates appear after assessed activities." />
          ) : (
            <ul className={styles.conceptList}>
              {mastery.map((item) => (
                <li key={item.label} className={styles.conceptRow}>
                  <span className={styles.conceptLabel}>{item.label}</span>
                  <EstimateChip uncertainty="Cohort estimate">{item.score}%</EstimateChip>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {/* Leaderboard behaviour is retained pending FR25 roadmap work (plan 006,
            Behaviour-preservation rule); presentation is a plain table with no
            rank celebration styling. */}
        <Card eyebrow="Gamification" heading="Leaderboard" className={styles.wide}>
          {leaderboard.length === 0 ? (
            <EmptyState
              icon={<Trophy size={20} />}
              title="The leaderboard starts after students earn their first points."
            />
          ) : (
            <div className={styles.tableScroll}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th scope="col">Rank</th>
                    <th scope="col">Student</th>
                    <th scope="col">Activities completed</th>
                    <th scope="col">Points</th>
                  </tr>
                </thead>
                <tbody>
                  {leaderboard.slice(0, 8).map((student, index) => (
                    <tr key={student.student_id}>
                      <td className={styles.rank}>{index + 1}</td>
                      <th scope="row" className={styles.studentCell}>{student.display_name}</th>
                      <td>{student.completed_tasks}</td>
                      <td className={styles.points}>{student.points.toLocaleString()} XP</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
