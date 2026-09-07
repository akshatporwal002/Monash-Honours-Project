import { useState } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { EpisodeFields } from '../components/EpisodeFields'
import { EpisodeSnapshot } from '../components/EpisodeSnapshot'
import type { EpisodePayload, EpisodeState } from '../app/types'

const state: EpisodeState = { supported_part_id: 'supported', prediction_required: true, required_responses: ['prediction', 'explanation'], supported_hints: ['Consider the input state.'], accessibility_support: ['Text circuit available'], transfer_part_id: 'fresh' }
function Harness() {
  const [value, setValue] = useState<EpisodePayload>({ schema_version: 'learnlens.episode.v1', supported: {} })
  const [stage, setStage] = useState(state)
  return <><EpisodeFields value={value} state={stage} attempts={[{ id: 'old', attempt_number: 1, score: null, feedback: null, status: 'submitted' }]} disabled={false} onChange={setValue} onCheckpoint={() => setValue({ ...value, supported: { ...value.supported, prediction_checkpoint_id: 'checkpoint' } })} onTransfer={() => {
    const transfer = { stage_start_id: 'start', part_id: 'fresh', prompt: 'Fresh approved application', instructions: 'Work independently', starter_circuit: { qubits: 1, operations: [] } }
    setStage({ ...state, supported_hints: [], transfer })
    setValue({ ...value, transfer: { stage_start_id: 'start', part_id: 'fresh', content: { answer: '', circuit: transfer.starter_circuit }, process: {} } })
  }} onTransferCheckpoint={() => {}} onTransferSimulation={() => {}} /><EpisodeSnapshot episode={value} /></>
}

test('keyboard episode controls retain separate prediction, reasoning, explanation, reflection and revision reason', async () => {
  render(<Harness />)
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('Your prediction before results'), '  Original prediction{Enter}')
  await user.type(screen.getByLabelText('Your reasoning'), '  Reason{Enter}')
  await user.type(screen.getByLabelText('Explain the result'), '  Explanation{Enter}')
  await user.type(screen.getByLabelText('Your reflection'), '  Reflection{Enter}')
  await user.selectOptions(screen.getByLabelText('Revise an earlier response'), 'old')
  await user.type(screen.getByLabelText('Reason for your revision'), '  A clearer claim{Enter}')
  screen.getByRole('button', { name: 'Record prediction for this input' }).focus()
  await user.keyboard('{Enter}')
  expect(screen.getByLabelText('Your prediction before results')).toHaveAttribute('readonly')
  expect(screen.getByLabelText('Your prediction before results')).toHaveValue('  Original prediction\n')
  expect(screen.getByLabelText('Your reasoning')).toHaveValue('  Reason\n')
  expect(screen.getByLabelText('Reason for your revision')).toHaveValue('  A clearer claim\n')
  expect(screen.getByRole('navigation', { name: 'Episode sections' })).toBeVisible()
})

test('transfer opens through its action, removes instructional hints and retains access support and editable fresh circuit', async () => {
  render(<Harness />)
  const user = userEvent.setup()
  expect(screen.queryByText('Fresh approved application')).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Start unaided fresh application' }))
  expect(screen.getByText('Fresh approved application')).toBeVisible()
  expect(screen.queryByText('Conceptual hints, use as often as needed')).not.toBeInTheDocument()
  expect(screen.getByText('Text circuit available')).toBeVisible()
  await user.type(screen.getByLabelText('Fresh application response'), '  Fresh answer{Enter}')
  await user.type(screen.getByLabelText('Fresh application code'), '  h(0){Enter}')
  screen.getByRole('button', { name: 'Add fresh H gate' }).focus()
  await user.keyboard('{Enter}')
  expect(screen.getByLabelText('Fresh application code')).toHaveValue('  h(0)\n')
  expect(screen.getByLabelText('Fresh application circuit text')).toHaveTextContent('H on qubit 0')
  expect(screen.getByRole('button', { name: 'Run fresh circuit' })).toBeDisabled()
})
