import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { api } from '../app/api'
import type { LearningTask } from '../app/types'
import { TaskView } from '../components/TaskView'
import { StructuredTask, StructuredSnapshot, type StructuredDefinition } from '../components/StructuredTask'
import { SupportRepresentation } from '../components/SupportRepresentation'
import { EpisodeSupport } from '../components/EpisodeSupport'
import type { EpisodeState } from '../app/types'

afterEach(() => vi.restoreAllMocks())
const items = [{ id: 'h', text: 'Hadamard gate', source_references: ['source'] }, { id: 'm', text: 'Measurement', source_references: ['source'] }]
const matching: StructuredDefinition = { schema_version: 'learnlens.matching.v1', task_type: 'matching', prompts: items, options: [{ ...items[0], id: 's', text: 'Changes amplitudes' }, { ...items[1], id: 'c', text: 'Produces a classical outcome' }] }

test('matching saves a partial draft, restores it, submits labels and renders readable saved evidence', async () => {
  const partial = JSON.stringify({ schema_version: 'learnlens.matching-response.v1', pairs: { h: 's' } })
  const task: LearningTask = { id: 'matching', title: 'Match', module: 'Quantum', description: 'Match operations', instructions: 'Use every option once', task_type: 'matching', structured_task: matching, difficulty: 'beginner', points: 0, position: 1, status: 'draft' }
  const draft = { id: 'draft', task_id: task.id, answer: partial, code: null, circuit: null, updated_at: '2026-09-11' }
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(Response.json([]))
  vi.spyOn(api.student, 'draft').mockResolvedValue(draft)
  vi.spyOn(api.student, 'attempts').mockResolvedValue([])
  const save = vi.spyOn(api.student, 'saveDraft').mockResolvedValue(draft)
  const submit = vi.spyOn(api.student, 'submit').mockImplementation(async (_, payload) => ({ id: 'attempt', answer: payload.answer ?? '', status: 'submitted', feedback: '' }))
  render(<TaskView task={task} onClose={() => {}} onSubmitted={async () => {}} />)
  const first = await screen.findByLabelText('Hadamard gate')
  expect(first).toHaveValue('s')
  expect(screen.getByRole('button', { name: 'Submit activity' })).toBeDisabled()
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Save draft' }))
  expect(save).toHaveBeenCalledWith(task.id, expect.objectContaining({ answer: partial }))
  await user.selectOptions(screen.getByLabelText('Measurement'), 'c')
  await user.click(screen.getByRole('button', { name: 'Submit activity' }))
  await waitFor(() => expect(submit).toHaveBeenCalledOnce())
  const saved = submit.mock.calls[0][1].answer ?? ''
  expect(JSON.parse(saved).labels['prompt:h']).toBe('Hadamard gate')
  await user.click(await screen.findByText('Saved response'))
  expect(screen.getByRole('table', { name: 'Saved matching evidence' })).toBeVisible()
  expect(screen.getByRole('cell', { name: 'Changes amplitudes' })).toBeVisible()
})

test('sequencing supports keyboard ordering, confirmation and saved evidence', async () => {
  const definition: StructuredDefinition = { schema_version: 'learnlens.sequencing.v1', task_type: 'sequencing', items }
  function Harness() {
    const [answer, setAnswer] = useState('')
    return <><StructuredTask definition={definition} answer={answer} onChange={setAnswer} /><StructuredSnapshot answer={answer} /></>
  }
  render(<Harness />)
  const move = screen.getByRole('button', { name: 'Move m earlier' })
  move.focus()
  await userEvent.setup().keyboard('{Enter}')
  expect(screen.getByRole('status')).toHaveTextContent('m, h')
  expect(screen.getAllByRole('list')[1].textContent).toBe('MeasurementHadamard gate')
  expect(screen.getByRole('button', { name: 'Move m earlier' })).toBeDisabled()
})

test('visual support includes the same ordered text evidence', () => {
  render(<SupportRepresentation value={{ instructional_support_level: 2, mode: 'visual', title: 'Inspect then explain', text: 'Inspect a state before explaining the operation.', steps: ['Inspect input', 'Explain operation'], circuit: null, source_references: ['source'], equivalence_basis: 'Same reviewed conceptual content.' }} />)
  expect(screen.getByRole('list', { name: 'Text equivalent of the diagram' })).toHaveTextContent('Inspect inputExplain operation')
  expect(screen.getByText('Sources: source')).toBeVisible()
})

test('reviewed representations are requested by frozen support index and disappear in transfer', async () => {
  vi.spyOn(api.student, 'helpHistory').mockResolvedValue({ items: [], next_offset: null })
  const record = { id: 'help', assessment_work_start_id: 'work', task_form_version_id: 'form', stage_start_id: null, part_id: 'supported', kind: 'conceptual_hint' as const, item_index: 1, created_at: '2026-09-11T00:00:00Z' }
  const request = vi.spyOn(api.student, 'recordHelp').mockResolvedValue({ record, content: 'Inspect then explain.', representation: { mode: 'visual', instructional_support_level: 2, title: 'State diagram', text: 'Inspect then explain.', steps: ['Inspect', 'Explain'], circuit: null, source_references: ['source'], equivalence_basis: 'Same conceptual content.' } } as Awaited<ReturnType<typeof api.student.recordHelp>>)
  const state: EpisodeState = { schema_version: 'learnlens.episode-plan.v1', supported_part_id: 'supported', prediction_required: false, required_responses: [], supported_hints: ['Conceptual hint 1'], accessibility_support: ['Keyboard controls'], transfer_part_id: 'transfer', transfer: null, representation_choices: [{ item_index: 1, title: 'State diagram', mode: 'visual' }] }
  const { rerender } = render(<EpisodeSupport taskId="task" workId="work" state={state} disabled={false} />)
  const button = await screen.findByRole('button', { name: 'Open State diagram (visual)' })
  button.focus()
  await userEvent.setup().keyboard('{Enter}')
  expect(await screen.findByRole('list', { name: 'Text equivalent of the diagram' })).toBeVisible()
  expect(request).toHaveBeenCalledWith('task', expect.objectContaining({ assessment_work_start_id: 'work', item_index: 1, kind: 'conceptual_hint' }))
  rerender(<EpisodeSupport taskId="task" workId="work" disabled={false} state={{ ...state, transfer: { stage_start_id: 'stage', part_id: 'transfer', prompt: 'Fresh application', instructions: 'Unaided', starter_code: null, starter_circuit: null } }} />)
  expect(screen.queryByText('Inspect then explain.')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Open State diagram (visual)' })).not.toBeInTheDocument()
  expect(screen.getByText('Keyboard controls')).toBeVisible()
})
