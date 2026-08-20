import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../App'

function response(body: unknown, status = 200): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

const educatorDashboard = {
  courses: [],
  total_students: 0,
  at_risk_students: 0,
  completion_percentage: 0,
  weekly_engagement: [],
  task_type_performance: [],
  concept_mastery: [],
  leaderboard: [],
  recent_activity: [],
}

const studentDashboard = {
  student: { id: 'profile-1', display_name: 'Alex Student' },
  summary: {
    completed_tasks: 0,
    total_tasks: 0,
    completion_percentage: 0,
    average_score: 0,
    points: 0,
    level: 1,
    next_level_points: 500,
  },
  tasks: [],
  recommendations: [],
  reminders: [],
  achievements: [],
}

function mockStudentSession() {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = String(input)
    if (url.endsWith('/auth/me')) {
      return response({ id: 1, email: 'student@example.edu', full_name: 'Alex Student', role: 'student' })
    }
    if (url.endsWith('/students/me/dashboard')) return response(studentDashboard)
    throw new Error(`Unexpected request: ${url}`)
  })
}

function mockEducatorSession(withAssessor = false) {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = String(input)
    if (url.endsWith('/auth/me')) {
      return response({
        id: 2,
        email: 'educator@example.edu',
        full_name: 'Avery Educator',
        role: 'educator',
        scoped_assignments: withAssessor
          ? [{ id: 'assignment-1', course_id: 'course-1', role: 'assessor', version: 1, valid_from: '2026-08-16T00:00:00Z', valid_until: null }]
          : [],
      })
    }
    if (url.endsWith('/educator/dashboard')) return response(educatorDashboard)
    if (url.endsWith('/educator/students')) return response([])
    if (url.includes('/assessment/courses/course-1/review-queue')) return response([])
    throw new Error(`Unexpected request: ${url}`)
  })
}

beforeEach(() => {
  vi.restoreAllMocks()
  window.history.pushState({}, '', '/')
})

test('a student visiting an admin URL sees not-found, identical to an unknown URL', async () => {
  mockStudentSession()
  window.history.pushState({}, '', '/admin')
  render(<App />)
  expect(await screen.findByRole('heading', { name: /not available to your account/ })).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'System overview' })).not.toBeInTheDocument()
})

test('an unknown URL renders the same not-found page', async () => {
  mockEducatorSession()
  window.history.pushState({}, '', '/definitely/not/a/page')
  render(<App />)
  expect(await screen.findByRole('heading', { name: /not available to your account/ })).toBeInTheDocument()
})

test('a deep link into the assessor review queue works with an active assignment', async () => {
  mockEducatorSession(true)
  window.history.pushState({}, '', '/assessor/review')
  render(<App />)
  expect(await screen.findByRole('heading', { name: 'Assessment review queue' })).toBeInTheDocument()
})

test('the same assessor URL without an assignment renders not-found', async () => {
  mockEducatorSession(false)
  window.history.pushState({}, '', '/assessor/review')
  render(<App />)
  expect(await screen.findByRole('heading', { name: /not available to your account/ })).toBeInTheDocument()
})

test('browser back returns to the previous screen', async () => {
  mockEducatorSession()
  render(<App />)
  const user = userEvent.setup()
  expect(await screen.findByRole('heading', { name: 'Learning pulse' })).toBeInTheDocument()
  await user.click(screen.getByRole('link', { name: 'Students' }))
  expect(await screen.findByRole('heading', { name: 'Students' })).toBeInTheDocument()
  window.history.back()
  await waitFor(() => expect(screen.getByRole('heading', { name: 'Learning pulse' })).toBeInTheDocument())
  expect(window.location.pathname).toBe('/educator')
})

test('the root URL resolves to the signed-in role home', async () => {
  mockStudentSession()
  render(<App />)
  await waitFor(() => expect(window.location.pathname).toBe('/student'))
})
