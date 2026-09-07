import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TaskView } from '../components/TaskView'
import type { LearningTask } from '../app/types'

beforeEach(() => vi.restoreAllMocks())

const task: LearningTask = {
  id: 'task-13', title: 'Explain the circuit', module: 'Quantum', description: 'Explain your prediction.',
  instructions: 'Use your own reasoning.', task_type: 'short_answer', difficulty: 'beginner',
  points: 0, position: 1, status: 'in_progress', score: null,
  assessment: {
    task_form_version_id: 'form-original', purpose: 'SUMMATIVE', bloom_process: 'APPLY',
    knowledge_dimension: 'PROCEDURAL', claim: 'Apply the circuit to a fresh example.', criteria: [],
    task_conditions: { stage: 'supported' }, permitted_tools: { allowed: ['approved notes'] },
    instructional_support: { hints: 'Unlimited approved conceptual hints' },
    access_conditions: { modes: [{ mode: 'screen_reader', preserves_construct: true }] }, transfer_rule: { stage: 'Separate unaided transfer' },
    review_rule: 'An assessor confirms the result.',
  },
}
const draft = { id: 'draft-13', task_id: task.id, answer: 'My saved reasoning', code: null, circuit: null,
  updated_at: '2026-09-07T00:00:00Z', assessment_work_start_id: 'work-original' }
function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}
function showTask() {
  render(<TaskView task={task} onClose={() => {}} onSubmitted={async () => {}} />)
}

test('workspace pins the displayed form and retains its work reference on save and submit', async () => {
  const mock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input)
    if (url.endsWith('/draft')) return response(draft)
    if (url.endsWith('/start')) return response(draft)
    if (init?.method === 'POST') return response({ id: 'attempt', status: 'submitted', score: null, formal_assessment: { result: null }, assessment_work_start_id: 'work-original' })
    return response([])
  })
  showTask()
  expect(await screen.findByDisplayValue('My saved reasoning')).toBeVisible()
  expect(screen.getByText('Unlimited approved conceptual hints')).toBeVisible()
  expect(screen.getByText('Separate unaided transfer')).toBeVisible()
  expect(screen.getByText('mode: screen reader; preserves construct: yes')).toBeVisible()
  expect(screen.queryByText('[object Object]')).not.toBeInTheDocument()
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Save draft' }))
  await screen.findByText('Draft saved.')
  await user.click(screen.getByRole('button', { name: 'Submit activity' }))
  await screen.findByRole('heading', { name: 'Assessment response saved' })
  const start = mock.mock.calls.find(([url]) => String(url).endsWith('/start'))
  expect(JSON.parse(String(start?.[1]?.body))).toEqual({ task_form_version_id: 'form-original' })
  const writes = mock.mock.calls.filter(([, init]) => init?.method === 'PUT' || (init?.method === 'POST' && String(init?.body).includes('idempotency_key')))
  expect(writes).toHaveLength(2)
  for (const [, init] of writes) expect(JSON.parse(String(init?.body)).assessment_work_start_id).toBe('work-original')
})

test('changed standards leave saved work visible and never refresh onto a newer form', async () => {
  const mock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = String(input)
    if (url.endsWith('/draft')) return response(draft)
    if (url.endsWith('/start')) return response({ detail: 'Assessment conditions changed. Your saved work is preserved; ask your assessor to review the conflict.' }, 409)
    return response([])
  })
  showTask()
  expect(await screen.findByDisplayValue('My saved reasoning')).toBeVisible()
  expect(screen.getByRole('alert')).toHaveTextContent('ask your assessor to review')
  expect(screen.getByRole('button', { name: 'Save draft' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Submit activity' })).toBeDisabled()
  expect(mock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
})

test('a submission conflict preserves local edits and stops later writes', async () => {
  const mock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input)
    if (url.endsWith('/draft') || url.endsWith('/start')) return response(draft)
    if (init?.method === 'POST') return response({ detail: 'Assessment conditions changed. Ask your assessor to review the conflict.' }, 409)
    return response([])
  })
  showTask()
  const input = await screen.findByDisplayValue('My saved reasoning')
  const user = userEvent.setup()
  await user.type(input, ' plus my new evidence')
  await user.click(screen.getByRole('button', { name: 'Submit activity' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Submit activity' })).toBeDisabled())
  expect(input).toHaveValue('My saved reasoning plus my new evidence')
  expect(mock.mock.calls.filter(([url]) => String(url).endsWith('/start'))).toHaveLength(1)
})


test('a transient start failure can retry the same displayed standard', async () => {
  let starts = 0
  const mock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = String(input)
    if (url.endsWith('/draft')) return response(draft)
    if (url.endsWith('/start')) return ++starts === 1 ? response({ detail: 'Temporary service fault' }, 503) : response(draft)
    return response([])
  })
  showTask()
  expect(await screen.findByRole('alert')).toHaveTextContent('Temporary service fault')
  expect(screen.getByRole('button', { name: 'Save draft' })).toBeDisabled()
  await userEvent.setup().click(screen.getByRole('button', { name: 'Try restoring again' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Save draft' })).toBeEnabled())
  const startCalls = mock.mock.calls.filter(([url]) => String(url).endsWith('/start'))
  expect(startCalls).toHaveLength(2)
  for (const [, init] of startCalls) expect(JSON.parse(String(init?.body)).task_form_version_id).toBe('form-original')
})
