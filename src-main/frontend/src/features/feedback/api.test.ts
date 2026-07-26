import { afterEach, describe, expect, test, vi } from 'vitest'

import { createFeedbackApiClient, FeedbackApiError } from './api'

const processingResponse = {
  workflow_run_id: 'workflow-1',
  submission_id: 'submission-1',
  status: 'processing',
  processing_stage: 'context_collection',
  feedback: null,
  error: null,
}

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  const headers = new Headers(init.headers)
  headers.set('Content-Type', 'application/json')
  return new Response(JSON.stringify(body), { ...init, headers })
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('feedback API client', () => {
  test('uses the configured base URL, credentials, CSRF hook, and Retry-After header', async () => {
    const fetchMock = vi.fn<typeof fetch>(async () =>
      jsonResponse(processingResponse, {
        status: 202,
        headers: { 'Retry-After': '2' },
      }),
    )
    const client = createFeedbackApiClient({
      apiBaseUrl: 'https://learn.example/api/v1/',
      getCsrfToken: () => 'csrf-value',
      fetch: fetchMock,
    })

    const result = await client.start('submission / one')

    expect(result.response.processing_stage).toBe('context_collection')
    expect(result.retryAfterMs).toBe(2_000)
    expect(fetchMock).toHaveBeenCalledOnce()
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe(
      'https://learn.example/api/v1/submissions/submission%20%2F%20one/feedback',
    )
    expect(init?.credentials).toBe('include')
    expect(new Headers(init?.headers).get('X-CSRF-Token')).toBe('csrf-value')
  })

  test('does not send a CSRF header for reads', async () => {
    const fetchMock = vi.fn<typeof fetch>(async () => jsonResponse(processingResponse))
    const client = createFeedbackApiClient({
      getCsrfToken: () => 'csrf-value',
      fetch: fetchMock,
    })

    await client.get('submission-1')

    const [, init] = fetchMock.mock.calls[0]
    expect(new Headers(init?.headers).has('X-CSRF-Token')).toBe(false)
  })

  test('validates report responses at runtime', async () => {
    const fetchMock = vi.fn<typeof fetch>(async () =>
      jsonResponse({ report_id: 'report-1', status: 'received' }, { status: 201 }),
    )
    const client = createFeedbackApiClient({ fetch: fetchMock })

    await expect(
      client.report('feedback-1', { category: 'unclear', note: 'Needs an example.' }),
    ).resolves.toEqual({ report_id: 'report-1', status: 'received' })

    const [, init] = fetchMock.mock.calls[0]
    expect(init?.body).toBe(
      JSON.stringify({ category: 'unclear', note: 'Needs an example.' }),
    )
  })

  test.each([
    { ...processingResponse, processing_stage: 'completed' },
    { ...processingResponse, workflow_run_id: '' },
    { ...processingResponse, status: 'validated', processing_stage: null },
  ])('rejects malformed workflow payloads', async (payload) => {
    const client = createFeedbackApiClient({
      fetch: vi.fn<typeof fetch>(async () => jsonResponse(payload)),
    })

    await expect(client.get('submission-1')).rejects.toMatchObject({
      name: 'FeedbackApiError',
      code: 'invalid_response',
    })
  })

  test('accepts sanitized terminal failures with either retry policy', async () => {
    const terminalFailure = {
      workflow_run_id: 'workflow-1',
      submission_id: 'submission-1',
      status: 'failed',
      processing_stage: null,
      feedback: null,
      error: {
        code: 'feedback_processing_failed',
        message: 'Feedback processing could not be completed.',
        retryable: false,
      },
    }
    const client = createFeedbackApiClient({
      fetch: vi.fn<typeof fetch>(async () => jsonResponse(terminalFailure)),
    })

    await expect(client.get('submission-1')).resolves.toMatchObject({
      response: {
        status: 'failed',
        error: { retryable: false },
      },
    })
  })

  test('does not expose an HTTP error body', async () => {
    const client = createFeedbackApiClient({
      fetch: vi.fn<typeof fetch>(async () =>
        new Response('provider secret and raw answer', { status: 503 }),
      ),
    })

    const error = await client.get('submission-1').catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(FeedbackApiError)
    expect(error).toMatchObject({ code: 'request_failed', status: 503 })
    expect(String(error)).not.toContain('provider secret')
    expect(String(error)).not.toContain('raw answer')
  })

  test('classifies offline and network failures without exposing raw errors', async () => {
    const online = vi.spyOn(window.navigator, 'onLine', 'get')
    online.mockReturnValue(false)
    const offlineClient = createFeedbackApiClient({
      fetch: vi.fn<typeof fetch>(),
    })
    await expect(offlineClient.get('submission-1')).rejects.toMatchObject({
      code: 'offline',
    })

    online.mockReturnValue(true)
    const networkClient = createFeedbackApiClient({
      fetch: vi.fn<typeof fetch>(async () => {
        throw new Error('private DNS detail')
      }),
    })
    const error = await networkClient.get('submission-1').catch((caught: unknown) => caught)
    expect(error).toMatchObject({ code: 'network' })
    expect(String(error)).not.toContain('private DNS detail')
  })

  test('times out a request and preserves caller cancellation as AbortError', async () => {
    const neverCompletes = vi.fn<typeof fetch>(
      (_input, init) =>
        new Promise((_resolve, reject) => {
          init?.signal?.addEventListener(
            'abort',
            () => reject(new DOMException('Aborted', 'AbortError')),
            { once: true },
          )
        }),
    )
    const client = createFeedbackApiClient({
      requestTimeoutMs: 1,
      fetch: neverCompletes,
    })

    await expect(client.get('submission-1')).rejects.toMatchObject({ code: 'timeout' })

    const controller = new AbortController()
    const request = client.get('submission-1', controller.signal)
    controller.abort()
    await expect(request).rejects.toMatchObject({ name: 'AbortError' })
  })
})
