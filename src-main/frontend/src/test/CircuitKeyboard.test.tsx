import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { GateOperation, LearningTask } from '../app/types'
import { TaskView } from '../components/TaskView'
import { emptyPracticeCatalogResponse } from './practiceRepresentationFixtures'

const task: LearningTask = {
  id: 'keyboard-circuit', title: 'Place gates on either wire', module: 'Circuits',
  description: 'Build a circuit.', instructions: 'Choose the target wire.',
  task_type: 'quantum_circuit', difficulty: 'beginner', points: 0, position: 1,
  status: 'in_progress',
}

function setup(operations: GateOperation[] = [], qubits = 2) {
  let saved = { qubits, operations }
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const catalog = emptyPracticeCatalogResponse(input)
    if (catalog) return catalog
    const path = String(input)
    let body: unknown = []
    if (path.endsWith('/draft')) {
      if (init?.method === 'PUT') saved = JSON.parse(String(init.body)).circuit
      body = { id: 'draft', task_id: task.id, answer: '', code: null, circuit: saved, updated_at: '2026-09-10T00:00:00Z' }
    }
    return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } })
  })
  render(<TaskView task={task} onClose={() => {}} onSubmitted={async () => {}} />)
  return () => saved
}

afterEach(() => vi.restoreAllMocks())

test('task support siblings remain unique through saves and reset before another task loads', async () => {
  const secondTask = { ...task, id: 'second-circuit', title: 'Another circuit' }
  const pendingSecond: Array<() => void> = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const path = String(input)
    const taskId = path.includes(secondTask.id) ? secondTask.id : task.id
    let body: unknown = []
    if (path.includes('/practice-representations/tasks/')) {
      body = {
        revision_id: `revision-${taskId}`, review_event_id: `review-${taskId}`,
        preference_version: 0, on_request: true, selected_id: null,
        recommended_id: null, selection: 'preference', explanation: `Reviewed choices for ${taskId}`,
        choices: [{ representation_id: `choice-${taskId}`, title: taskId,
          mode: 'text', explanation_detail: 'brief', support_kind: 'accessibility',
          instructional_support_level: 0 }],
      }
    } else if (path.endsWith('/deadline')) {
      body = { task_id: taskId, time_zone: 'Australia/Sydney', original_due_at: null,
        effective_due_at: null, arrangement_active: false, reminders_paused: false,
        learner_notice: `Deadline notice for ${taskId}` }
    } else if (path.endsWith('/draft')) {
      body = { id: `draft-${taskId}`, task_id: taskId, answer: '', code: null,
        circuit: { qubits: 2, operations: [] }, updated_at: '2026-09-10T00:00:00Z' }
    }
    if (taskId === secondTask.id && (path.endsWith('/deadline') || path.includes('/practice-representations/tasks/'))) {
      await new Promise<void>(resolve => pendingSecond.push(resolve))
    }
    return Response.json(body)
  })
  const user = userEvent.setup()
  const { rerender } = render(<TaskView task={task} onClose={() => {}} onSubmitted={async () => {}} />)
  await screen.findByText('Saved draft restored.')
  await screen.findByText(`Reviewed choices for ${task.id}`)
  await screen.findByText(`Deadline notice for ${task.id}`)
  const expectUniqueSupport = () => {
    expect(screen.getAllByRole('region', { name: 'Reviewed practice representations' })).toHaveLength(1)
    expect(screen.getAllByRole('heading', { name: 'Your deadline' })).toHaveLength(1)
  }
  expectUniqueSupport()
  for (let saved = 0; saved < 3; saved++) {
    await user.click(screen.getByRole('button', { name: 'Add H gate' }))
    await user.click(screen.getByRole('button', { name: 'Save draft' }))
    await screen.findByText('Draft saved.')
    expectUniqueSupport()
  }
  rerender(<TaskView task={secondTask} onClose={() => {}} onSubmitted={async () => {}} />)
  expect(screen.queryByText(`Reviewed choices for ${task.id}`)).not.toBeInTheDocument()
  expect(screen.queryByText(`Deadline notice for ${task.id}`)).not.toBeInTheDocument()
  await waitFor(() => expect(pendingSecond.length).toBeGreaterThanOrEqual(2))
  await act(async () => pendingSecond.forEach(resolve => resolve()))
  await screen.findByText(`Reviewed choices for ${secondTask.id}`)
  await screen.findByText(`Deadline notice for ${secondTask.id}`)
  expectUniqueSupport()
})

test('keyboard targets the same second wire as drag, and preserves CX, remove and clear', async () => {
  const saved = setup()
  const user = userEvent.setup()
  await screen.findByText('Saved draft restored.')
  const target = screen.getByRole('combobox', { name: 'Target qubit for H and X' })
  target.focus()
  await user.selectOptions(target, '1')
  screen.getByRole('button', { name: 'Add H gate' }).focus()
  await user.keyboard('{Enter}')
  screen.getByRole('button', { name: 'Add X gate' }).focus()
  await user.keyboard(' ')
  await user.click(screen.getByRole('button', { name: 'Save draft' }))
  expect(saved().operations).toEqual([{ gate: 'h', targets: [1] }, { gate: 'x', targets: [1] }])
  const wire = screen.getByText('|0⟩ q1').parentElement!
  fireEvent.drop(wire, { dataTransfer: { getData: () => 'h' } })
  await user.click(screen.getByRole('button', { name: 'Save draft' }))
  expect(saved().operations[2]).toEqual(saved().operations[0])
  screen.getByRole('button', { name: 'Add CX gate' }).focus()
  await user.keyboard('{Enter}')
  await user.click(screen.getByRole('button', { name: 'Save draft' }))
  expect(saved().operations[3]).toEqual({ gate: 'cx', targets: [0, 1] })
  screen.getByRole('button', { name: 'Remove gate 2: X on qubit 1' }).focus()
  await user.keyboard('{Enter}')
  expect(screen.queryByRole('button', { name: 'Remove gate 2: X on qubit 1' })).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Save draft' }))
  expect(saved().operations).toEqual([{ gate: 'h', targets: [1] }, { gate: 'h', targets: [1] }, { gate: 'cx', targets: [0, 1] }])
  screen.getByRole('button', { name: 'Clear' }).focus()
  await user.keyboard('{Enter}')
  expect(screen.queryAllByTitle('Remove gate')).toHaveLength(0)
  expect(screen.getByRole('button', { name: 'Save draft' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Run 1,024 shots' })).toBeDisabled()
})

test('restored CX names distinguish control from target even when their wire order is reversed', async () => {
  setup([{ gate: 'x', targets: [1] }, { gate: 'cx', targets: [1, 0] }])
  await screen.findByText('Saved draft restored.')
  expect(screen.getByRole('button', { name: 'Remove gate 1: X on qubit 1' })).toBeVisible()
  expect(screen.getByRole('button', { name: 'Remove gate 2: CX, control qubit 1, target qubit 0 (control on qubit 1)' })).toHaveTextContent('●')
  expect(screen.getByRole('button', { name: 'Remove gate 2: CX, control qubit 1, target qubit 0 (target on qubit 0)' })).toHaveTextContent('⊕')
})

test('one-qubit restored work cannot select a second wire or add CX', async () => {
  setup([], 1)
  await screen.findByText('Saved draft restored.')
  const target = screen.getByRole('combobox', { name: 'Target qubit for H and X' })
  expect(target).toHaveValue('0')
  expect(target).toBeDisabled()
  expect(screen.queryByRole('button', { name: 'Add CX gate' })).not.toBeInTheDocument()
})

test('restored larger circuits expose every existing wire as an H or X target', async () => {
  const saved = setup([], 4)
  const user = userEvent.setup()
  await screen.findByText('Saved draft restored.')
  await user.selectOptions(screen.getByRole('combobox', { name: 'Target qubit for H and X' }), '3')
  screen.getByRole('button', { name: 'Add X gate' }).focus()
  await user.keyboard('{Enter}')
  await user.click(screen.getByRole('button', { name: 'Save draft' }))
  expect(saved()).toEqual({ qubits: 4, operations: [{ gate: 'x', targets: [3] }] })
})
