import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { TaskPage } from '../components/TaskPage'

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

function renderPage() {
  return render(<MemoryRouter initialEntries={['/student/tasks/task-1']}>
    <Routes><Route path="/student/tasks/:taskId" element={<TaskPage onSubmitted={async () => {}} />} /></Routes>
  </MemoryRouter>)
}

test('withdrawn activities preserve read-only saved work without exposing provisional results', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = String(input)
    if (url.endsWith('/tasks/task-1')) return response({ detail: 'This task needs a new educator review' }, 409)
    if (url.endsWith('/draft')) return response({
      id: 'draft-1', task_id: 'task-1', answer: 'My saved draft response', code: null,
      circuit: { qubits: 1, operations: [{ gate: 'h', targets: [0] }] }, updated_at: '2026-09-07T01:00:00Z',
    })
    if (url.endsWith('/submissions')) return response([{
      id: 'attempt-1', attempt_number: 1, answer: 'My earlier submitted answer',
      score: null, formal_assessment: { result: 'PASS', result_state: 'PROVISIONAL' },
      feedback: 'Recorded for review', status: 'submitted', submitted_at: '2026-09-07T01:00:00Z',
    }])
    throw new Error(`Unexpected request: ${url}`)
  })
  renderPage()
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: 'View saved work' }))
  expect(await screen.findByText('My saved draft response')).toBeVisible()
  expect(screen.getByText('My earlier submitted answer')).toBeVisible()
  expect(screen.getByText('H on qubit 0')).toBeVisible()
  expect(screen.queryByText('PASS')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Submit|Save draft/ })).not.toBeInTheDocument()
  expect(fetchMock.mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true)
})

test('course access denial does not offer or fetch saved activity records', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockClear().mockResolvedValue(response({ detail: 'Access denied' }, 403))
  renderPage()
  expect(await screen.findByText('Access denied')).toBeVisible()
  expect(screen.queryByRole('button', { name: 'View saved work' })).not.toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledTimes(1)
})

test('a failed attempt-history read leaves a recovered draft visible', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = String(input)
    if (url.endsWith('/tasks/task-1')) return response({ detail: 'Review required' }, 409)
    if (url.endsWith('/draft')) return response({
      id: 'draft-1', task_id: 'task-1', answer: 'Recovered draft', code: null, circuit: null,
      updated_at: '2026-09-07T01:00:00Z',
    })
    return response({ detail: 'Temporary failure' }, 503)
  })
  renderPage()
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: 'View saved work' }))
  expect(await screen.findByText('Recovered draft')).toBeVisible()
  expect(screen.getByText(/Some saved work could not be loaded/)).toBeVisible()
})
