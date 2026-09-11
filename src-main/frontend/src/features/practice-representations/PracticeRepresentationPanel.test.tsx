import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ApiError } from '../../app/api'
import { PracticeRepresentationPanel } from './PracticeRepresentationPanel'
import { practiceRepresentations, type Catalog, type Receipt } from './api'

const catalog: Catalog = {
  revision_id: 'revision', review_event_id: 'review', preference_version: 3, on_request: false,
  recommended_id: 'steps', selected_id: 'steps', selection: 'preference',
  explanation: 'Your format and detail preferences match this reviewed version.',
  choices: [
    { representation_id: 'steps', title: 'Boundary walkthrough', mode: 'stepwise', explanation_detail: 'detailed', support_kind: 'instructional', instructional_support_level: 3 },
    { representation_id: 'access', title: 'Readable program', mode: 'text', explanation_detail: 'brief', support_kind: 'accessibility', instructional_support_level: 0 },
  ],
}
const receipt: Receipt = {
  evidence_id: 'evidence', revision_id: 'revision', review_event_id: 'review', preference_version: 3,
  selection: 'preference', delivered_at: '2026-09-11T00:00:00Z',
  representation: { ...catalog.choices[0], text: 'Compare the equality case before tracing the branch.', steps: ['Inspect the boundary', 'Trace the selected branch'], circuit: null, source_references: ['reviewed-source'], equivalence_basis: 'Synthetic equivalence rationale for this test.' },
}

afterEach(() => vi.restoreAllMocks())

test('standard preferences deliver the actual reviewed detailed steps with provenance', async () => {
  vi.spyOn(practiceRepresentations, 'catalog').mockResolvedValue(catalog)
  const deliver = vi.spyOn(practiceRepresentations, 'deliver').mockResolvedValue(receipt)
  render(<PracticeRepresentationPanel taskId="task" preferenceVersion={3} />)
  expect(await screen.findByRole('list', { name: 'Explanation steps' })).toHaveTextContent('Inspect the boundaryTrace the selected branch')
  expect(deliver).toHaveBeenCalledWith('task', expect.objectContaining({ revision_id: 'revision', preference_version: 3, representation_id: 'steps', selection: 'preference' }), expect.any(AbortSignal))
  expect(screen.getByText('Sources: reviewed-source')).toBeVisible()
})

test('on-request content stays undisclosed until an explicit learner override', async () => {
  vi.spyOn(practiceRepresentations, 'catalog').mockResolvedValue({ ...catalog, on_request: true })
  const deliver = vi.spyOn(practiceRepresentations, 'deliver').mockResolvedValue({ ...receipt, selection: 'override', representation: { ...receipt.representation, ...catalog.choices[1], steps: [] } })
  render(<PracticeRepresentationPanel taskId="task" preferenceVersion={3} />)
  const access = await screen.findByRole('button', { name: /Open Readable program/ })
  expect(deliver).not.toHaveBeenCalled()
  expect(screen.queryByText(receipt.representation.text)).not.toBeInTheDocument()
  access.focus()
  await userEvent.setup().keyboard('{Enter}')
  expect(await screen.findByText(/Access support delivered/)).toBeVisible()
  expect(deliver).toHaveBeenCalledWith('task', expect.objectContaining({ representation_id: 'access', selection: 'override', preference_version: 3 }))
})

test('disabled work never automatically releases content and stale review leaves it hidden', async () => {
  vi.spyOn(practiceRepresentations, 'catalog').mockResolvedValue(catalog)
  const deliver = vi.spyOn(practiceRepresentations, 'deliver').mockRejectedValue(new ApiError('The reviewed task changed. Reload.', 409))
  const view = render(<PracticeRepresentationPanel taskId="task" preferenceVersion={3} disabled />)
  expect(await screen.findByRole('button', { name: /Open Boundary walkthrough/ })).toBeDisabled()
  expect(deliver).not.toHaveBeenCalled()
  view.rerender(<PracticeRepresentationPanel taskId="task" preferenceVersion={3} />)
  expect(await screen.findByRole('alert')).toHaveTextContent('The reviewed task changed')
  expect(screen.queryByText(receipt.representation.text)).not.toBeInTheDocument()
})

test('a retained override opens its reviewed content while preferences remain available', async () => {
  vi.spyOn(practiceRepresentations, 'catalog').mockResolvedValue({ ...catalog, selected_id: 'access', selection: 'override' })
  const deliver = vi.spyOn(practiceRepresentations, 'deliver').mockResolvedValue({ ...receipt, selection: 'override', representation: { ...receipt.representation, ...catalog.choices[1], steps: [] } })
  render(<PracticeRepresentationPanel taskId="task" preferenceVersion={3} />)
  await waitFor(() => expect(deliver).toHaveBeenCalledWith('task', expect.objectContaining({ representation_id: 'access', selection: 'override' }), expect.any(AbortSignal)))
  await userEvent.setup().click(screen.getByRole('button', { name: 'Use my presentation preferences' }))
  expect(deliver).toHaveBeenLastCalledWith('task', expect.objectContaining({ representation_id: 'steps', selection: 'preference' }))
})

test('a late automatic response cannot replace a learner override', async () => {
  vi.spyOn(practiceRepresentations, 'catalog').mockResolvedValue(catalog)
  let finishAutomatic!: (value: Receipt) => void
  const automatic = new Promise<Receipt>(resolve => { finishAutomatic = resolve })
  const accessReceipt: Receipt = { ...receipt, selection: 'override', representation: { ...receipt.representation, ...catalog.choices[1], text: 'Readable program content.', steps: [] } }
  vi.spyOn(practiceRepresentations, 'deliver').mockReturnValueOnce(automatic).mockResolvedValueOnce(accessReceipt)
  render(<PracticeRepresentationPanel taskId="task" preferenceVersion={3} />)
  await userEvent.setup().click(await screen.findByRole('button', { name: /Open Readable program/ }))
  expect(await screen.findByText('Readable program content.')).toBeVisible()
  await act(async () => { finishAutomatic(receipt); await automatic })
  expect(screen.getByText('Readable program content.')).toBeVisible()
  expect(screen.queryByText(receipt.representation.text)).not.toBeInTheDocument()
})

test('reapproval of the same revision starts a fresh delivery request', async () => {
  const list = vi.spyOn(practiceRepresentations, 'catalog').mockResolvedValue(catalog)
  const deliver = vi.spyOn(practiceRepresentations, 'deliver').mockResolvedValue(receipt)
  const view = render(<PracticeRepresentationPanel taskId="task" preferenceVersion={3} />)
  expect(await screen.findByText(receipt.representation.text)).toBeVisible()
  const originalKey = deliver.mock.calls[0][1].request_key
  list.mockResolvedValue({ ...catalog, review_event_id: 'reapproved' })
  view.rerender(<PracticeRepresentationPanel taskId="task" preferenceVersion={3} disabled />)
  await waitFor(() => expect(list).toHaveBeenCalledTimes(2))
  deliver.mockResolvedValue({ ...receipt, review_event_id: 'reapproved' })
  view.rerender(<PracticeRepresentationPanel taskId="task" preferenceVersion={3} />)
  await waitFor(() => expect(deliver).toHaveBeenCalledTimes(2))
  expect(deliver.mock.calls[1][1].request_key).not.toBe(originalKey)
  expect(await screen.findByText(receipt.representation.text)).toBeVisible()
})
