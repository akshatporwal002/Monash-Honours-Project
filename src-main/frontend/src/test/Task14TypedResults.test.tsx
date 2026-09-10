import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { api } from '../app/api'
import type { LearningTask, TaskDraft, TaskType } from '../app/types'
import { TaskView } from '../components/TaskView'

const types: TaskType[] = ['prediction', 'reasoning', 'explanation', 'revision', 'reflection', 'transfer']
test.each(types)('%s displays restored fresh circuit results and preserves saved supported input', async taskType => {
  const task: LearningTask = { id: `task-${taskType}`, title: 'Typed episode', module: 'Hadamard', description: 'Apply H', instructions: 'Explain your result', task_type: taskType, difficulty: 'beginner', points: 0, position: 1, status: 'draft',  }
  const draft: TaskDraft = {
    id: 'draft', task_id: task.id, answer: '  Saved answer\n', code: '  saved.h(0)\n',
    circuit: { qubits: 1, operations: [{ gate: 'h', targets: [0] }] }, updated_at: '2026-09-07T01:00:00Z',
    episode: { supported: { explanation: 'Equal probabilities' }, transfer: {
      stage_start_id: 'stage', part_id: 'fresh', content: { answer: 'Fresh answer' },
      process: { simulation_references: [{ run_id: 'run', circuit_version_id: 'circuit' }] },
    } },
  }
  vi.spyOn(api.student, 'draft').mockResolvedValue(draft)
  vi.spyOn(api.student, 'attempts').mockResolvedValue([])
  vi.spyOn(api.student, 'savedSimulation').mockResolvedValue({ run_id: 'run', counts: { '0': 512, '1': 512 }, probabilities: { '0': 0.5, '1': 0.5 }, sampled_frequencies: { '0': 0.5, '1': 0.5 }, shots: 1024, engine: 'Qiskit Aer', circuit_text: 'H on qubit 0' })
  const saved = vi.spyOn(api.student, 'saveDraft').mockResolvedValue(draft)
  render(<TaskView task={task} onClose={() => {}} onSubmitted={async () => {}} />)
  expect(await screen.findByRole('table', { name: 'Exact probabilities and sampled frequencies' })).toBeVisible()
  expect(screen.getAllByText('50.00%')).toHaveLength(4)
  expect(screen.getByText('H on qubit 0')).toBeVisible()
  await userEvent.setup().click(screen.getByRole('button', { name: 'Save draft' }))
  expect(saved).toHaveBeenCalledWith(task.id, expect.objectContaining({ answer: draft.answer, code: draft.code, circuit: draft.circuit }))
})
