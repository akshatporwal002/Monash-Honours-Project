import { useEffect, useMemo, useState } from 'react'
import { Send, Users } from 'lucide-react'

import { api } from '../app/api'
import type { EducatorStudent, StudentRisk } from '../app/types'
import {
  BarList,
  Button,
  Card,
  Checkbox,
  EmptyState,
  ErrorState,
  EstimateChip,
  PageHeader,
  SearchInput,
  Select,
  Skeleton,
} from './ui'
import styles from './StudentsView.module.css'

type StudentFilter = 'all' | StudentRisk

function riskFor(student: EducatorStudent): StudentRisk {
  if (student.risk) return student.risk
  if (student.completed_tasks === 0) return 'not_started'
  return student.completion_percent < 50 ? 'at_risk' : 'on_track'
}

const riskLabel: Record<StudentRisk, string> = {
  on_track: 'On track',
  at_risk: 'At risk',
  not_started: 'Not started',
}

function formatLastActive(value: string | null): string {
  if (!value) return 'No activity yet'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Recently'
  return date.toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' })
}

export function StudentsView() {
  const [students, setStudents] = useState<EducatorStudent[] | null>(null)
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<StudentFilter>('all')
  const [selected, setSelected] = useState<string[]>([])
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [sending, setSending] = useState(false)

  const load = async (signal?: AbortSignal) => {
    try {
      setStudents(await api.educator.students(signal))
      setError('')
    } catch (caught) {
      if (!signal?.aborted) setError(caught instanceof Error ? caught.message : 'Students could not be loaded.')
    }
  }

  useEffect(() => {
    const controller = new AbortController()
    async function loadInitialStudents() {
      try {
        setStudents(await api.educator.students(controller.signal))
        setError('')
      } catch (caught) {
        if (!controller.signal.aborted) {
          setError(caught instanceof Error ? caught.message : 'Students could not be loaded.')
        }
      }
    }
    void loadInitialStudents()
    return () => controller.abort()
  }, [])

  const filtered = useMemo(() => {
    if (!students) return []
    const normalizedQuery = query.trim().toLowerCase()
    return students.filter((student) => {
      const matchesQuery = !normalizedQuery
        || student.display_name.toLowerCase().includes(normalizedQuery)
        || student.email?.toLowerCase().includes(normalizedQuery)
        || student.course_title?.toLowerCase().includes(normalizedQuery)
      return matchesQuery && (filter === 'all' || riskFor(student) === filter)
    })
  }, [filter, query, students])

  const distribution = useMemo(() => {
    const total = Math.max(1, students?.length ?? 0)
    return (['on_track', 'at_risk', 'not_started'] as const).map((risk) => {
      const count = students?.filter((student) => riskFor(student) === risk).length ?? 0
      return { risk, count, percent: Math.round((count / total) * 100) }
    })
  }, [students])

  const toggleAll = () => {
    const visibleIds = filtered.map((student) => student.student_id)
    setSelected((current) => visibleIds.every((id) => current.includes(id))
      ? current.filter((id) => !visibleIds.includes(id))
      : Array.from(new Set([...current, ...visibleIds])))
  }

  const notify = async () => {
    if (selected.length === 0) return
    setSending(true)
    setNotice('')
    try {
      const result = await api.educator.notifyStudents(
        selected,
        'Your educator has shared a learning check-in. Open LearnLens to review your next recommended activity.',
      )
      setNotice(`${result.sent} notification${result.sent === 1 ? '' : 's'} sent.`)
      setSelected([])
    } catch (caught) {
      setNotice(caught instanceof Error ? caught.message : 'Notifications could not be sent.')
    } finally {
      setSending(false)
    }
  }

  if (error) {
    return (
      <div className={styles.screen}>
        <ErrorState title="Student view unavailable" description={error} onRetry={() => void load()} />
      </div>
    )
  }
  if (!students) {
    return (
      <div className={styles.screen}>
        <p role="status" className={styles.loading}>
          Loading students: building the latest progress view for your courses.
        </p>
        <Skeleton height="2.5rem" width="24rem" />
        <Skeleton height="9rem" />
        <Skeleton height="14rem" />
      </div>
    )
  }

  return (
    <div className={styles.screen}>
      <PageHeader
        eyebrow="Student support"
        title="Students"
        description="Find learners quickly, compare progress and send a timely check-in."
        actions={
          <div className={styles.headerActions}>
            <Button
              variant="primary"
              onClick={() => void notify()}
              disabled={selected.length === 0}
              loading={sending}
            >
              <Send size={16} aria-hidden="true" />
              {`Notify selected${selected.length ? ` (${selected.length})` : ''}`}
            </Button>
            {selected.length === 0 && (
              <span className={styles.actionHint}>Select students below to enable notifications.</span>
            )}
          </div>
        }
      />

      <Card eyebrow="Current standing" heading="Cohort distribution">
        <BarList
          max={100}
          items={distribution.map(({ risk, count, percent }) => ({
            label: riskLabel[risk],
            value: percent,
            display: `${count} (${percent}%)`,
          }))}
        />
      </Card>

      <Card padding="none" className={styles.tablePanel} aria-labelledby="student-table-title">
        <header className={styles.toolbar}>
          <div>
            <p className={styles.eyebrow}>Enrolment</p>
            <h2 id="student-table-title" className={styles.tableTitle}>{students.length} students</h2>
          </div>
          <div className={styles.controls}>
            <SearchInput
              label="Search students"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search name, email or course"
              className={styles.search}
            />
            <Select
              aria-label="Filter by progress state"
              value={filter}
              onValueChange={(value) => setFilter(value as StudentFilter)}
              options={[
                { value: 'all', label: 'All students' },
                { value: 'on_track', label: 'On track' },
                { value: 'at_risk', label: 'At risk' },
                { value: 'not_started', label: 'Not started' },
              ]}
            />
          </div>
        </header>
        {notice && <p className={styles.notice} role="status">{notice}</p>}
        {filtered.length === 0 ? (
          <EmptyState
            icon={<Users size={20} />}
            title="No students match this search and filter."
            className={styles.empty}
          />
        ) : (
          <div className={styles.tableScroll}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th scope="col" className={styles.selectCell}>
                    <Checkbox
                      label=""
                      aria-label="Select all visible students"
                      checked={filtered.every((student) => selected.includes(student.student_id))}
                      onChange={toggleAll}
                    />
                  </th>
                  <th scope="col">Student</th>
                  <th scope="col">Course</th>
                  <th scope="col">Progress</th>
                  <th scope="col">Average</th>
                  <th scope="col">Last active</th>
                  <th scope="col">Status</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((student) => {
                  const risk = riskFor(student)
                  return (
                    <tr key={student.student_id}>
                      <td className={styles.selectCell}>
                        <Checkbox
                          label=""
                          aria-label={`Select ${student.display_name}`}
                          checked={selected.includes(student.student_id)}
                          onChange={() => setSelected((current) => current.includes(student.student_id)
                            ? current.filter((id) => id !== student.student_id)
                            : [...current, student.student_id])}
                        />
                      </td>
                      <th scope="row" className={styles.studentCell}>
                        <strong className={styles.studentName}>{student.display_name}</strong>
                        <small className={styles.studentEmail}>{student.email}</small>
                      </th>
                      <td>{student.course_title || 'All courses'}</td>
                      <td>
                        <div className={styles.progress}>
                          <span className={styles.progressTrack} aria-hidden="true">
                            <span style={{ width: `${student.completion_percent}%` }} />
                          </span>
                          <strong className={styles.progressValue}>{student.completion_percent}%</strong>
                        </div>
                        <small className={styles.progressDetail}>
                          {student.completed_tasks}/{student.total_tasks} activities
                        </small>
                      </td>
                      <td>
                        <strong className={styles.average}>
                          {student.completed_tasks ? `${student.average_score}%` : '—'}
                        </strong>
                      </td>
                      <td>{formatLastActive(student.last_active)}</td>
                      <td>
                        <EstimateChip uncertainty="Estimate from completion activity">
                          {riskLabel[risk]}
                        </EstimateChip>
                        {Boolean(student.overdue_tasks) && (
                          <small className={styles.overdue}>{student.overdue_tasks} overdue</small>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
