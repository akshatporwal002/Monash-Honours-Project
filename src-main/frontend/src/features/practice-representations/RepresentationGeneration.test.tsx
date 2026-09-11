import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RepresentationGeneration } from './RepresentationGeneration'
import { EpisodeAccessEditor } from './EpisodeAccessEditor'

afterEach(() => vi.restoreAllMocks())

test('generation saves a revision-bound transfer-access draft without approval requests', async () => {
  const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } }))
  const onSaved = vi.fn()
  const onBusy = vi.fn()
  render(<RepresentationGeneration taskId="task" revisionId="revision" episode disabled={false} onBusy={onBusy} onSaved={onSaved} />)
  const user = userEvent.setup()
  await user.selectOptions(screen.getByLabelText('Stage for generated alternatives'), 'transfer')
  await user.click(screen.getByRole('button', { name: 'Generate alternatives and save draft' }))
  await waitFor(() => expect(onSaved).toHaveBeenCalledOnce())
  expect(fetch).toHaveBeenCalledOnce()
  const [url, init] = fetch.mock.calls[0]
  expect(String(url)).toMatch(/\/practice-representations\/tasks\/task\/generate$/)
  expect(JSON.parse(String(init?.body))).toEqual({ expected_revision_id: 'revision', target: 'transfer' })
  expect(onBusy.mock.calls).toEqual([[true], [false]])
  expect(screen.queryByRole('button', { name: /Approve/ })).not.toBeInTheDocument()
})

test('unsaved changes disable generation and stale revisions remain visible as errors', async () => {
  const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ detail: 'Task content changed; reload before generating representations' }), { status: 409, headers: { 'Content-Type': 'application/json' } }))
  const onSaved = vi.fn()
  const view = render(<RepresentationGeneration taskId="task" revisionId="old" episode={false} disabled onBusy={() => {}} onSaved={onSaved} />)
  expect(screen.getByRole('button', { name: 'Generate alternatives and save draft' })).toBeDisabled()
  expect(fetch).not.toHaveBeenCalled()
  view.rerender(<RepresentationGeneration taskId="task" revisionId="old" episode={false} disabled={false} onBusy={() => {}} onSaved={onSaved} />)
  await userEvent.setup().click(screen.getByRole('button', { name: 'Generate alternatives and save draft' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Task content changed')
  expect(onSaved).not.toHaveBeenCalled()
})

test('stage access editor fixes the support level at zero and keeps transfer content separate', async () => {
  const onChange = vi.fn()
  const value = { episode_plan: { transfer: { prompt: 'Private fresh input.' }, supported_hints: ['Concept cue'] } }
  render(<EpisodeAccessEditor value={value} disabled={false} onChange={onChange} />)
  const user = userEvent.setup()
  await user.click(screen.getByText('Equivalent access forms by stage'))
  await user.click(screen.getByRole('button', { name: 'Add transfer access form' }))
  const saved = onChange.mock.calls[0][0]
  expect(saved.episode_plan.transfer.access_representations[0].instructional_support_level).toBe(0)
  expect(saved.episode_plan.supported_hints).toEqual(['Concept cue'])
  expect(saved.episode_plan.access_representations).toBeUndefined()
})
