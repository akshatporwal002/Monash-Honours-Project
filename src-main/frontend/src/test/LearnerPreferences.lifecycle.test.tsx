import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { api } from '../app/api'
import { baselinePreferences } from '../app/preferences'
import { LearnerPreferences } from '../components/LearnerPreferences'
import type { ApiSchemas } from '../api/generated'

type Preferences = ApiSchemas['PreferenceRead']

function deferredPreferences() {
  let resolve!: (value: Preferences) => void
  const promise = new Promise<Preferences>(done => { resolve = done })
  return { promise, resolve }
}

function transition(type: 'pagehide' | 'pageshow', persisted = false) {
  window.dispatchEvent(new PageTransitionEvent(type, { persisted }))
}

afterEach(() => vi.restoreAllMocks())

test('aborts a pending preference load when its document departs', async () => {
  const pending = deferredPreferences()
  const read = vi.spyOn(api.student, 'preferences').mockReturnValue(pending.promise)
  const onSaved = vi.fn()
  render(<LearnerPreferences onSaved={onSaved} />)
  await waitFor(() => expect(read).toHaveBeenCalledOnce())

  act(() => transition('pagehide'))

  expect(read.mock.calls[0][0]?.aborted).toBe(true)
  await act(async () => pending.resolve({ version: 1, values: baselinePreferences }))
  expect(onSaved).not.toHaveBeenCalled()
})

test('does not begin the queued preference load after document departure', async () => {
  const read = vi.spyOn(api.student, 'preferences').mockResolvedValue({ version: 1, values: baselinePreferences })
  render(<LearnerPreferences />)

  act(() => transition('pagehide'))
  await act(async () => { await Promise.resolve() })

  expect(read).not.toHaveBeenCalled()
})

test('restoring a cached document restarts an interrupted load and rejects its stale result', async () => {
  const stale = deferredPreferences()
  const read = vi.spyOn(api.student, 'preferences')
    .mockReturnValueOnce(stale.promise)
    .mockResolvedValueOnce({ version: 2, values: baselinePreferences })
  const onSaved = vi.fn()
  render(<LearnerPreferences onSaved={onSaved} />)
  await waitFor(() => expect(read).toHaveBeenCalledOnce())
  const oldSignal = read.mock.calls[0][0]

  act(() => transition('pagehide', true))
  act(() => transition('pageshow', true))

  expect(await screen.findByText('Saved preferences loaded. Version 2.')).toBeVisible()
  expect(oldSignal?.aborted).toBe(true)
  expect(read.mock.calls[1][0]?.aborted).toBe(false)
  await act(async () => stale.resolve({ version: 1, values: baselinePreferences }))
  expect(screen.getByText('Saved preferences loaded. Version 2.')).toBeVisible()
  expect(onSaved).toHaveBeenCalledExactlyOnceWith({ version: 2, values: baselinePreferences })
})

test('restoring a cached document preserves an already-loaded unsaved preference draft', async () => {
  const read = vi.spyOn(api.student, 'preferences').mockResolvedValue({ version: 1, values: baselinePreferences })
  render(<LearnerPreferences />)
  await screen.findByText('Saved preferences loaded. Version 1.')
  await userEvent.setup().selectOptions(screen.getByLabelText('Pace'), 'stepwise')

  act(() => transition('pagehide', true))
  act(() => transition('pageshow', true))
  await act(async () => { await Promise.resolve() })

  expect(read).toHaveBeenCalledOnce()
  expect(screen.getByLabelText('Pace')).toHaveValue('stepwise')
  expect(screen.getByText('Unsaved preference changes.')).toBeVisible()
})
