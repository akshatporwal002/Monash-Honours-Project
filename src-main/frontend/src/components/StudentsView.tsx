import { useEffect, useMemo, useState } from 'react'
import { api } from '../app/api'
import type { EducatorStudent, StudentRisk } from '../app/types'
import { Icon, PageHeading, Panel, ScreenState } from './ScreenPrimitives'

type StudentFilter = 'all' | StudentRisk

function riskFor(student: EducatorStudent): StudentRisk {
  if (student.risk) return student.risk
  if (student.completed_tasks === 0) return 'not_started'
  return student.completion_percent < 50 ? 'at_risk' : 'on_track'
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
        'Your educator has shared a learning check-in. Open QuantumLearn to review your next recommended activity.',
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
    return <div className="screen"><ScreenState kind="error" title="Student view unavailable" message={error} action={<button className="button button--secondary" onClick={() => void load()}>Try again</button>} /></div>
  }
  if (!students) {
    return <div className="screen"><ScreenState kind="loading" title="Loading students" message="Building the latest progress view for your courses." /></div>
  }

  return (
    <div className="screen">
      <PageHeading
        eyebrow="Student support"
        title="Students"
        description="Find learners quickly, compare progress and send a timely check-in."
        actions={
          <button className="button button--primary" onClick={() => void notify()} disabled={selected.length === 0 || sending}>
            <Icon name="people" size={18} /> {sending ? 'Sending…' : `Notify selected${selected.length ? ` (${selected.length})` : ''}`}
          </button>
        }
      />

      <Panel title="Cohort distribution" eyebrow="Current standing">
        <div className="distribution-chart" role="img" aria-label="Student progress distribution">
          {distribution.map(({ risk, count, percent }) => (
            <div key={risk}>
              <span>{risk === 'on_track' ? 'On track' : risk === 'at_risk' ? 'At risk' : 'Not started'}</span>
              <div><i className={`distribution-${risk}`} style={{ width: `${percent}%` }} /></div>
              <strong>{count} <small>({percent}%)</small></strong>
            </div>
          ))}
        </div>
      </Panel>

      <section className="table-panel" aria-labelledby="student-table-title">
        <header className="table-toolbar">
          <div>
            <p className="eyebrow">Enrolment</p>
            <h2 id="student-table-title">{students.length} students</h2>
          </div>
          <div className="table-controls">
            <label className="search-field">
              <span className="sr-only">Search students</span>
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search name, email or course" />
            </label>
            <label>
              <span className="sr-only">Filter by progress state</span>
              <select value={filter} onChange={(event) => setFilter(event.target.value as StudentFilter)}>
                <option value="all">All students</option>
                <option value="on_track">On track</option>
                <option value="at_risk">At risk</option>
                <option value="not_started">Not started</option>
              </select>
            </label>
          </div>
        </header>
        {notice && <p className="form-status table-notice" role="status">{notice}</p>}
        {filtered.length === 0 ? (
          <div className="inline-empty table-empty"><Icon name="people" /><p>No students match this search and filter.</p></div>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>
                    <input
                      type="checkbox"
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
                      <td><input type="checkbox" aria-label={`Select ${student.display_name}`} checked={selected.includes(student.student_id)} onChange={() => setSelected((current) => current.includes(student.student_id) ? current.filter((id) => id !== student.student_id) : [...current, student.student_id])} /></td>
                      <th scope="row"><strong>{student.display_name}</strong><small>{student.email}</small></th>
                      <td>{student.course_title || 'All courses'}</td>
                      <td>
                        <div className="table-progress"><span><i style={{ width: `${student.completion_percent}%` }} /></span><strong>{student.completion_percent}%</strong></div>
                        <small>{student.completed_tasks}/{student.total_tasks} activities</small>
                      </td>
                      <td><strong>{student.completed_tasks ? `${student.average_score}%` : '—'}</strong></td>
                      <td>{formatLastActive(student.last_active)}</td>
                      <td><span className={`risk-badge risk-badge--${risk}`}>{risk === 'on_track' ? 'On track' : risk === 'at_risk' ? 'At risk' : 'Not started'}</span>{Boolean(student.overdue_tasks) && <small>{student.overdue_tasks} overdue</small>}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
