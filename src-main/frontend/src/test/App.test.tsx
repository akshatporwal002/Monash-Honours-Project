import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import axe from 'axe-core'
import App from '../App'
import type { LearningTask } from '../app/types'
import { TaskView } from '../components/TaskView'

function response(body: unknown, status = 200, headers?: HeadersInit): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
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

const rawStudentTask = {
  id: 'task-live',
  title: 'Open a live task',
  prompt: 'What does the Hadamard gate do?',
  instructions: 'Choose the best answer.',
  task_type: 'multiple_choice',
  difficulty: 'beginner',
  points: 100,
  position: 1,
  starter_code: null,
  due_at: null,
  course_id: 'course-1',
  module_id: 'module-1',
  module_title: 'Quantum foundations',
  learning_outcome_id: 'outcome-1',
  source_references: [],
  prerequisite_task_ids: [],
  choices: [
    { id: 'a', text: 'Measures the qubit' },
    { id: 'b', text: 'Creates a superposition' },
  ],
  access_status: 'available',
  attempt_count: 0,
  latest_score: null,
}

const studentDashboard = {
  student: { id: 'profile-1', display_name: 'Alex Student' },
  summary: {
    completed_tasks: 0,
    total_tasks: 1,
    completion_percentage: 0,
    average_score: 0,
    points: 0,
    level: 1,
    next_level_points: 500,
  },
  tasks: [rawStudentTask],
  recommendations: [{
    task_id: rawStudentTask.id,
    title: rawStudentTask.title,
    reason: 'Start with superposition.',
  }],
  reminders: [],
  achievements: [],
}

beforeEach(() => {
  vi.restoreAllMocks()
  document.cookie = 'ql_csrf=; Max-Age=0'
})

test('signs an educator into the server-authorised workspace with credentialed requests', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = String(input)
    if (url.endsWith('/auth/me')) return response({ detail: 'Not authenticated' }, 401)
    if (url.endsWith('/auth/login')) {
      document.cookie = 'ql_csrf=test-token'
      return response({
        id: 2,
        email: 'educator@example.edu',
        full_name: 'Dr Maya Chen',
        role: 'educator',
      })
    }
    if (url.endsWith('/educator/dashboard')) return response(educatorDashboard)
    if (url.endsWith('/educator/students')) return response([])
    if (url.endsWith('/educator/students')) return response([])
    throw new Error(`Unexpected request: ${url}`)
  })

  render(<App />)
  const user = userEvent.setup()
  expect(await screen.findByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /Educator/ }))
  await user.type(screen.getByLabelText('Email address'), 'educator@example.edu')
  await user.type(screen.getByLabelText('Password'), 'correct-password')
  await user.click(screen.getByRole('button', { name: /Enter educator workspace/ }))

  expect(await screen.findByRole('heading', { name: 'Learning pulse' })).toBeInTheDocument()
  const loginCall = fetchMock.mock.calls.find(([input]) => String(input).endsWith('/auth/login'))
  expect(loginCall?.[1]).toEqual(expect.objectContaining({ credentials: 'include' }))
  expect(new Headers(loginCall?.[1]?.headers).get('Content-Type')).toBe('application/json')
})

test('assessor navigation follows active server assignments', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = String(input)
    if (url.endsWith('/auth/me')) {
      return response({
        id: 2, email: 'educator@example.edu', full_name: 'Avery Educator', role: 'educator',
        scoped_assignments: [{ id: 'assignment-1', course_id: 'course-1', role: 'assessor', version: 1, valid_from: '2026-08-16T00:00:00Z', valid_until: null }],
      })
    }
    if (url.endsWith('/educator/dashboard')) return response(educatorDashboard)
    if (url.endsWith('/educator/students')) return response([])
    throw new Error(`Unexpected request: ${url}`)
  })

  render(<App />)
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: 'Assessment setup' }))
  expect(await screen.findByRole('heading', { name: 'Assessment setup' })).toBeInTheDocument()

  fetchMock.mockRestore()
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = String(input)
    if (url.endsWith('/auth/me')) return response({ id: 2, email: 'educator@example.edu', full_name: 'Avery Educator', role: 'educator', scoped_assignments: [] })
    if (url.endsWith('/educator/dashboard')) return response(educatorDashboard)
    throw new Error(`Unexpected request: ${url}`)
  })
  await user.click(screen.getByRole('button', { name: 'Check assessor access' }))
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Assessment setup' })).not.toBeInTheDocument())
  expect(screen.queryByRole('button', { name: 'Assessment setup' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Approve and publish' })).not.toBeInTheDocument()
})

test('maps the backend administrator role to the Admin workspace', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = String(input)
    if (url.endsWith('/auth/me')) {
      return response({
        id: 3,
        email: 'admin@example.edu',
        full_name: 'Platform Admin',
        role: 'administrator',
      })
    }
    if (url.endsWith('/admin/users')) return response([])
    if (url.endsWith('/courses')) return response([])
    if (url.endsWith('/admin/settings')) {
      return response({
        llm_provider: '',
        llm_model: '',
        at_risk_threshold: 50,
        reminders_enabled: true,
        passing_score: 70,
        points_per_level: 500,
      })
    }
    throw new Error(`Unexpected request: ${url}`)
  })

  render(<App />)
  expect(await screen.findByRole('heading', { name: 'System overview' })).toBeInTheDocument()
  expect(screen.getByText('admin workspace')).toBeInTheDocument()
})

test('opens dashboard tasks through the event-recording student task endpoint', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = String(input)
    if (url.endsWith('/auth/me')) {
      return response({
        id: 1,
        email: 'student@example.edu',
        full_name: 'Alex Student',
        role: 'student',
      })
    }
    if (url.endsWith('/students/me/dashboard')) return response(studentDashboard)
    if (url.endsWith('/students/me/tasks/task-live')) return response(rawStudentTask)
    if (url.endsWith('/students/me/tasks/task-live/draft')) return response(null)
    if (url.endsWith('/students/me/tasks/task-live/submissions')) return response([])
    throw new Error(`Unexpected request: ${url}`)
  })

  render(<App />)
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: 'Open Open a live task' }))

  expect(await screen.findByRole('heading', { name: 'Open a live task', level: 1 })).toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([input]) =>
    String(input).endsWith('/students/me/tasks/task-live'))).toBe(true)
})

test('shows a retryable error when the live task cannot be opened', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = String(input)
    if (url.endsWith('/auth/me')) {
      return response({
        id: 1,
        email: 'student@example.edu',
        full_name: 'Alex Student',
        role: 'student',
      })
    }
    if (url.endsWith('/students/me/dashboard')) return response(studentDashboard)
    if (url.endsWith('/students/me/tasks/task-live')) {
      return response({ detail: 'The activity is temporarily unavailable.' }, 503)
    }
    throw new Error(`Unexpected request: ${url}`)
  })

  render(<App />)
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: 'Open Open a live task' }))

  expect(await screen.findByRole('heading', { name: 'Activity unavailable' })).toBeInTheDocument()
  expect(screen.getByText('The activity is temporarily unavailable.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Try again' })).toBeEnabled()
})

test('loads a pre-seeded demo by logging in without calling loopback bootstrap', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = String(input)
    if (url.endsWith('/auth/me')) return response({ detail: 'Not authenticated' }, 401)
    if (url.endsWith('/auth/login')) {
      return response({
        id: 1,
        email: 'student@quantumlearn.demo',
        full_name: 'Alex Student',
        role: 'student',
      })
    }
    if (url.endsWith('/students/me/dashboard')) return response(studentDashboard)
    throw new Error(`Unexpected request: ${url}`)
  })

  render(<App />)
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: 'Load demo workspace' }))

  expect(await screen.findByRole('heading', { name: 'Welcome back, Alex' })).toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([input]) =>
    String(input).endsWith('/admin/bootstrap-demo'))).toBe(false)
})

test('uses loopback bootstrap only after the demo credentials return 401', async () => {
  let loginAttempts = 0
  const requestOrder: string[] = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = String(input)
    if (url.endsWith('/auth/me')) return response({ detail: 'Not authenticated' }, 401)
    if (url.endsWith('/auth/login')) {
      requestOrder.push('login')
      loginAttempts += 1
      if (loginAttempts === 1) return response({ detail: 'Invalid credentials' }, 401)
      return response({
        id: 1,
        email: 'student@quantumlearn.demo',
        full_name: 'Alex Student',
        role: 'student',
      })
    }
    if (url.endsWith('/admin/bootstrap-demo')) {
      requestOrder.push('bootstrap')
      return response({}, 201)
    }
    if (url.endsWith('/students/me/dashboard')) return response(studentDashboard)
    throw new Error(`Unexpected request: ${url}`)
  })

  render(<App />)
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: 'Load demo workspace' }))

  expect(await screen.findByRole('heading', { name: 'Welcome back, Alex' })).toBeInTheDocument()
  expect(requestOrder).toEqual(['login', 'bootstrap', 'login'])
})

test('submits an MCQ and renders only validated feedback from the feedback workflow', async () => {
  document.cookie = 'ql_csrf=feedback-token'
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input)
    const method = init?.method ?? 'GET'
    if (url.endsWith('/students/me/tasks/task-1/draft')) {
      return response(null)
    }
    if (url.endsWith('/students/me/tasks/task-1/submissions') && method === 'GET') {
      return response([])
    }
    if (url.endsWith('/students/me/tasks/task-1/submissions')) {
      return response({
        id: 'attempt-1',
        task_id: 'task-1',
        attempt_number: 1,
        status: 'completed',
        score: 100,
        feedback: 'pending',
        feedback_reference: 'attempt-1',
        points_awarded: 100,
        submitted_at: '2026-07-26T08:30:00Z',
      })
    }
    if (url.endsWith('/submissions/attempt-1/feedback')) {
      return response({
        workflow_run_id: 'workflow-1',
        submission_id: 'attempt-1',
        status: 'validated',
        processing_stage: null,
        feedback: {
          kind: 'validated',
          feedback_id: 'feedback-1',
          response_classification: 'correct',
          summary: 'The Hadamard gate creates an equal superposition.',
          identified_error: null,
          explanation: 'Measurement therefore has two equally likely outcomes.',
          improvement_actions: ['Connect the amplitudes to the measurement probabilities.'],
          recommended_next_step: 'Build the same state in the circuit activity.',
          sources: [{ source_id: 'source-1', label: 'Week 1 course notes' }],
          simulation_references: [],
          ai_generated_notice: 'AI-generated feedback validated against authorised course material.',
        },
        error: null,
      })
    }
    throw new Error(`Unexpected request: ${url}`)
  })

  const task: LearningTask = {
    id: 'task-1',
    title: 'Hadamard intuition',
    module: 'Module 1',
    description: 'What does a Hadamard gate do to |0⟩?',
    instructions: 'Choose the best answer.',
    task_type: 'multiple_choice',
    difficulty: 'beginner',
    points: 100,
    position: 1,
    status: 'in_progress',
    score: null,
    options: [
      { id: 'a', text: 'Creates an equal superposition' },
      { id: 'b', text: 'Measures immediately' },
    ],
  }
  const onSubmitted = vi.fn().mockResolvedValue(undefined)
  render(<TaskView task={task} onClose={() => undefined} onSubmitted={onSubmitted} />)
  const user = userEvent.setup()
  await user.click(await screen.findByRole('radio', { name: /Creates an equal superposition/ }))
  await user.click(screen.getByRole('button', { name: /Submit activity/ }))

  expect(await screen.findByText('The Hadamard gate creates an equal superposition.')).toBeInTheDocument()
  expect(screen.queryByText('pending')).not.toBeInTheDocument()
  expect(screen.getByText(/AI-generated feedback validated/)).toBeInTheDocument()
  await waitFor(() => expect(onSubmitted).toHaveBeenCalled())

  const submissionCall = fetchMock.mock.calls.find(([input, init]) =>
    String(input).endsWith('/students/me/tasks/task-1/submissions') && init?.method === 'POST')
  expect(new Headers(submissionCall?.[1]?.headers).get('X-CSRF-Token')).toBe('feedback-token')
  const feedbackCall = fetchMock.mock.calls.find(([input]) => String(input).endsWith('/submissions/attempt-1/feedback'))
  expect(feedbackCall?.[1]).toEqual(expect.objectContaining({ method: 'POST', credentials: 'include' }))
})

test('shows formal assessment conditions and saves a response without a numeric result', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input)
    if (url.endsWith('/draft')) return response(null)
    if ((init?.method ?? 'GET') === 'GET') return response([])
    return response({
      id: 'formal-attempt-1',
      status: 'submitted',
      score: null,
      feedback_reference: null,
    })
  })
  const task: LearningTask = {
    id: 'formal-task',
    title: 'Explain interference evidence',
    module: 'Module 2',
    description: 'Explain how the observed pattern supports the claim.',
    instructions: 'Use your own words.',
    task_type: 'short_answer',
    difficulty: 'intermediate',
    points: 0,
    position: 2,
    status: 'in_progress',
    score: null,
    assessment: {
      purpose: 'SUMMATIVE',
      bloom_process: 'ANALYSE',
      knowledge_dimension: 'CONCEPTUAL',
      claim: 'The learner can explain how the observed pattern supports the claim.',
      criteria: [{ description: 'Explain the evidence-to-claim relationship.', mandatory: true }],
      task_conditions: { response_mode: 'written' },
      permitted_tools: { allowed: ['notes'] },
      instructional_support: { maximum_level: 1 },
      access_conditions: { equivalent_modes: ['screen reader'] },
      transfer_rule: { required: true },
      review_rule: 'A formal result remains subject to assessor confirmation, correction, or override.',
    },
  }
  render(<TaskView task={task} onClose={() => undefined} onSubmitted={() => Promise.resolve()} />)
  const user = userEvent.setup()

  expect(await screen.findByText('Assessment conditions')).toBeInTheDocument()
  expect(screen.getByText(/Purpose: SUMMATIVE/)).toBeInTheDocument()
  expect(screen.getByText(/Required: Explain the evidence-to-claim relationship/)).toBeInTheDocument()
  expect(screen.getByText(/Permitted tools: notes/)).toBeInTheDocument()
  await user.type(screen.getByLabelText('Your response'), 'The evidence supports the claim.')
  await user.click(screen.getByRole('button', { name: /Submit activity/ }))

  expect(await screen.findByRole('heading', { name: 'Assessment response saved' })).toBeInTheDocument()
  const submissionCall = fetchMock.mock.calls.find(([input, init]) =>
    String(input).endsWith('/students/me/tasks/formal-task/submissions') && init?.method === 'POST')
  const payload = JSON.parse(String(submissionCall?.[1]?.body)) as { idempotency_key?: string }
  expect(payload.idempotency_key).toEqual(expect.any(String))
  expect(screen.queryByText('0%')).not.toBeInTheDocument()
})

test('submits multiple-answer choice identifiers as a JSON set', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input)
    if (url.endsWith('/draft')) return response(null)
    if ((init?.method ?? 'GET') === 'GET') return response([])
    return response({
        id: 'attempt-multi',
        status: 'completed',
        score: 100,
        feedback_reference: null,
      })
  })
  const task: LearningTask = {
    id: 'task-multi',
    title: 'Measurement facts',
    module: 'Module 2',
    description: 'Which statements about measurement are correct?',
    instructions: 'Select every correct answer.',
    task_type: 'multiple_answer',
    difficulty: 'intermediate',
    points: 120,
    position: 2,
    status: 'in_progress',
    score: null,
    options: [
      { id: 'a', text: 'Measurement produces a classical result.' },
      { id: 'b', text: 'Measurement preserves every amplitude.' },
      { id: 'c', text: 'Repeated shots estimate a distribution.' },
    ],
  }
  render(<TaskView task={task} onClose={() => undefined} onSubmitted={() => Promise.resolve()} />)
  const user = userEvent.setup()
  await user.click(await screen.findByRole('checkbox', { name: /produces a classical result/ }))
  await user.click(screen.getByRole('checkbox', { name: /estimate a distribution/ }))
  await user.click(screen.getByRole('button', { name: /Submit activity/ }))

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
  const submissionCall = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST')
  const payload = JSON.parse(String(submissionCall?.[1]?.body)) as { answer: string }
  expect(JSON.parse(payload.answer)).toEqual(['a', 'c'])
})

test('allows code-completion tasks to edit and submit Qiskit code', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input)
    if (url.endsWith('/draft')) return response(null)
    if ((init?.method ?? 'GET') === 'GET') return response([])
    return response({
        id: 'attempt-code',
        status: 'completed',
        score: 100,
        feedback_reference: null,
      })
  })
  const task: LearningTask = {
    id: 'task-code',
    title: 'Complete the circuit',
    module: 'Module 3',
    description: 'Add a Hadamard gate before measurement.',
    instructions: 'Edit the Qiskit program and submit it.',
    task_type: 'code_completion',
    difficulty: 'beginner',
    points: 100,
    position: 3,
    status: 'in_progress',
    score: null,
    starter_code: 'from qiskit import QuantumCircuit\n\ncircuit = QuantumCircuit(1, 1)',
  }
  render(<TaskView task={task} onClose={() => undefined} onSubmitted={() => Promise.resolve()} />)
  const user = userEvent.setup()
  const editor = await screen.findByLabelText('Qiskit code editor')
  await user.type(editor, '\ncircuit.h(0)')
  await user.click(screen.getByRole('button', { name: /Submit activity/ }))

  await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3))
  const submissionCall = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST')
  const payload = JSON.parse(String(submissionCall?.[1]?.body)) as { code: string }
  expect(payload.code).toContain('circuit.h(0)')
})

test('shows retained student attempt history and the latest existing feedback', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = String(input)
    if (url.endsWith('/draft')) return response(null)
    if (url.endsWith('/submissions/attempt-2/feedback')) {
      return response({
        workflow_run_id: 'workflow-2',
        submission_id: 'attempt-2',
        status: 'validated',
        processing_stage: null,
        feedback: {
          kind: 'validated',
          feedback_id: 'feedback-2',
          response_classification: 'partially_correct',
          summary: 'Review how relative phase changes interference.',
          identified_error: 'The phase relationship was omitted.',
          explanation: 'Relative phase controls constructive and destructive interference.',
          improvement_actions: ['Compare the amplitudes before measurement.'],
          recommended_next_step: 'Simulate both phase choices.',
          sources: [{ source_id: 'source-2', label: 'Interference notes' }],
          simulation_references: [],
          ai_generated_notice: 'AI-generated feedback validated against authorised course material.',
        },
        error: null,
      })
    }
    return response([
      {
        id: 'attempt-2',
        task_id: 'task-history',
        attempt_number: 2,
        status: 'completed',
        score: 90,
        feedback: 'Validated feedback',
        feedback_reference: 'attempt-2',
        points_awarded: 100,
        submitted_at: '2026-07-26T08:30:00Z',
      },
      {
        id: 'attempt-1',
        task_id: 'task-history',
        attempt_number: 1,
        status: 'submitted',
        score: 65,
        feedback: 'Validated feedback',
        feedback_reference: 'attempt-1',
        points_awarded: 0,
        submitted_at: '2026-07-25T08:30:00Z',
      },
    ])
  })
  const task: LearningTask = {
    id: 'task-history',
    title: 'Explain interference',
    module: 'Module 2',
    description: 'Explain constructive and destructive interference.',
    instructions: 'Use your own words.',
    task_type: 'short_answer',
    difficulty: 'intermediate',
    points: 100,
    position: 2,
    status: 'completed',
    score: 90,
  }

  render(<TaskView task={task} onClose={() => undefined} onSubmitted={() => Promise.resolve()} />)

  expect(await screen.findByText('2 attempts')).toBeInTheDocument()
  expect(screen.getByText('#2')).toBeInTheDocument()
  expect(screen.getByText('90%')).toBeInTheDocument()
  expect(screen.getByText('26 July 2026, 6:30 pm')).toBeInTheDocument()
  expect(screen.getByText('submitted')).toBeInTheDocument()
  expect(await screen.findByText('Review how relative phase changes interference.')).toBeInTheDocument()
  expect(fetchMock.mock.calls.some(([input]) =>
    String(input).endsWith('/submissions/attempt-2/feedback'))).toBe(true)
})

test('restores a saved MCQ selection', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) =>
    String(input).endsWith('/draft')
      ? response({
          id: 'draft-mcq',
          task_id: 'task-mcq-draft',
          answer: 'b',
          code: null,
          circuit: null,
          updated_at: '2026-07-26T08:00:00Z',
        })
      : response([]))
  const task: LearningTask = {
    id: 'task-mcq-draft',
    title: 'Saved measurement answer',
    module: 'Module 1',
    description: 'Choose an answer.',
    instructions: 'Select one.',
    task_type: 'multiple_choice',
    difficulty: 'beginner',
    points: 100,
    position: 1,
    status: 'in_progress',
    score: null,
    options: [
      { id: 'a', text: 'First answer' },
      { id: 'b', text: 'Saved answer' },
    ],
  }

  render(<TaskView task={task} onClose={() => undefined} onSubmitted={() => Promise.resolve()} />)

  expect(await screen.findByRole('radio', { name: /Saved answer/ })).toBeChecked()
  expect(screen.getByText('Saved draft restored.')).toBeInTheDocument()
})

test('restores saved multiple-answer identifiers', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) =>
    String(input).endsWith('/draft')
      ? response({
          id: 'draft-multiple',
          task_id: 'task-multiple-draft',
          answer: '["a","c"]',
          code: null,
          circuit: null,
          updated_at: '2026-07-26T08:00:00Z',
        })
      : response([]))
  const task: LearningTask = {
    id: 'task-multiple-draft',
    title: 'Saved measurement facts',
    module: 'Module 1',
    description: 'Choose every answer.',
    instructions: 'Select all that apply.',
    task_type: 'multiple_answer',
    difficulty: 'beginner',
    points: 100,
    position: 1,
    status: 'in_progress',
    score: null,
    options: [
      { id: 'a', text: 'Classical result' },
      { id: 'b', text: 'Every amplitude remains' },
      { id: 'c', text: 'Shots estimate a distribution' },
    ],
  }

  render(<TaskView task={task} onClose={() => undefined} onSubmitted={() => Promise.resolve()} />)

  expect(await screen.findByRole('checkbox', { name: /Classical result/ })).toBeChecked()
  expect(screen.getByRole('checkbox', { name: /Every amplitude remains/ })).not.toBeChecked()
  expect(screen.getByRole('checkbox', { name: /Shots estimate a distribution/ })).toBeChecked()
})

test('restores saved text and Qiskit code responses', async () => {
  const drafts = new Map([
    ['task-text-draft', {
      id: 'draft-text',
      task_id: 'task-text-draft',
      answer: 'A phase difference controls the interference pattern.',
      code: null,
      circuit: null,
      updated_at: '2026-07-26T08:00:00Z',
    }],
    ['task-code-draft', {
      id: 'draft-code',
      task_id: 'task-code-draft',
      answer: '',
      code: 'from qiskit import QuantumCircuit\ncircuit = QuantumCircuit(1)\ncircuit.h(0)',
      circuit: null,
      updated_at: '2026-07-26T08:00:00Z',
    }],
  ])
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = String(input)
    if (url.endsWith('/draft')) {
      const taskId = url.includes('task-text-draft') ? 'task-text-draft' : 'task-code-draft'
      return response(drafts.get(taskId))
    }
    return response([])
  })
  const textTask: LearningTask = {
    id: 'task-text-draft',
    title: 'Explain phase',
    module: 'Module 2',
    description: 'Explain interference.',
    instructions: 'Use your own words.',
    task_type: 'short_answer',
    difficulty: 'intermediate',
    points: 100,
    position: 1,
    status: 'in_progress',
    score: null,
  }
  const { unmount } = render(
    <TaskView task={textTask} onClose={() => undefined} onSubmitted={() => Promise.resolve()} />,
  )

  expect(await screen.findByDisplayValue(
    'A phase difference controls the interference pattern.',
  )).toBeInTheDocument()
  unmount()

  const codeTask: LearningTask = {
    ...textTask,
    id: 'task-code-draft',
    title: 'Complete the circuit',
    task_type: 'code_completion',
    starter_code: 'from qiskit import QuantumCircuit',
  }
  render(<TaskView task={codeTask} onClose={() => undefined} onSubmitted={() => Promise.resolve()} />)

  expect(await screen.findByLabelText('Qiskit code editor')).toHaveValue(
    'from qiskit import QuantumCircuit\ncircuit = QuantumCircuit(1)\ncircuit.h(0)',
  )
})

test('restores a saved quantum circuit', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) =>
    String(input).endsWith('/draft')
      ? response({
          id: 'draft-circuit',
          task_id: 'task-circuit-draft',
          answer: '',
          code: null,
          circuit: {
            qubits: 2,
            operations: [
              { gate: 'h', targets: [0] },
              { gate: 'cx', targets: [0, 1] },
            ],
          },
          updated_at: '2026-07-26T08:00:00Z',
        })
      : response([]))
  const task: LearningTask = {
    id: 'task-circuit-draft',
    title: 'Saved Bell circuit',
    module: 'Module 3',
    description: 'Build an entangled state.',
    instructions: 'Use H then CX.',
    task_type: 'quantum_circuit',
    difficulty: 'intermediate',
    points: 150,
    position: 1,
    status: 'in_progress',
    score: null,
  }

  render(<TaskView task={task} onClose={() => undefined} onSubmitted={() => Promise.resolve()} />)

  await screen.findByText('Saved draft restored.')
  expect(screen.getAllByTitle('Remove gate')).toHaveLength(3)
  expect(screen.getByRole('button', { name: 'Run 1,024 shots' })).toBeEnabled()
})

test('saves a circuit draft before a simulation fault', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input)
    if (url.endsWith('/draft') && (init?.method ?? 'GET') === 'GET') return response(null)
    if (url.endsWith('/draft')) return response({
      id: 'draft-simulation',
      task_id: 'task-simulation',
      answer: '',
      code: null,
      circuit: { qubits: 2, operations: [{ gate: 'h', targets: [0] }] },
      updated_at: '2026-08-16T08:00:00Z',
    })
    if (url.endsWith('/simulate')) return response({ detail: 'Simulator unavailable.' }, 503)
    return response([])
  })
  const task: LearningTask = {
    id: 'task-simulation',
    title: 'Check a circuit',
    module: 'Module 3',
    description: 'Build a circuit and inspect its result.',
    instructions: 'Add a gate, then run the simulator.',
    task_type: 'quantum_circuit',
    difficulty: 'intermediate',
    points: 100,
    position: 1,
    status: 'in_progress',
    score: null,
  }
  render(<TaskView task={task} onClose={() => undefined} onSubmitted={() => Promise.resolve()} />)
  const user = userEvent.setup()

  await user.click(await screen.findByRole('button', { name: 'Add H gate' }))
  await user.click(screen.getByRole('button', { name: 'Run 1,024 shots' }))

  await screen.findByText('Simulator unavailable.')
  const calls = fetchMock.mock.calls.map(([input, init]) => ({ url: String(input), init }))
  const draftIndex = calls.findIndex(({ url, init }) =>
    url.endsWith('/draft') && init?.method === 'PUT')
  const simulationIndex = calls.findIndex(({ url }) => url.endsWith('/simulate'))
  expect(draftIndex).toBeGreaterThanOrEqual(0)
  expect(simulationIndex).toBeGreaterThan(draftIndex)
  const draftPayload = JSON.parse(String(calls[draftIndex]?.init?.body)) as {
    circuit: { operations: Array<{ gate: string }> }
  }
  expect(draftPayload.circuit.operations).toEqual([{ gate: 'h', targets: [0] }])
})

test('has no detectable axe violations on the role selection and sign-in screen', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(response({ detail: 'Not authenticated' }, 401))
  const { container } = render(<App />)

  expect(await screen.findByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
  expect((await axe.run(container)).violations).toEqual([])
})
