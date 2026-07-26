import { afterEach, describe, expect, test, vi } from 'vitest'

import {
  AnalyticsApiError,
  createAnalyticsApiClient,
  serializeAnalyticsFilters,
} from './api'
import {
  FILTER_OPTIONS,
  FILTERS,
  inactivePage,
  learningMetrics,
  metric,
  researchMetrics,
} from './testFixtures'

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init.headers },
  })
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('analytics API client', () => {
  test('serializes the complete UTC half-open filter contract', () => {
    const query = serializeAnalyticsFilters({
      ...FILTERS,
      experimentalCondition: 'agentic_rag',
      taskType: 'short_answer',
      model: 'model-a',
      judgeDecision: 'pass',
    })

    expect(Object.fromEntries(query)).toEqual({
      course_id: 'course-a',
      date_from: '2026-06-26T00:00:00.000Z',
      date_to: '2026-07-26T00:00:00.000Z',
      experimental_condition: 'agentic_rag',
      task_type: 'short_answer',
      model: 'model-a',
      judge_decision: 'pass',
    })
  })

  test('uses aggregate endpoint paths, credentials, and strict runtime validation', async () => {
    const fetchMock = vi.fn<typeof fetch>(async (input) => {
      const url = String(input)
      if (url.includes('/analytics/learning')) return jsonResponse(learningMetrics())
      if (url.includes('/analytics/research')) return jsonResponse(researchMetrics())
      if (url.includes('/analytics/filter-options')) return jsonResponse(FILTER_OPTIONS)
      return jsonResponse(inactivePage())
    })
    const client = createAnalyticsApiClient({
      apiBaseUrl: 'https://learn.example/api/v1/',
      fetch: fetchMock,
    })

    const [learning, research, options, inactive] = await Promise.all([
      client.getLearning(FILTERS),
      client.getResearch(FILTERS),
      client.getFilterOptions(),
      client.getInactiveLearners(FILTERS, 1, 25),
    ])

    expect(learning.completion_rate.value).toBe(0.75)
    expect(research.by_condition.agentic_rag.overall_pass_rate.value).toBe(0.8)
    expect(options.courses).toContain('course-a')
    expect(inactive.total).toBe(30)
    expect(inactive.schema_version).toBe('inactive-learners-v1')
    expect(inactive.filters.course_ids).toEqual(['course-a'])
    expect(inactive.inactive_learner_count).toMatchObject({
      value: 30,
      numerator: 30,
      denominator: 120,
      sample_size: 120,
      unit: 'learners',
    })
    expect(inactive.excluded_incomplete_count).toBe(0)
    expect(fetchMock.mock.calls.every(([, init]) => init?.credentials === 'include')).toBe(true)
    expect(fetchMock.mock.calls.map(([url]) => String(url))).toEqual(
      expect.arrayContaining([
        expect.stringContaining('/analytics/learning?'),
        expect.stringContaining('/analytics/research?'),
        'https://learn.example/api/v1/analytics/filter-options',
        expect.stringContaining('/analytics/inactive-learners?'),
      ]),
    )
  })

  test('preserves null measurements rather than coercing them to zero', async () => {
    const payload = researchMetrics()
    payload.by_condition.single_step_baseline.average_cost = metric(
      null,
      'currency_units',
    )
    const client = createAnalyticsApiClient({
      fetch: vi.fn<typeof fetch>(async () => jsonResponse(payload)),
    })

    const result = await client.getResearch(FILTERS)

    expect(result.by_condition.single_step_baseline.average_cost.value).toBeNull()
    expect(result.by_condition.single_step_baseline.average_cost.denominator).toBe(0)
  })

  test('rejects malformed aggregate and pagination payloads', async () => {
    const malformed = learningMetrics({
      completion_rate: {
        value: 0.8,
        numerator: 8,
        denominator: -10,
        sample_size: 10,
        unit: 'ratio',
      },
    })
    const malformedClient = createAnalyticsApiClient({
      fetch: vi.fn<typeof fetch>(async () => jsonResponse(malformed)),
    })
    await expect(malformedClient.getLearning(FILTERS)).rejects.toMatchObject({
      code: 'invalid_response',
    })

    const client = createAnalyticsApiClient({
      fetch: vi.fn<typeof fetch>(async () => jsonResponse(inactivePage())),
    })
    await expect(client.getInactiveLearners(FILTERS, 1, 101)).rejects.toMatchObject({
      code: 'invalid_request',
    })

    const oversizedPage = inactivePage({
      items: Array.from({ length: 26 }, (_, index) => ({
        pseudonymous_user_id: `v1_learner_${index}`,
        last_activity_at: null,
      })),
      page_size: 25,
      total: 26,
    })
    const oversizedClient = createAnalyticsApiClient({
      fetch: vi.fn<typeof fetch>(async () => jsonResponse(oversizedPage)),
    })
    await expect(
      oversizedClient.getInactiveLearners(FILTERS, 1, 25),
    ).rejects.toMatchObject({
      code: 'invalid_response',
    })

    const inconsistentTotal = inactivePage({
      inactive_learner_count: {
        value: 29,
        numerator: 29,
        denominator: 120,
        sample_size: 120,
        unit: 'learners',
      },
    })
    const inconsistentClient = createAnalyticsApiClient({
      fetch: vi.fn<typeof fetch>(async () => jsonResponse(inconsistentTotal)),
    })
    await expect(
      inconsistentClient.getInactiveLearners(FILTERS, 1, 25),
    ).rejects.toMatchObject({
      code: 'invalid_response',
    })
  })

  test('maps authorization failures without exposing response content', async () => {
    const client = createAnalyticsApiClient({
      fetch: vi.fn<typeof fetch>(async () =>
        new Response('private authorization detail', { status: 403 }),
      ),
    })

    const error = await client.getResearch(FILTERS).catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(AnalyticsApiError)
    expect(error).toMatchObject({ code: 'permission', status: 403 })
    expect(String(error)).not.toContain('private authorization detail')
  })

  test('preserves caller cancellation and bounds requests with a timeout', async () => {
    const hangingFetch = vi.fn<typeof fetch>(
      (_input, init) =>
        new Promise((_resolve, reject) => {
          init?.signal?.addEventListener(
            'abort',
            () => reject(new DOMException('Aborted', 'AbortError')),
            { once: true },
          )
        }),
    )
    const client = createAnalyticsApiClient({
      requestTimeoutMs: 1,
      fetch: hangingFetch,
    })

    await expect(client.getLearning(FILTERS)).rejects.toMatchObject({ code: 'timeout' })

    const controller = new AbortController()
    const request = client.getLearning(FILTERS, controller.signal)
    controller.abort()
    await expect(request).rejects.toMatchObject({ name: 'AbortError' })
  })

  test('builds filtered CSV and JSON export URLs', () => {
    const client = createAnalyticsApiClient({ apiBaseUrl: '/custom/api/v1/' })

    const csv = new URL(client.researchExportUrl('csv', FILTERS), 'https://example.test')
    const json = new URL(client.researchExportUrl('json', FILTERS), 'https://example.test')

    expect(csv.pathname).toBe('/custom/api/v1/research/exports')
    expect(csv.searchParams.get('format')).toBe('csv')
    expect(csv.searchParams.get('course_id')).toBe('course-a')
    expect(json.searchParams.get('format')).toBe('json')
  })
})
