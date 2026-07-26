import type {
  AnalyticsApiClient,
  AnalyticsFilterOptions,
  AnalyticsFilterSnapshot,
  AnalyticsFilterState,
  ConditionMetrics,
  ExperimentalCondition,
  FunnelEventType,
  FunnelStage,
  InactiveLearner,
  InactiveLearnerPage,
  LearningMetrics,
  MetricValue,
  PairedDifferences,
  ResearchExportFormat,
  ResearchMetrics,
} from './types'

const DEFAULT_TIMEOUT_MS = 30_000
const MAX_TEXT_LENGTH = 255
const MAX_OPTIONS = 1_000
const MAX_DATE_RANGE_MS = 365 * 24 * 60 * 60 * 1_000
const CONDITIONS = new Set<ExperimentalCondition>([
  'agentic_rag',
  'single_step_baseline',
])
const JUDGE_DECISIONS = new Set(['pass', 'fail'])
const FUNNEL_STAGES = new Set<FunnelEventType>([
  'task_view',
  'draft_save',
  'submission',
  'feedback_view',
  'completion',
])

export type AnalyticsApiErrorCode =
  | 'invalid_request'
  | 'permission'
  | 'offline'
  | 'timeout'
  | 'network'
  | 'invalid_response'
  | 'request_failed'

const ERROR_MESSAGES: Record<AnalyticsApiErrorCode, string> = {
  invalid_request: 'The analytics filters are invalid.',
  permission: 'You do not have permission to view these analytics.',
  offline: 'You appear to be offline. Reconnect and try again.',
  timeout: 'The analytics service took too long to respond. Try again.',
  network: 'Analytics could not be loaded. Check your connection and try again.',
  invalid_response: 'The analytics service returned an unexpected response. Try again.',
  request_failed: 'Analytics could not be loaded. Try again.',
}

export class AnalyticsApiError extends Error {
  readonly code: AnalyticsApiErrorCode
  readonly status: number | null

  constructor(code: AnalyticsApiErrorCode, status: number | null = null) {
    super(ERROR_MESSAGES[code])
    this.name = 'AnalyticsApiError'
    this.code = code
    this.status = status
  }
}

export type AnalyticsApiClientOptions = {
  apiBaseUrl?: string
  requestTimeoutMs?: number
  fetch?: typeof fetch
}

type JsonRecord = Record<string, unknown>

function invalidResponse(): never {
  throw new AnalyticsApiError('invalid_response')
}

function asRecord(value: unknown): JsonRecord {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    return invalidResponse()
  }
  return value as JsonRecord
}

function asString(value: unknown, maxLength = MAX_TEXT_LENGTH): string {
  if (
    typeof value !== 'string' ||
    value.trim().length === 0 ||
    value.length > maxLength
  ) {
    return invalidResponse()
  }
  return value
}

function asNullableDate(value: unknown): string | null {
  if (value === null) return null
  return asDate(value)
}

function asDate(value: unknown): string {
  const date = asString(value)
  if (Number.isNaN(Date.parse(date))) return invalidResponse()
  return date
}

function asNonNegativeInteger(value: unknown): number {
  if (!Number.isInteger(value) || (value as number) < 0) return invalidResponse()
  return value as number
}

function asFiniteNumber(value: unknown): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) return invalidResponse()
  return value
}

function asMetric(value: unknown): MetricValue {
  const metric = asRecord(value)
  const resolved =
    metric.value === null ? null : asFiniteNumber(metric.value)
  return {
    value: resolved,
    numerator: asFiniteNumber(metric.numerator),
    denominator: asNonNegativeInteger(metric.denominator),
    sample_size: asNonNegativeInteger(metric.sample_size),
    unit: asString(metric.unit),
  }
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value) || value.length > MAX_OPTIONS) return invalidResponse()
  return value.map((item) => asString(item))
}

function asConditions(value: unknown): ExperimentalCondition[] {
  const values = asStringArray(value)
  if (!values.every((item) => CONDITIONS.has(item as ExperimentalCondition))) {
    return invalidResponse()
  }
  return values as ExperimentalCondition[]
}

function asFilterSnapshot(value: unknown): AnalyticsFilterSnapshot {
  const filters = asRecord(value)
  return {
    course_ids: asStringArray(filters.course_ids),
    start_at: asNullableDate(filters.start_at),
    end_at: asNullableDate(filters.end_at),
    experimental_conditions: asConditions(filters.experimental_conditions),
    task_types: asStringArray(filters.task_types),
    models: asStringArray(filters.models),
    judge_decisions: asStringArray(filters.judge_decisions),
  }
}

function asInactiveLearner(value: unknown): InactiveLearner {
  const learner = asRecord(value)
  return {
    pseudonymous_user_id: asString(learner.pseudonymous_user_id),
    last_activity_at: asNullableDate(learner.last_activity_at),
  }
}

function asInactiveLearners(value: unknown): InactiveLearner[] {
  if (!Array.isArray(value) || value.length > 100) return invalidResponse()
  return value.map(asInactiveLearner)
}

function asFunnel(value: unknown): FunnelStage[] {
  if (!Array.isArray(value) || value.length > FUNNEL_STAGES.size) return invalidResponse()
  return value.map((item) => {
    const stage = asRecord(item)
    if (
      typeof stage.event_type !== 'string' ||
      !FUNNEL_STAGES.has(stage.event_type as FunnelEventType)
    ) {
      return invalidResponse()
    }
    return {
      event_type: stage.event_type as FunnelEventType,
      count: asNonNegativeInteger(stage.count),
      previous_stage_rate: asMetric(stage.previous_stage_rate),
    }
  })
}

function asLearningMetrics(value: unknown): LearningMetrics {
  const metrics = asRecord(value)
  if (metrics.schema_version !== 'learning-metrics-v1') return invalidResponse()
  return {
    schema_version: 'learning-metrics-v1',
    filters: asFilterSnapshot(metrics.filters),
    generated_at: asDate(metrics.generated_at),
    task_views: asMetric(metrics.task_views),
    unique_task_views: asMetric(metrics.unique_task_views),
    submissions: asMetric(metrics.submissions),
    unique_submissions: asMetric(metrics.unique_submissions),
    completion_rate: asMetric(metrics.completion_rate),
    average_score: asMetric(metrics.average_score),
    total_attempts: asMetric(metrics.total_attempts),
    average_attempts: asMetric(metrics.average_attempts),
    feedback_view_rate: asMetric(metrics.feedback_view_rate),
    funnel: asFunnel(metrics.funnel),
    inactive_learner_count: asMetric(metrics.inactive_learner_count),
    excluded_incomplete_count: asNonNegativeInteger(metrics.excluded_incomplete_count),
  }
}

function asConditionMetrics(value: unknown): ConditionMetrics {
  const metrics = asRecord(value)
  return {
    hallucination_rate: asMetric(metrics.hallucination_rate),
    overall_pass_rate: asMetric(metrics.overall_pass_rate),
    average_relevance: asMetric(metrics.average_relevance),
    average_latency_ms: asMetric(metrics.average_latency_ms),
    p95_latency_ms: asMetric(metrics.p95_latency_ms),
    average_total_tokens: asMetric(metrics.average_total_tokens),
    average_cost: asMetric(metrics.average_cost),
    fallback_rate: asMetric(metrics.fallback_rate),
  }
}

function asPairedDifferences(value: unknown): PairedDifferences {
  const metrics = asRecord(value)
  return {
    pass_rate: asMetric(metrics.pass_rate),
    relevance: asMetric(metrics.relevance),
    latency_ms: asMetric(metrics.latency_ms),
    total_tokens: asMetric(metrics.total_tokens),
    cost: asMetric(metrics.cost),
  }
}

function asResearchMetrics(value: unknown): ResearchMetrics {
  const metrics = asRecord(value)
  const byCondition = asRecord(metrics.by_condition)
  if (metrics.schema_version !== 'research-metrics-v1') return invalidResponse()
  return {
    schema_version: 'research-metrics-v1',
    filters: asFilterSnapshot(metrics.filters),
    generated_at: asDate(metrics.generated_at),
    retrieval_threshold: asFiniteNumber(metrics.retrieval_threshold),
    retrieval_threshold_version: asString(metrics.retrieval_threshold_version),
    by_condition: {
      agentic_rag: asConditionMetrics(byCondition.agentic_rag),
      single_step_baseline: asConditionMetrics(byCondition.single_step_baseline),
    },
    first_pass_rate: asMetric(metrics.first_pass_rate),
    regeneration_success_rate: asMetric(metrics.regeneration_success_rate),
    retrieval_hit_rate: asMetric(metrics.retrieval_hit_rate),
    paired_agentic_minus_baseline: asPairedDifferences(
      metrics.paired_agentic_minus_baseline,
    ),
    excluded_incomplete_count: asNonNegativeInteger(metrics.excluded_incomplete_count),
  }
}

function asFilterOptions(value: unknown): AnalyticsFilterOptions {
  const options = asRecord(value)
  const decisions = asStringArray(options.judge_decisions)
  if (!decisions.every((decision) => JUDGE_DECISIONS.has(decision))) {
    return invalidResponse()
  }
  return {
    schema_version: asString(options.schema_version),
    generated_at: asDate(options.generated_at),
    courses: asStringArray(options.courses),
    task_types: asStringArray(options.task_types),
    models: asStringArray(options.models),
    experimental_conditions: asConditions(options.experimental_conditions),
    judge_decisions: decisions as AnalyticsFilterOptions['judge_decisions'],
  }
}

function asInactivePage(value: unknown): InactiveLearnerPage {
  const page = asRecord(value)
  if (page.schema_version !== 'inactive-learners-v1') return invalidResponse()
  const pageNumber = asNonNegativeInteger(page.page)
  const pageSize = asNonNegativeInteger(page.page_size)
  if (pageNumber < 1 || pageSize < 1 || pageSize > 100) return invalidResponse()
  const items = asInactiveLearners(page.items)
  const total = asNonNegativeInteger(page.total)
  const inactiveLearnerCount = asMetric(page.inactive_learner_count)
  if (
    items.length > pageSize ||
    items.length > total ||
    inactiveLearnerCount.unit !== 'learners' ||
    inactiveLearnerCount.value !== total ||
    inactiveLearnerCount.numerator !== total
  ) {
    return invalidResponse()
  }
  return {
    schema_version: 'inactive-learners-v1',
    filters: asFilterSnapshot(page.filters),
    generated_at: asDate(page.generated_at),
    inactive_learner_count: inactiveLearnerCount,
    excluded_incomplete_count: asNonNegativeInteger(
      page.excluded_incomplete_count,
    ),
    items,
    page: pageNumber,
    page_size: pageSize,
    total,
  }
}

function utcDate(value: string): string {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    throw new AnalyticsApiError('invalid_request')
  }
  const timestamp = `${value}T00:00:00.000Z`
  if (Number.isNaN(Date.parse(timestamp))) {
    throw new AnalyticsApiError('invalid_request')
  }
  return timestamp
}

export function serializeAnalyticsFilters(
  filters: AnalyticsFilterState,
): URLSearchParams {
  const dateFrom = utcDate(filters.dateFrom)
  const dateTo = utcDate(filters.dateTo)
  if (
    dateFrom >= dateTo ||
    Date.parse(dateTo) - Date.parse(dateFrom) > MAX_DATE_RANGE_MS
  ) {
    throw new AnalyticsApiError('invalid_request')
  }
  const query = new URLSearchParams()
  if (filters.courseId) query.set('course_id', filters.courseId)
  query.set('date_from', dateFrom)
  query.set('date_to', dateTo)
  if (filters.experimentalCondition) {
    query.set('experimental_condition', filters.experimentalCondition)
  }
  if (filters.taskType) query.set('task_type', filters.taskType)
  if (filters.model) query.set('model', filters.model)
  if (filters.judgeDecision) query.set('judge_decision', filters.judgeDecision)
  return query
}

function isOffline(): boolean {
  return typeof navigator !== 'undefined' && navigator.onLine === false
}

function aborted(): DOMException {
  return new DOMException('Aborted', 'AbortError')
}

async function requestJson<T>(
  url: string,
  signal: AbortSignal | undefined,
  validate: (value: unknown) => T,
  options: { fetch: typeof fetch; timeoutMs: number },
): Promise<T> {
  if (isOffline()) throw new AnalyticsApiError('offline')
  if (signal?.aborted) throw aborted()

  const controller = new AbortController()
  let timedOut = false
  const onAbort = () => controller.abort()
  signal?.addEventListener('abort', onAbort, { once: true })
  const timeout = globalThis.setTimeout(() => {
    timedOut = true
    controller.abort()
  }, options.timeoutMs)

  try {
    const response = await options.fetch(url, {
      method: 'GET',
      credentials: 'include',
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    })
    if (!response.ok) {
      const code = response.status === 401 || response.status === 403
        ? 'permission'
        : 'request_failed'
      throw new AnalyticsApiError(code, response.status)
    }
    let body: unknown
    try {
      body = await response.json()
    } catch {
      throw new AnalyticsApiError('invalid_response')
    }
    return validate(body)
  } catch (error) {
    if (error instanceof AnalyticsApiError) throw error
    if (signal?.aborted) throw aborted()
    if (timedOut) throw new AnalyticsApiError('timeout')
    if (isOffline()) throw new AnalyticsApiError('offline')
    throw new AnalyticsApiError('network')
  } finally {
    globalThis.clearTimeout(timeout)
    signal?.removeEventListener('abort', onAbort)
  }
}

function normalizedBaseUrl(value: string | undefined): string {
  const fallback = '/api/v1'
  return (value?.trim() || fallback).replace(/\/+$/, '') || fallback
}

export function createAnalyticsApiClient(
  options: AnalyticsApiClientOptions = {},
): AnalyticsApiClient {
  const apiBaseUrl = normalizedBaseUrl(
    options.apiBaseUrl ?? import.meta.env.VITE_API_BASE_URL,
  )
  const timeoutMs = options.requestTimeoutMs ?? DEFAULT_TIMEOUT_MS
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    throw new AnalyticsApiError('invalid_request')
  }
  const requestOptions = {
    fetch: options.fetch ?? globalThis.fetch.bind(globalThis),
    timeoutMs,
  }

  const analyticsUrl = (
    path: string,
    filters?: AnalyticsFilterState,
    extras?: Record<string, string>,
  ) => {
    const query = filters ? serializeAnalyticsFilters(filters) : new URLSearchParams()
    for (const [key, value] of Object.entries(extras ?? {})) query.set(key, value)
    const suffix = query.size ? `?${query.toString()}` : ''
    return `${apiBaseUrl}${path}${suffix}`
  }

  return {
    getLearning(filters, signal) {
      return requestJson(
        analyticsUrl('/analytics/learning', filters),
        signal,
        asLearningMetrics,
        requestOptions,
      )
    },
    getResearch(filters, signal) {
      return requestJson(
        analyticsUrl('/analytics/research', filters),
        signal,
        asResearchMetrics,
        requestOptions,
      )
    },
    getFilterOptions(signal) {
      return requestJson(
        analyticsUrl('/analytics/filter-options'),
        signal,
        asFilterOptions,
        requestOptions,
      )
    },
    getInactiveLearners(filters, page, pageSize, signal) {
      if (
        !Number.isInteger(page) ||
        page < 1 ||
        !Number.isInteger(pageSize) ||
        pageSize < 1 ||
        pageSize > 100
      ) {
        return Promise.reject(new AnalyticsApiError('invalid_request'))
      }
      return requestJson(
        analyticsUrl('/analytics/inactive-learners', filters, {
          page: String(page),
          page_size: String(pageSize),
        }),
        signal,
        asInactivePage,
        requestOptions,
      )
    },
    researchExportUrl(format: ResearchExportFormat, filters: AnalyticsFilterState) {
      return analyticsUrl('/research/exports', filters, { format })
    },
  }
}
