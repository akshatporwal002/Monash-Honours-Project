import axe from 'axe-core'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'

import { AnalyticsApiError } from './api'
import { AnalyticsDashboard } from './AnalyticsDashboard'
import {
  FILTER_OPTIONS,
  FILTERS,
  inactivePage,
  learningMetrics,
  metric,
  researchMetrics,
} from './testFixtures'
import type {
  AnalyticsApiClient,
  AnalyticsFilterState,
  ConditionMetrics,
  LearningMetrics,
  ResearchMetrics,
} from './types'

function fakeClient(
  overrides: Partial<AnalyticsApiClient> = {},
): AnalyticsApiClient {
  return {
    async getLearning() {
      return learningMetrics()
    },
    async getResearch() {
      return researchMetrics()
    },
    async getFilterOptions() {
      return FILTER_OPTIONS
    },
    async getInactiveLearners() {
      return inactivePage()
    },
    researchExportUrl(format, filters) {
      const query = new URLSearchParams({
        format,
        course_id: filters.courseId,
        date_from: filters.dateFrom,
        date_to: filters.dateTo,
      })
      return `/api/v1/research/exports?${query.toString()}`
    },
    ...overrides,
  }
}

function emptyCondition(): ConditionMetrics {
  return {
    hallucination_rate: metric(null),
    overall_pass_rate: metric(null),
    average_relevance: metric(null, 'score'),
    average_latency_ms: metric(null, 'milliseconds'),
    p95_latency_ms: metric(null, 'milliseconds'),
    average_total_tokens: metric(null, 'tokens'),
    average_cost: metric(null, 'currency_units'),
    fallback_rate: metric(null),
  }
}

function emptyLearning(): LearningMetrics {
  const empty = metric(null)
  return learningMetrics({
    task_views: { ...empty, unit: 'events' },
    unique_task_views: { ...empty, unit: 'actor_task_pairs' },
    submissions: { ...empty, unit: 'events' },
    unique_submissions: { ...empty, unit: 'actor_task_pairs' },
    completion_rate: empty,
    average_score: { ...empty, unit: 'score' },
    total_attempts: { ...empty, unit: 'attempts' },
    average_attempts: { ...empty, unit: 'attempts' },
    feedback_view_rate: empty,
    inactive_learner_count: { ...empty, unit: 'learners' },
    funnel: learningMetrics().funnel.map((stage) => ({
      ...stage,
      count: 0,
      previous_stage_rate: empty,
    })),
  })
}

function emptyResearch(): ResearchMetrics {
  return researchMetrics({
    by_condition: {
      agentic_rag: emptyCondition(),
      single_step_baseline: emptyCondition(),
    },
    first_pass_rate: metric(null),
    regeneration_success_rate: metric(null),
    retrieval_hit_rate: metric(null),
    paired_agentic_minus_baseline: {
      pass_rate: metric(null, 'ratio_points'),
      relevance: metric(null, 'score'),
      latency_ms: metric(null, 'milliseconds'),
      total_tokens: metric(null, 'tokens'),
      cost: metric(null, 'currency_units'),
    },
  })
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

test('renders aggregate cards, funnel, judge results, performance, and paired comparison', async () => {
  const { container } = render(
    <AnalyticsDashboard client={fakeClient()} initialFilters={FILTERS} />,
  )

  expect(await screen.findByRole('heading', { name: 'Learning activity' })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Chronological engagement funnel' })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Judge and retrieval results' })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Latency and cost' })).toBeInTheDocument()
  expect(
    screen.getByRole('heading', { name: 'Paired agentic − baseline comparison' }),
  ).toBeInTheDocument()
  expect(screen.getAllByText('75%').length).toBeGreaterThan(0)
  expect(screen.getAllByText(/sample 10/).length).toBeGreaterThan(0)
  expect(
    screen.getByRole('table', {
      name: 'Text equivalent of the chronological engagement funnel',
    }),
  ).toBeInTheDocument()
  expect(container.querySelector('svg[aria-hidden="true"]')).toBeInTheDocument()
  expect((await axe.run(container)).violations).toEqual([])
})

test('applies keyboard-operated filters and exposes filter changes to the route owner', async () => {
  const user = userEvent.setup()
  const onFiltersChange = vi.fn<(filters: AnalyticsFilterState) => void>()
  const getLearning = vi.fn<AnalyticsApiClient['getLearning']>(async () =>
    learningMetrics(),
  )
  render(
    <AnalyticsDashboard
      client={fakeClient({ getLearning })}
      initialFilters={FILTERS}
      onFiltersChange={onFiltersChange}
    />,
  )
  await screen.findByRole('heading', { name: 'Learning activity' })

  await user.selectOptions(screen.getByLabelText('Course'), 'course-b')
  await user.selectOptions(screen.getByLabelText('Task type'), 'short_answer')
  const apply = screen.getByRole('button', { name: 'Apply filters' })
  apply.focus()
  await user.keyboard('{Enter}')

  await waitFor(() => expect(getLearning).toHaveBeenCalledTimes(2))
  expect(onFiltersChange).toHaveBeenCalledWith({
    ...FILTERS,
    courseId: 'course-b',
    taskType: 'short_answer',
  })
  expect(getLearning.mock.calls.at(-1)?.[0]).toMatchObject({
    courseId: 'course-b',
    taskType: 'short_answer',
  })
})

test('shows null metrics and incomplete measurements explicitly', async () => {
  const partial = researchMetrics({ excluded_incomplete_count: 2 })
  partial.by_condition.single_step_baseline.average_cost = metric(
    null,
    'currency_units',
  )
  render(
    <AnalyticsDashboard
      client={fakeClient({
        async getResearch() {
          return partial
        },
      })}
      initialFilters={FILTERS}
    />,
  )

  expect(await screen.findByText(/Some measurements are unavailable or excluded/)).toBeInTheDocument()
  expect(screen.getByText('Not available')).toBeInTheDocument()
  expect(screen.getByText('0 / 0; sample 0')).toBeInTheDocument()
})

test('renders a no-data state without inventing zeros', async () => {
  render(
    <AnalyticsDashboard
      client={fakeClient({
        async getLearning() {
          return emptyLearning()
        },
        async getResearch() {
          return emptyResearch()
        },
        async getInactiveLearners() {
          return inactivePage({ items: [], total: 0 })
        },
      })}
      initialFilters={FILTERS}
    />,
  )

  expect(await screen.findByRole('heading', { name: 'No analytics data' })).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Learning activity' })).not.toBeInTheDocument()
})

test('paginates inactive learners and enforces the 100-row UI limit', async () => {
  const user = userEvent.setup()
  const getInactiveLearners = vi.fn<AnalyticsApiClient['getInactiveLearners']>(
    async (_filters, page, pageSize) =>
      inactivePage({
        items: [
          {
            pseudonymous_user_id: `v1_page_${page}`,
            last_activity_at: null,
          },
        ],
        page,
        page_size: pageSize,
        total: 40,
      }),
  )
  render(
    <AnalyticsDashboard
      client={fakeClient({ getInactiveLearners })}
      initialFilters={FILTERS}
    />,
  )

  expect(await screen.findByText('v1_page_1')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Next' }))
  expect(await screen.findByText('v1_page_2')).toBeInTheDocument()
  expect(getInactiveLearners).toHaveBeenLastCalledWith(
    FILTERS,
    2,
    25,
    expect.any(AbortSignal),
  )

  await user.selectOptions(screen.getByLabelText('Rows per page'), '100')
  await waitFor(() =>
    expect(getInactiveLearners).toHaveBeenLastCalledWith(
      FILTERS,
      1,
      100,
      expect.any(AbortSignal),
    ),
  )
})

test('aborts stale aggregate requests when filters are superseded', async () => {
  const user = userEvent.setup()
  const aborted: string[] = []
  const pending = <T,>(label: string, signal?: AbortSignal) =>
    new Promise<T>((_resolve, reject) => {
      signal?.addEventListener(
        'abort',
        () => {
          aborted.push(label)
          reject(new DOMException('Aborted', 'AbortError'))
        },
        { once: true },
      )
    })
  const getLearning = vi.fn<AnalyticsApiClient['getLearning']>(
    async (filters, signal) => {
      if (filters.courseId === 'course-b') return pending('learning-b', signal)
      if (filters.courseId === 'course-c') {
        return learningMetrics({ task_views: metric(99, 'events', 99) })
      }
      return learningMetrics()
    },
  )
  const getResearch = vi.fn<AnalyticsApiClient['getResearch']>(
    async (filters, signal) => {
      if (filters.courseId === 'course-b') return pending('research-b', signal)
      return researchMetrics()
    },
  )
  render(
    <AnalyticsDashboard
      client={fakeClient({ getLearning, getResearch })}
      initialFilters={FILTERS}
    />,
  )
  await screen.findByRole('heading', { name: 'Learning activity' })

  await user.selectOptions(screen.getByLabelText('Course'), 'course-b')
  await user.click(screen.getByRole('button', { name: 'Apply filters' }))
  await waitFor(() =>
    expect(getLearning).toHaveBeenLastCalledWith(
      expect.objectContaining({ courseId: 'course-b' }),
      expect.any(AbortSignal),
    ),
  )
  await user.selectOptions(screen.getByLabelText('Course'), 'course-c')
  await user.click(screen.getByRole('button', { name: 'Apply filters' }))

  await waitFor(() => {
    expect(aborted).toEqual(expect.arrayContaining(['learning-b', 'research-b']))
  })
  expect(await screen.findByText('99')).toBeInTheDocument()
})

test('renders permission failures without leaking server detail', async () => {
  render(
    <AnalyticsDashboard
      client={fakeClient({
        async getLearning() {
          throw new AnalyticsApiError('permission', 403)
        },
      })}
      initialFilters={FILTERS}
    />,
  )

  expect(await screen.findByRole('alert')).toHaveTextContent(
    'do not have permission',
  )
  expect(screen.queryByText(/403|private/i)).not.toBeInTheDocument()
})

test('provides filtered CSV and JSON download controls', async () => {
  render(<AnalyticsDashboard client={fakeClient()} initialFilters={FILTERS} />)
  await screen.findByRole('heading', { name: 'Research export' })

  const csv = screen.getByRole('link', { name: 'Download CSV' })
  const json = screen.getByRole('link', { name: 'Download JSON' })
  expect(csv).toHaveAttribute('download')
  expect(csv).toHaveAttribute('href', expect.stringContaining('format=csv'))
  expect(csv).toHaveAttribute('href', expect.stringContaining('course_id=course-a'))
  expect(json).toHaveAttribute('download')
  expect(json).toHaveAttribute('href', expect.stringContaining('format=json'))
})

test('keeps mobile semantics accessible and honors reduced-motion preference', async () => {
  Object.defineProperty(window, 'innerWidth', {
    configurable: true,
    value: 375,
  })
  vi.stubGlobal(
    'matchMedia',
    vi.fn().mockImplementation((query: string) => ({
      matches: query === '(prefers-reduced-motion: reduce)',
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  )
  const { container } = render(
    <AnalyticsDashboard client={fakeClient()} initialFilters={FILTERS} />,
  )
  await screen.findByRole('heading', { name: 'Learning activity' })

  const dashboard = container.querySelector('.analytics-dashboard')
  expect(dashboard).toHaveAttribute('data-motion', 'reduce')
  expect(container.querySelectorAll('.analytics-table-scroll').length).toBeGreaterThan(0)
  for (const table of screen.getAllByRole('table')) {
    expect(within(table).getByText(table.querySelector('caption')?.textContent ?? '')).toBeInTheDocument()
    expect(table.querySelector('th[scope="col"]')).toBeInTheDocument()
  }
  expect((await axe.run(container)).violations).toEqual([])
})
