import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { LearnerPreferencesSummary } from './LearnerPreferencesSummary'

const preferences = {
  pace: 'SLOWER',
  format: 'TEXT',
  explanation_detail: 'DETAILED',
  optional_breaks_enabled: true,
  repeat_practice_enabled: true,
  personalisation_enabled: false,
  revision: 4,
  saved: true,
}

describe('LearnerPreferencesSummary', () => {
  it('persists personalisation directly while the editor remains collapsed', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (_input, init) => {
      if (!init?.method || init.method === 'GET') {
        return new Response(JSON.stringify(preferences), { headers: { 'Content-Type': 'application/json' } })
      }
      return new Response(JSON.stringify({ ...preferences, personalisation_enabled: true, revision: 5 }), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      })
    })
    const user = userEvent.setup()

    render(<LearnerPreferencesSummary />)
    const toggle = await screen.findByRole('checkbox', { name: 'Allow non-essential personalisation' })
    expect(screen.getByRole('button', { name: 'Edit preferences' })).toHaveAttribute('aria-expanded', 'false')

    await user.click(toggle)

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    const [, request] = fetchMock.mock.calls[1]
    expect(request?.method).toBe('PUT')
    expect(JSON.parse(String(request?.body))).toMatchObject({
      ...preferences,
      personalisation_enabled: true,
      expected_revision: 4,
    })
    expect(screen.getByRole('button', { name: 'Edit preferences' })).toHaveAttribute('aria-expanded', 'false')
  })
})
