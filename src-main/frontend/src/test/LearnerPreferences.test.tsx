import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import axe from 'axe-core'
import { ApiError, api } from '../app/api'
import { baselinePreferences } from '../app/preferences'
import { LearnerPreferences } from '../components/LearnerPreferences'
import { PreferenceWorkspace } from '../components/PreferenceWorkspace'
import { EpisodeSupport } from '../components/EpisodeSupport'
import type { EpisodeState } from '../app/types'

beforeEach(() => { vi.spyOn(api.student, 'preferences').mockResolvedValue({ version: 1, values: baselinePreferences }) })
afterEach(() => vi.restoreAllMocks())

test('restores settings, keeps failed draft and request key, saves and resets without erasing history', async () => {
  const save = vi.spyOn(api.student, 'savePreferences').mockRejectedValueOnce(new Error('offline')).mockResolvedValue({ version: 2, values: { ...baselinePreferences, pace: 'stepwise' } })
  const reset = vi.spyOn(api.student, 'resetPreferences').mockResolvedValue({ version: 3, values: baselinePreferences })
  vi.spyOn(api.student, 'preferenceHistory').mockResolvedValue({ items: [{ version: 2, action: 'save', values: { ...baselinePreferences, pace: 'stepwise' }, created_at: '2026-09-08T00:00:00Z' }], next_offset: null })
  render(<LearnerPreferences />)
  const user = userEvent.setup()
  await screen.findByText(/Saved preferences loaded/)
  await user.selectOptions(screen.getByLabelText('Pace'), 'stepwise')
  await user.click(screen.getByRole('button', { name: 'Save preferences' }))
  expect(await screen.findByText(/Your draft is kept/)).toBeVisible()
  expect(screen.getByLabelText('Pace')).toHaveValue('stepwise')
  await user.click(screen.getByRole('button', { name: 'Save preferences' }))
  await screen.findByText('Preferences saved. Version 2.')
  expect(save.mock.calls[0][0].request_key).toBe(save.mock.calls[1][0].request_key)
  await user.click(screen.getByRole('button', { name: 'Reset and save defaults' }))
  await screen.findByText(/Preferences reset and saved/)
  expect(reset.mock.calls[0][0].expected_version).toBe(2)
  expect(screen.getByLabelText('Pace')).toHaveValue('self_paced')
  await user.click(screen.getByText('Preference change history'))
  await user.click(screen.getByRole('button', { name: 'Load preference history' }))
  expect(await screen.findByRole('heading', { name: /Version 2, save/ })).toBeVisible()
})

test('conflict requires explicit refresh and retains draft before resaving', async () => {
  const save = vi.spyOn(api.student, 'savePreferences').mockRejectedValueOnce(new ApiError('stale', 409)).mockResolvedValue({ version: 5, values: { ...baselinePreferences, breaks: true } })
  render(<LearnerPreferences />)
  const user = userEvent.setup()
  await screen.findByText(/Saved preferences loaded/)
  await user.click(screen.getByLabelText('Show save and break control'))
  await user.click(screen.getByRole('button', { name: 'Save preferences' }))
  const refresh = await screen.findByRole('button', { name: 'Refresh saved version, keep my draft' })
  expect(screen.getByRole('button', { name: 'Save preferences' })).toBeDisabled()
  vi.mocked(api.student.preferences).mockResolvedValue({ version: 4, values: baselinePreferences })
  await user.click(refresh)
  expect(screen.getByLabelText('Show save and break control')).toBeChecked()
  await user.click(screen.getByRole('button', { name: 'Save preferences' }))
  await screen.findByText('Preferences saved. Version 5.')
  expect(save.mock.calls[1][0].expected_version).toBe(4)
  expect(save.mock.calls[1][0].request_key).not.toBe(save.mock.calls[0][0].request_key)
})

test('labelled settings support keyboard input and have no Axe violations', async () => {
  const { container } = render(<main><LearnerPreferences /></main>)
  await screen.findByText(/Saved preferences loaded/)
  const user = userEvent.setup()
  screen.getByLabelText('Enable non-essential personalisation').focus()
  await user.keyboard(' ')
  expect(screen.getByLabelText('Enable non-essential personalisation')).not.toBeChecked()
  await user.tab()
  expect(screen.getByLabelText('Pace')).toHaveFocus()
  expect((await axe.run(container)).violations).toEqual([])
})

test('effective workspace changes guide, detail, breaks and practice, then returns to baseline', async () => {
  const actions = { onBreak: vi.fn(), onRepeat: vi.fn(), disabled: false }
  const values = { ...baselinePreferences, pace: 'stepwise' as const, format: 'stepwise' as const, explanation_detail: 'detailed' as const, breaks: true, repeat_practice: true }
  const effective = { version: 2, values, requested: values, transfer: false, repeat_allowed: true, limitations: ['Approved task conditions apply.'] }
  const view = render(<PreferenceWorkspace effective={effective} {...actions} />)
  const user = userEvent.setup()
  expect(screen.getByRole('navigation', { name: 'Stepwise workspace guide' })).toBeVisible()
  expect(within(screen.getByLabelText('Optional workspace guidance')).getByRole('list')).toBeVisible()
  expect(screen.getByText(/Use only the tools/)).toBeVisible()
  await user.click(screen.getByRole('button', { name: 'Save draft and take a break' }))
  await user.click(screen.getByRole('button', { name: 'Start another practice draft' }))
  expect(actions.onBreak).toHaveBeenCalledOnce(); expect(actions.onRepeat).toHaveBeenCalledOnce()
  view.rerender(<PreferenceWorkspace effective={{ ...effective, values: baselinePreferences }} {...actions} />)
  expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
  expect(screen.queryByRole('button')).not.toBeInTheDocument()
  view.rerender(<PreferenceWorkspace effective={{ ...effective, transfer: true }} {...actions} />)
  expect(screen.queryByLabelText('Optional workspace guidance')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Start another practice draft' })).not.toBeInTheDocument()
})

test('on-demand hints retain access support and unlimited request controls', async () => {
  vi.spyOn(api.student, 'helpHistory').mockResolvedValue({ items: [], next_offset: null })
  const state: EpisodeState = { supported_part_id: 'supported', transfer_part_id: 'fresh', prediction_required: true, required_responses: ['prediction', 'explanation'], supported_hints: ['Conceptual hint 1'], accessibility_support: ['Approved text circuit'] }
  const view = render(<EpisodeSupport taskId="task" workId="work" state={state} disabled={false} onRequest />)
  expect(screen.getByText('Approved text circuit')).toBeVisible()
  expect(screen.getByRole('button', { name: 'Request conceptual hint 1', hidden: true })).not.toBeVisible()
  const user = userEvent.setup()
  await user.click(screen.getByText('Open approved hint controls'))
  expect(screen.getByRole('button', { name: 'Request conceptual hint 1' })).toBeEnabled()
  view.rerender(<EpisodeSupport taskId="task" workId="work" state={state} disabled={false} />)
  expect(screen.getByRole('button', { name: 'Request conceptual hint 1' })).toBeVisible()
  expect(screen.getByRole('button', { name: 'I used access support 1' })).toBeEnabled()
})
