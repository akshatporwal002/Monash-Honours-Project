import { render, screen } from '@testing-library/react'
import { api } from './api'
import { StudentDashboard } from '../components/StudentDashboard'

const withheld = { result: null, visibility: 'withheld' }
const response = (body: unknown) => new Response(JSON.stringify(body), {
  headers: { 'Content-Type': 'application/json' },
})

afterEach(() => vi.restoreAllMocks())

test.each([null, 0, 80])('dashboard preserves a practice average of %s', async (average) => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(response({
    student: { id: 'student', display_name: 'Learner' },
    summary: { completed_tasks: 0, total_tasks: 0, completion_percentage: 0,
      average_score: average, points: 0, level: 1, next_level_points: 100 },
    tasks: [], recommendations: [], reminders: [], achievements: [], courses: [],
  }))
  const data = await api.student.dashboard()
  expect(data.progress.average_score).toBe(average)
  render(<StudentDashboard data={data} onOpenTask={vi.fn()} onReadNotification={vi.fn()} />)
  if (average === null) expect(screen.queryByText(/practice average/)).not.toBeInTheDocument()
  else expect(screen.getByText(new RegExp(`${average}% practice average`))).toBeInTheDocument()
})

test('educator activity keeps withheld formal results separate from real zero scores', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(response({
    courses: [], total_students: 1, at_risk_students: 0, completion_percentage: 0,
    weekly_engagement: [], task_type_performance: [], concept_mastery: [], leaderboard: [],
    recent_activity: [
      { student_name: 'Learner', task_title: 'Assessed task', score: null, formal_assessment: withheld, occurred_at: '2026-09-06' },
      { student_name: 'Learner', task_title: 'Practice task', score: 0, formal_assessment: null, occurred_at: '2026-09-06' },
    ],
  }))
  const data = await api.educator.dashboard()
  expect(data.recent_activity[0].action).toContain('Formal result unavailable')
  expect(data.recent_activity[0].action).not.toMatch(/null%|0%/)
  expect(data.recent_activity[0].formal_assessment).toEqual(withheld)
  expect(data.recent_activity[1].action).toContain('0% practice')
})

test('task normalization retains the explicit formal result marker', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(response({
    id: 'task', latest_score: null, latest_attempt: { formal_assessment: withheld },
  }))
  const task = await api.student.task('task')
  expect(task.score).toBeNull()
  expect(task.formal_assessment).toEqual(withheld)
})
