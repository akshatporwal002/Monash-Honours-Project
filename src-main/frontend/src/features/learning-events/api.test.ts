import { createLearningEventClient } from './api'

const EVENT_ID = '00000000-0000-4000-8000-000000000601'

describe('learning event client', () => {
  it('sends only the approved task-view fields without awaiting the response', () => {
    const fetchMock = vi.fn<typeof fetch>(() => new Promise(() => undefined))
    const client = createLearningEventClient({
      apiBaseUrl: '/custom-api/',
      createEventId: () => EVENT_ID,
      fetch: fetchMock,
      getCsrfToken: () => 'csrf-token',
    })

    client.record({
      eventType: 'task_view',
      taskId: 'task-1',
      source: 'task-page',
      actor_reference: 'must-not-leak',
      course_id: 'must-not-leak',
    } as never)

    expect(fetchMock).toHaveBeenCalledOnce()
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/custom-api/learning-events')
    expect(init).toMatchObject({
      method: 'POST',
      credentials: 'include',
      keepalive: true,
    })
    expect(JSON.parse(init?.body as string)).toEqual({
      event_id: EVENT_ID,
      event_type: 'task_view',
      task_id: 'task-1',
      metadata: { source: 'task-page' },
    })
    expect(new Headers(init?.headers).get('X-CSRF-Token')).toBe('csrf-token')
  })

  it('maps duration and silently drops invalid or sensitive-shaped input', () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(null))
    const client = createLearningEventClient({
      createEventId: () => EVENT_ID,
      fetch: fetchMock,
    })

    client.record({ eventType: 'draft_save', taskId: 'task-1', durationMs: 250 })
    client.record({ eventType: 'draft_save', taskId: 'task-1', durationMs: -1 })
    client.record({
      eventType: 'task_view',
      taskId: 'task-1',
      source: 'private answer',
    })

    expect(fetchMock).toHaveBeenCalledOnce()
    expect(JSON.parse(fetchMock.mock.calls[0][1]?.body as string)).toEqual({
      event_id: EVENT_ID,
      event_type: 'draft_save',
      task_id: 'task-1',
      metadata: { duration_ms: 250 },
    })
  })

  it('swallows request failures on the student path', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockRejectedValue(new Error('private failure'))
    const client = createLearningEventClient({
      createEventId: () => EVENT_ID,
      fetch: fetchMock,
    })

    expect(() =>
      client.record({ eventType: 'task_view', taskId: 'task-1' }),
    ).not.toThrow()
    await Promise.resolve()
  })
})

