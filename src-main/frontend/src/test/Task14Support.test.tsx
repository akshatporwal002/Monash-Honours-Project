import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { api } from '../app/api'
import type { ApiSchemas } from '../api/generated'
import type { EpisodeState } from '../app/types'
import { EpisodeSupport } from '../components/EpisodeSupport'
import type { Representation } from '../components/SupportRepresentation'

beforeEach(() => vi.restoreAllMocks())

test('support retries preserve the request key and appended history deduplicates concurrent pages', async () => {
  const state: EpisodeState = { supported_part_id: 'supported', transfer_part_id: 'fresh', prediction_required: true, required_responses: ['prediction', 'explanation'], supported_hints: ['Conceptual hint 1'], accessibility_support: ['Text circuit available'] }
  const item = (id: string): ApiSchemas['EpisodeHelpUseRead'] => ({ id, assessment_work_start_id: 'work', task_form_version_id: 'form', stage_start_id: null, part_id: 'supported', kind: 'conceptual_hint', item_index: 0, created_at: '2026-09-07T01:00:00Z' })
  vi.spyOn(api.student, 'helpHistory').mockImplementation(async (_task, _signal, offset) => offset ? { items: [item('first'), item('older')], next_offset: null } : { items: [item('first')], next_offset: 1 })
  const request = vi.spyOn(api.student, 'recordHelp').mockRejectedValueOnce(new Error('Lost response')).mockResolvedValue({ record: item('new'), content: 'Approved conceptual hint' })
  const view = render(<EpisodeSupport taskId="task" workId="work" state={state} disabled={false} />)
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Request conceptual hint 1' }))
  expect(await screen.findByText(/Support request could not be saved/)).toBeVisible()
  await user.click(screen.getByRole('button', { name: 'Request conceptual hint 1' }))
  expect(await screen.findByLabelText('Requested conceptual hint')).toHaveTextContent('Approved conceptual hint')
  expect(request.mock.calls[0][1].request_key).toBe(request.mock.calls[1][1].request_key)
  await user.click(screen.getByText('Support request history'))
  await user.click(screen.getByRole('button', { name: 'Load earlier support requests' }))
  expect(screen.getAllByText(/^Conceptual hint request 1,/)).toHaveLength(3)
  view.rerender(<EpisodeSupport taskId="task" workId="work" state={{ ...state, supported_hints: [], transfer: { stage_start_id: 'stage', part_id: 'fresh', prompt: 'Fresh application', instructions: 'Apply H' } }} disabled={false} />)
  expect(screen.queryByLabelText('Requested conceptual hint')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Request conceptual hint 1' })).not.toBeInTheDocument()
  expect(screen.getByText('Text circuit available')).toBeVisible()
  expect(screen.getByRole('button', { name: 'I used access support 1' })).toBeEnabled()
})

test('preferences choose actual reviewed detail and transfer opens only its access variant', async () => {
  vi.spyOn(api.student, 'helpHistory').mockResolvedValue({ items: [], next_offset: null })
  const representation: Representation = { mode: 'stepwise', instructional_support_level: 2, title: 'Detailed source explanation', text: 'Actual reviewed detail.', steps: ['Inspect the source', 'Connect the task'], circuit: null, source_references: ['source'], equivalence_basis: 'Reviewed test rationale.' }
  const record = { id: 'receipt', assessment_work_start_id: 'work', task_form_version_id: 'form', stage_start_id: null, part_id: 'supported', kind: 'conceptual_hint' as const, item_index: 1, created_at: '2026-09-11T00:00:00Z' }
  const request = vi.spyOn(api.student, 'recordHelp').mockResolvedValue({ record, content: representation.text, representation })
  const state: EpisodeState = { supported_part_id: 'supported', transfer_part_id: 'fresh', prediction_required: true, required_responses: ['prediction'], representation_choices: [{ item_index: 0, title: 'Brief text', mode: 'text', explanation_detail: 'brief' }, { item_index: 1, title: 'Detailed steps', mode: 'stepwise', explanation_detail: 'detailed' }] }
  const view = render(<EpisodeSupport taskId="task" workId="work" state={state} disabled={false} onRequest format="stepwise" detail="detailed" />)
  const user = userEvent.setup()
  expect(request).not.toHaveBeenCalled()
  await user.click(screen.getByRole('button', { name: 'Use my representation preferences' }))
  expect(request.mock.calls[0][1]).toMatchObject({ kind: 'conceptual_hint', item_index: 1 })
  expect(await screen.findByText('Actual reviewed detail.')).toBeVisible()
  request.mockResolvedValue({ record: { ...record, id: 'access-receipt', kind: 'accessibility', stage_start_id: 'stage', part_id: 'fresh' }, content: 'Fresh input in equivalent text.', representation: { ...representation, instructional_support_level: 0, text: 'Fresh input in equivalent text.' } })
  view.rerender(<EpisodeSupport taskId="task" workId="work" state={{ ...state, representation_choices: [], access_representation_choices: [{ item_index: 1, title: 'Fresh equivalent input', mode: 'stepwise', explanation_detail: 'detailed' }], transfer: { stage_start_id: 'stage', part_id: 'fresh', prompt: 'Fresh task', instructions: 'Work independently.' } }} disabled={false} format="stepwise" detail="detailed" />)
  expect(screen.queryByText('Actual reviewed detail.')).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Use my representation preferences' }))
  expect(request.mock.calls[1][1]).toMatchObject({ kind: 'accessibility', item_index: 1, stage_start_id: 'stage' })
  expect(await screen.findByText('Fresh input in equivalent text.')).toBeVisible()
})
