import { useEffect, useId, useMemo, useState } from 'react'

import { AnalyticsFilters } from './AnalyticsFilters'
import { AnalyticsApiError, createAnalyticsApiClient } from './api'
import { defaultAnalyticsFilters } from './defaults'
import { EngagementFunnel } from './EngagementFunnel'
import { ExportControls } from './ExportControls'
import { formatDateTime } from './format'
import { InactiveLearners } from './InactiveLearners'
import { LearningSummary } from './LearningSummary'
import { ResearchSummary } from './ResearchSummary'
import { useReducedMotion } from './useReducedMotion'
import type {
  AnalyticsApiClient,
  AnalyticsFilterOptions,
  AnalyticsFilterState,
  InactiveLearnerPage,
  LearningMetrics,
  MetricValue,
  ResearchMetrics,
} from './types'
import './analytics.css'

type AnalyticsDashboardProps = {
  client?: AnalyticsApiClient
  initialFilters?: AnalyticsFilterState
  onFiltersChange?: (filters: AnalyticsFilterState) => void
}

type LoadFailure =
  | 'invalid_request'
  | 'permission'
  | 'offline'
  | 'timeout'
  | 'network'
  | 'invalid_response'
  | 'request_failed'

type LoadStatus = 'loading' | 'ready' | 'error'

function failureCode(error: unknown): LoadFailure {
  return error instanceof AnalyticsApiError ? error.code : 'request_failed'
}

function failureMessage(failure: LoadFailure): string {
  if (failure === 'permission') {
    return 'You do not have permission to view analytics for these filters.'
  }
  if (failure === 'offline') return 'You appear to be offline. Reconnect and try again.'
  if (failure === 'timeout') return 'Analytics is taking longer than expected. Try again.'
  if (failure === 'network') {
    return 'Analytics could not be loaded. Check your connection and try again.'
  }
  if (failure === 'invalid_response') {
    return 'The analytics service returned an unexpected response. Try again.'
  }
  if (failure === 'invalid_request') return 'The selected analytics filters are invalid.'
  return 'Analytics could not be loaded. Try again.'
}

function hasMetricData(metrics: MetricValue[]): boolean {
  return metrics.some((metric) => metric.denominator > 0 || metric.sample_size > 0)
}

function hasSummaryData(learning: LearningMetrics, research: ResearchMetrics): boolean {
  const learningMetrics = [
    learning.task_views,
    learning.unique_task_views,
    learning.submissions,
    learning.unique_submissions,
    learning.completion_rate,
    learning.average_score,
    learning.total_attempts,
    learning.average_attempts,
    learning.feedback_view_rate,
    learning.inactive_learner_count,
  ]
  const researchMetrics = [
    research.first_pass_rate,
    research.regeneration_success_rate,
    research.retrieval_hit_rate,
    ...Object.values(research.by_condition).flatMap((condition) => [
      condition.overall_pass_rate,
      condition.hallucination_rate,
      condition.average_relevance,
      condition.average_latency_ms,
      condition.average_cost,
    ]),
  ]
  return (
    hasMetricData(learningMetrics) ||
    learning.funnel.some((stage) => stage.count > 0) ||
    hasMetricData(researchMetrics)
  )
}

function hasPartialMeasurements(
  learning: LearningMetrics,
  research: ResearchMetrics,
): boolean {
  if (
    learning.excluded_incomplete_count > 0 ||
    research.excluded_incomplete_count > 0
  ) {
    return true
  }
  const conditions = Object.values(research.by_condition)
  return conditions.some(
    (condition) =>
      condition.overall_pass_rate.denominator > 0 &&
      (condition.average_cost.value === null ||
        condition.average_total_tokens.value === null ||
        condition.average_relevance.value === null),
  )
}

export function AnalyticsDashboard({
  client,
  initialFilters,
  onFiltersChange,
}: AnalyticsDashboardProps) {
  const apiClient = useMemo(() => client ?? createAnalyticsApiClient(), [client])
  const [filters, setFilters] = useState<AnalyticsFilterState>(
    () => initialFilters ?? defaultAnalyticsFilters(),
  )
  const [filterOptions, setFilterOptions] = useState<AnalyticsFilterOptions | null>(null)
  const [filterOptionsStatus, setFilterOptionsStatus] = useState<LoadStatus>('loading')
  const [filterOptionsFailure, setFilterOptionsFailure] = useState<LoadFailure | null>(null)
  const [learning, setLearning] = useState<LearningMetrics | null>(null)
  const [research, setResearch] = useState<ResearchMetrics | null>(null)
  const [summaryStatus, setSummaryStatus] = useState<LoadStatus>('loading')
  const [summaryFailure, setSummaryFailure] = useState<LoadFailure | null>(null)
  const [inactivePage, setInactivePage] = useState<InactiveLearnerPage | null>(null)
  const [inactiveStatus, setInactiveStatus] = useState<LoadStatus>('loading')
  const [inactiveFailure, setInactiveFailure] = useState<LoadFailure | null>(null)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(25)
  const [requestVersion, setRequestVersion] = useState(0)
  const headingId = useId()
  const reducedMotion = useReducedMotion()

  useEffect(() => {
    const controller = new AbortController()
    async function loadOptions() {
      setFilterOptionsStatus('loading')
      setFilterOptionsFailure(null)
      try {
        const next = await apiClient.getFilterOptions(controller.signal)
        if (!controller.signal.aborted) {
          setFilterOptions(next)
          setFilterOptionsStatus('ready')
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          setFilterOptionsFailure(failureCode(error))
          setFilterOptionsStatus('error')
        }
      }
    }
    void loadOptions()
    return () => controller.abort()
  }, [apiClient, requestVersion])

  useEffect(() => {
    const controller = new AbortController()
    async function loadSummary() {
      setSummaryStatus('loading')
      setSummaryFailure(null)
      try {
        const [nextLearning, nextResearch] = await Promise.all([
          apiClient.getLearning(filters, controller.signal),
          apiClient.getResearch(filters, controller.signal),
        ])
        if (!controller.signal.aborted) {
          setLearning(nextLearning)
          setResearch(nextResearch)
          setSummaryStatus('ready')
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          setSummaryFailure(failureCode(error))
          setSummaryStatus('error')
        }
      }
    }
    void loadSummary()
    return () => controller.abort()
  }, [apiClient, filters, requestVersion])

  useEffect(() => {
    const controller = new AbortController()
    async function loadInactiveLearners() {
      setInactiveStatus('loading')
      setInactiveFailure(null)
      try {
        const next = await apiClient.getInactiveLearners(
          filters,
          page,
          pageSize,
          controller.signal,
        )
        if (!controller.signal.aborted) {
          setInactivePage(next)
          setInactiveStatus('ready')
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          setInactiveFailure(failureCode(error))
          setInactiveStatus('error')
        }
      }
    }
    void loadInactiveLearners()
    return () => controller.abort()
  }, [apiClient, filters, page, pageSize, requestVersion])

  const globalFailure =
    filterOptionsFailure ??
    summaryFailure ??
    (inactiveFailure === 'permission' ? inactiveFailure : null)
  const loadingOptions = filterOptionsStatus === 'loading' && filterOptions === null
  const loadingSummary = summaryStatus === 'loading' && (learning === null || research === null)

  function applyFilters(next: AnalyticsFilterState) {
    setFilters(next)
    setPage(1)
    onFiltersChange?.(next)
  }

  if (globalFailure === 'permission') {
    return (
      <section className="analytics-dashboard analytics-state" aria-labelledby={headingId}>
        <h1 id={headingId}>Learning and research analytics</h1>
        <p role="alert">{failureMessage(globalFailure)}</p>
      </section>
    )
  }

  if (loadingOptions || loadingSummary) {
    return (
      <section className="analytics-dashboard analytics-state" aria-labelledby={headingId}>
        <h1 id={headingId}>Learning and research analytics</h1>
        <p role="status">Loading analytics…</p>
      </section>
    )
  }

  if (
    filterOptionsStatus === 'error' ||
    summaryStatus === 'error' ||
    filterOptions === null ||
    learning === null ||
    research === null
  ) {
    const failure = globalFailure ?? 'request_failed'
    return (
      <section className="analytics-dashboard analytics-state" aria-labelledby={headingId}>
        <h1 id={headingId}>Learning and research analytics</h1>
        <p role="alert">{failureMessage(failure)}</p>
        <button type="button" onClick={() => setRequestVersion((value) => value + 1)}>
          Try again
        </button>
      </section>
    )
  }

  const noSummaryData = !hasSummaryData(learning, research)
  const partialMeasurements = hasPartialMeasurements(learning, research)
  const latestGeneratedAt =
    Date.parse(learning.generated_at) > Date.parse(research.generated_at)
      ? learning.generated_at
      : research.generated_at

  return (
    <section
      className="analytics-dashboard"
      aria-labelledby={headingId}
      data-motion={reducedMotion ? 'reduce' : 'no-preference'}
    >
      <header className="analytics-dashboard__header">
        <div>
          <p className="analytics-dashboard__eyebrow">Authorized aggregate view</p>
          <h1 id={headingId}>Learning and research analytics</h1>
          <p>
            Generated{' '}
            <time dateTime={latestGeneratedAt}>{formatDateTime(latestGeneratedAt)}</time>
          </p>
        </div>
        <button
          type="button"
          className="analytics-button analytics-button--secondary"
          disabled={summaryStatus === 'loading'}
          onClick={() => setRequestVersion((value) => value + 1)}
        >
          Refresh
        </button>
      </header>

      <AnalyticsFilters
        filters={filters}
        options={filterOptions}
        onApply={applyFilters}
      />

      {summaryStatus === 'loading' && <p role="status">Updating analytics…</p>}
      {summaryFailure && <p role="alert">{failureMessage(summaryFailure)}</p>}

      {partialMeasurements && (
        <div className="analytics-banner" role="status">
          Some measurements are unavailable or excluded. Missing values remain marked “Not
          available” and are not treated as zero.
        </div>
      )}

      {noSummaryData ? (
        <div className="analytics-empty-state" role="status">
          <h2>No analytics data</h2>
          <p>No aggregate records match the applied filters.</p>
        </div>
      ) : (
        <>
          <LearningSummary metrics={learning} />
          <EngagementFunnel stages={learning.funnel} />
          <ResearchSummary metrics={research} />
        </>
      )}

      <InactiveLearners
        page={inactivePage}
        loading={inactiveStatus === 'loading'}
        error={inactiveFailure ? failureMessage(inactiveFailure) : null}
        pageSize={pageSize}
        onPageChange={setPage}
        onPageSizeChange={(nextPageSize) => {
          setPageSize(Math.min(100, nextPageSize))
          setPage(1)
        }}
      />
      <ExportControls client={apiClient} filters={filters} />
    </section>
  )
}
