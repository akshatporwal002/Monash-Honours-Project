import { api } from '../../app/api'

describe('learner preference API isolation', () => {
  it('sends preference values only to the learner-self preference endpoint', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({
      pace: 'SLOWER', format: 'TEXT', explanation_detail: 'DETAILED', optional_breaks_enabled: true,
      repeat_practice_enabled: true, personalisation_enabled: false, revision: 1, saved: true,
    }), { status: 201, headers: { 'Content-Type': 'application/json' } }))

    await api.preferences.save({ pace: 'SLOWER', format: 'TEXT', explanation_detail: 'DETAILED', optional_breaks_enabled: true, repeat_practice_enabled: true, personalisation_enabled: false, expected_revision: 0, idempotency_key: 'preference-key' })

    expect(fetchMock).toHaveBeenCalledOnce()
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/v1/students/me/preferences')
    expect(init?.method).toBe('PUT')
    expect(String(init?.body)).not.toContain('learner_id')
    for (const path of ['/draft', '/checkpoint', '/simulate', '/transfer', '/help', '/submit', '/feedback']) {
      expect(String(url)).not.toContain(path)
    }
    fetchMock.mockRestore()
  })
})
