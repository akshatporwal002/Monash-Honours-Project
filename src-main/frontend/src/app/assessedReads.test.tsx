import { render, screen } from '@testing-library/react'
import { api } from './api'
import { StudentDashboard } from '../components/StudentDashboard'

const withheld = { result: null, visibility: 'withheld' }
const response = (body: unknown) => new Response(JSON.stringify(body), {
  headers: { 'Content-Type': 'application/json' },
})

afterEach(() => vi.restoreAllMocks())

test('dashboard has no numeric learner average', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(response({
    student: { id: 'student', display_name: 'Learner' },
    summary: { completed_tasks: 0, total_tasks: 0, completion_percentage: 0,
       points: 0, level: 1, next_level_points: 100 },
    tasks: [], recommendations: [], reminders: [], achievements: [], courses: [],
  }))
  const data = await api.student.dashboard()
  expect(data.progress).not.toHaveProperty('average_score')
  render(<StudentDashboard data={data} onOpenTask={vi.fn()} onReadNotification={vi.fn()} />)
  expect(screen.queryByText(/practice average/)).not.toBeInTheDocument()
})

test('educator activity keeps withheld formal results separate from practice participation', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(response({
    courses: [], total_students: 1, at_risk_students: 0, completion_percentage: 0,
    weekly_engagement: [],   leaderboard: [],
    recent_activity: [
      { student_name: 'Learner', task_title: 'Assessed task',  formal_assessment: withheld, occurred_at: '2026-09-06' },
      { student_name: 'Learner', task_title: 'Practice task',  formal_assessment: null, occurred_at: '2026-09-06' },
    ],
  }))
  const data = await api.educator.dashboard()
  expect(data.recent_activity[0].action).toContain('Formal result unavailable')
  expect(data.recent_activity[0].action).not.toMatch(/null%|0%/)
  expect(data.recent_activity[0].formal_assessment).toEqual(withheld)
  expect(data.recent_activity[1].action).toContain('Practice response submitted')
})

test('task normalization retains the explicit formal result marker', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(response({
    id: 'task',  latest_attempt: { formal_assessment: withheld },
  }))
  const task = await api.student.task('task')
  expect(task).not.toHaveProperty('score')
  expect(task.formal_assessment).toEqual(withheld)
})
