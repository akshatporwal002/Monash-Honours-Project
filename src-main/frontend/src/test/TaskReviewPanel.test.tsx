import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { TaskReviewPanel } from '../components/TaskReviewPanel'

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

function setupApi({ conflict = false, taskType = 'quantum_circuit', initialCriteria = { required_gates: ['h'] } }: { conflict?: boolean; taskType?: string; initialCriteria?: Record<string, unknown> } = {}) {
  let revision = 1
  let reviewVersion = 0
  let state = 'DRAFT'
  let prompt = 'Predict measurement after H'
  let criteria = initialCriteria
  const actions: unknown[] = []
  const edits: unknown[] = []
  const mock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input)
    if (url.endsWith('/courses/course-1/tasks')) return response([{ id: 'task-1', title: 'Hadamard practice' }])
    if (url.endsWith('/tasks/task-1') && init?.method === 'PATCH') {
      const payload = JSON.parse(String(init.body))
      edits.push(payload)
      if (conflict) return response({ detail: 'Task content changed; reload before saving edits' }, 409)
      prompt = payload.prompt
      if (payload.marking_criteria) criteria = payload.marking_criteria
      revision += 1
      state = 'DRAFT'
      reviewVersion = 0
      return response({ id: 'task-1' })
    }
    if (url.endsWith('/tasks/task-1/review')) {
      if (init?.method === 'POST') {
        const payload = JSON.parse(String(init.body))
        actions.push(payload)
        if (conflict) return response({ detail: 'Task review changed; reload its history' }, 409)
        state = payload.state
        reviewVersion += 1
        return response({ state })
      }
      return response({
        revision_id: `revision-${revision}`, revision, content_digest: 'digest', state,
        review_version: reviewVersion, available: state === 'APPROVED',
        issues: state === 'APPROVED' ? [] : ['Educator approval is required'],
      })
    }
    if (url.includes('/tasks/task-1/review/history')) return response([{
      revision: {
        id: `revision-${revision}`, version: revision, created_at: '2026-09-07T00:00:00Z',
        snapshot: { title: 'Hadamard practice', description: prompt, instructions: 'Explain the outcome',
          expected_answer: 'Equal probabilities', source_references: ['approved-passage'], task_type: taskType, marking_criteria: criteria },
      },
      events: reviewVersion ? [{ id: 'event-1', state, reason: 'Teaching content checked', created_at: '2026-09-07T00:00:00Z' }] : [],
    }])
    throw new Error(`Unexpected request: ${url}`)
  })
  return { mock, actions, edits }
}

async function openReview() {
  render(<TaskReviewPanel courseId="course-1" />)
  const user = userEvent.setup()
  await user.click(screen.getByRole('combobox', { name: 'Task to review' }))
  await user.click(await screen.findByRole('option', { name: 'Hadamard practice' }))
  await screen.findByRole('textbox', { name: 'Task prompt' })
  return user
}

test('edits circuit guidance while preserving saved settings and unrelated marking fields', async () => {
  const { edits } = setupApi({ initialCriteria: {
    required_gates: ['h'], instructor_note: 'Keep this guidance',
    starter_circuit: { qubits: 6, operations: [], shots: 2048, seed: 11 },
  } })
  const user = await openReview()
  const qubits = screen.getByRole('spinbutton', { name: 'Starter circuit qubits' })
  await user.clear(qubits)
  await user.type(qubits, '2')
  await user.click(screen.getByRole('button', { name: 'Add starter circuit gate' }))
  await user.click(screen.getByRole('combobox', { name: 'Starter circuit gate 1' }))
  await user.click(screen.getByRole('option', { name: 'CX' }))
  const targets = screen.getByRole('textbox', { name: 'Starter circuit targets 1' })
  await user.clear(targets)
  await user.type(targets, '0,1')
  await user.clear(screen.getByRole('textbox', { name: 'Required gates' }))
  await user.type(screen.getByRole('textbox', { name: 'Required gates' }), 'cx\n')
  expect(screen.getByRole('button', { name: 'Submit for review' })).toBeDisabled()
  await user.click(screen.getByRole('button', { name: 'Save task revision' }))
  await screen.findByText(/Revision 2/, { selector: 'p' })
  expect(edits).toEqual([expect.objectContaining({ expected_revision_id: 'revision-1', marking_criteria: {
    required_gates: ['cx'], instructor_note: 'Keep this guidance',
    starter_circuit: { qubits: 2, operations: [{ gate: 'cx', targets: [0, 1] }], shots: 2048, seed: 11 },
  } })])
})

test('edits answer choices and correct answer IDs without raw JSON', async () => {
  const { edits } = setupApi({ taskType: 'multiple_answer', initialCriteria: { choices: [{ id: 'a', text: 'First choice' }], correct_answers: ['a'] } })
  const user = await openReview()
  await user.click(screen.getByRole('button', { name: 'Add answer choice' }))
  await user.type(screen.getByRole('textbox', { name: 'Choice 2 ID' }), 'b')
  await user.type(screen.getByRole('textbox', { name: 'Choice 2 text' }), 'Repeated shots estimate a distribution')
  await user.type(screen.getByRole('textbox', { name: 'Correct choice IDs' }), '\nb')
  await user.click(screen.getByRole('button', { name: 'Save task revision' }))
  await screen.findByText(/Revision 2/, { selector: 'p' })
  expect(edits).toEqual([expect.objectContaining({ marking_criteria: { choices: [{ id: 'a', text: 'First choice' }, { id: 'b', text: 'Repeated shots estimate a distribution' }], correct_answers: ['a', 'b'] } })])
})

test('records explicit review actions against the loaded revision and shows history', async () => {
  const { actions } = setupApi()
  const user = await openReview()
  expect(screen.getByRole('button', { name: 'Submit for review' })).toBeDisabled()
  await user.type(screen.getByRole('textbox', { name: /Review reason/ }), 'Teaching content checked')
  await user.click(screen.getByRole('button', { name: 'Submit for review' }))
  await screen.findByText('Awaiting review')
  expect(screen.getByRole('button', { name: 'Approve task' })).toBeDisabled()
  await user.type(screen.getByRole('textbox', { name: /Review reason/ }), 'Source and guidance checked')
  await user.click(screen.getByRole('button', { name: 'Approve task' }))
  await screen.findByRole('button', { name: 'Withdraw approval' })
  expect(actions).toEqual([
    { expected_revision_id: 'revision-1', expected_review_version: 0, state: 'SUBMITTED', reason: 'Teaching content checked' },
    { expected_revision_id: 'revision-1', expected_review_version: 1, state: 'APPROVED', reason: 'Source and guidance checked' },
  ])
  await user.click(screen.getByText('Saved content and review history'))
  expect(screen.getByText('Expected answer: Equal probabilities')).toBeVisible()
  expect(screen.getByText('Source passages: approved-passage')).toBeVisible()
})

test('requires saving edits before review and sends the expected revision', async () => {
  const { edits } = setupApi()
  const user = await openReview()
  await user.type(screen.getByRole('textbox', { name: /Review reason/ }), 'Ready to review')
  await user.clear(screen.getByRole('textbox', { name: 'Task prompt' }))
  await user.type(screen.getByRole('textbox', { name: 'Task prompt' }), 'A fresh prediction')
  expect(screen.getByRole('button', { name: 'Submit for review' })).toBeDisabled()
  await user.click(screen.getByRole('button', { name: 'Save task revision' }))
  await waitFor(() => expect(screen.getByRole('textbox', { name: 'Task prompt' })).toHaveValue('A fresh prediction'))
  expect(edits).toEqual([expect.objectContaining({ expected_revision_id: 'revision-1', prompt: 'A fresh prediction' })])
  expect(screen.getByRole('button', { name: 'Submit for review' })).toBeDisabled()
  expect(screen.getByText(/Revision 2/, { selector: 'p' })).toBeInTheDocument()
})

test('shows stale review conflicts without claiming approval', async () => {
  setupApi({ conflict: true })
  const user = await openReview()
  await user.type(screen.getByRole('textbox', { name: /Review reason/ }), 'Checked')
  await user.click(screen.getByRole('button', { name: 'Submit for review' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Task review changed; reload its history')
  expect(screen.getByText('Draft')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Approve task' })).not.toBeInTheDocument()
})
