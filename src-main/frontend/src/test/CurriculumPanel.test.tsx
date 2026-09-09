import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import axe from 'axe-core'
import { DiagnosticCard } from '../components/CurriculumPanel'
import { curriculum } from '../app/curriculum'
import type { Diagnostic } from '../app/curriculum'

const record: Diagnostic = {
  id: 'diagnostic-1', learner_id: 1, learner_name: 'Learner', target_title: 'Fresh practice', pathway_id: 'pathway-1',
  purpose: 'initial', target_task_id: 'task-3', state: 'started', prompt: 'Explain H twice.',
  independent_conditions: 'Use no instructional help. Approved access support is allowed.', evidence_id: null, response: null, reason: null,
}
afterEach(() => vi.restoreAllMocks())

test('retains diagnostic answers after a failed save and retries the same request', async () => {
  const user = userEvent.setup()
  const saved = { ...record, state: 'needs_review' as const, evidence_id: 'evidence-1' }
  const submit = vi.spyOn(curriculum, 'submit').mockRejectedValueOnce(new Error('Connection lost')).mockResolvedValueOnce(saved)
  const onSaved = vi.fn()
  render(<DiagnosticCard record={record} staff={false} onSaved={onSaved} />)
  await user.type(screen.getByLabelText('Prior knowledge'), 'H twice restores the input.')
  await user.type(screen.getByLabelText('Reasoning'), 'H is its own inverse.')
  await user.click(screen.getByLabelText('I met the stated independent conditions'))
  await user.click(screen.getByRole('button', { name: 'Save diagnostic evidence' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Your entries are retained')
  expect(screen.getByLabelText('Reasoning')).toHaveValue('H is its own inverse.')
  await user.click(screen.getByRole('button', { name: 'Save diagnostic evidence' }))
  await waitFor(() => expect(onSaved).toHaveBeenCalledWith(saved))
  expect(submit.mock.calls[0]).toEqual(submit.mock.calls[1])
})

test('assessor sees learner evidence and explicitly records the reason and independence check', async () => {
  const user = userEvent.setup()
  const pending: Diagnostic = { ...record, state: 'needs_review', evidence_id: 'evidence-1', response: {
    request_key: 'response-1', prior_knowledge: 'H twice restores input', reasoning: 'H is self inverse', confidence: 'sure',
    concept_uncertainty: 'none_reported', requested_support: 'none', independent_conditions_met: true,
  } }
  const confirm = vi.spyOn(curriculum, 'confirm').mockResolvedValue({ ...pending, state: 'advance', reason: 'Verified against approved criteria' })
  render(<DiagnosticCard record={pending} staff onSaved={vi.fn()} />)
  expect(screen.getByText('H is self inverse')).toBeInTheDocument()
  expect(screen.getByText('Learner: Learner')).toBeInTheDocument()
  await user.selectOptions(screen.getByLabelText('Pathway decision'), 'advance')
  await user.click(screen.getByLabelText('Independent conditions verified'))
  await user.type(screen.getByLabelText('Assessor reason'), 'Verified against approved criteria')
  await user.click(screen.getByRole('button', { name: 'Confirm pathway decision' }))
  expect(confirm).toHaveBeenCalledWith(record.id, expect.objectContaining({ decision: 'advance', independent_verified: true, reason: 'Verified against approved criteria' }))
})

test('diagnostic form has labelled keyboard controls and passes Axe', async () => {
  const { container } = render(<DiagnosticCard record={record} staff={false} onSaved={vi.fn()} />)
  const user = userEvent.setup()
  await user.tab()
  expect(screen.getByLabelText('Prior knowledge')).toHaveFocus()
  expect((await axe.run(container)).violations).toEqual([])
})
