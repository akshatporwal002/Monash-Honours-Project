import type {
  FeedbackApiClient,
  FeedbackProcessingStage,
  FeedbackReportCategory,
  FeedbackReportInput,
  FeedbackReportResponse,
  FeedbackSource,
  FeedbackWorkflowResponse,
  SafeFallbackFeedback,
  ValidatedFeedback,
} from './types'

const DEFAULT_REQUEST_TIMEOUT_MS = 60_000
const MAX_IDENTIFIER_LENGTH = 255
const MAX_CONTENT_LENGTH = 20_000
const MAX_LIST_LENGTH = 100

export type FeedbackApiErrorCode =
  | 'invalid_request'
  | 'offline'
  | 'timeout'
  | 'network'
  | 'invalid_response'
  | 'request_failed'

const ERROR_MESSAGES: Record<FeedbackApiErrorCode, string> = {
  invalid_request: 'The feedback request is invalid.',
  offline: 'You appear to be offline. Reconnect and try again.',
  timeout: 'The feedback service took too long to respond. Try again.',
  network: 'Feedback could not be loaded. Check your connection and try again.',
  invalid_response: 'The feedback service returned an unexpected response. Try again.',
  request_failed: 'Feedback could not be loaded. Try again.',
}

export class FeedbackApiError extends Error {
  readonly code: FeedbackApiErrorCode
  readonly status: number | null

  constructor(code: FeedbackApiErrorCode = 'request_failed', status: number | null = null) {
    super(ERROR_MESSAGES[code])
    this.name = 'FeedbackApiError'
    this.code = code
    this.status = status
  }
}

export type FeedbackApiClientOptions = {
  apiBaseUrl?: string
  requestTimeoutMs?: number
  getCsrfToken?: () => string | null | undefined
  fetch?: typeof fetch
}

type JsonRecord = Record<string, unknown>

function invalidResponse(): never {
  throw new FeedbackApiError('invalid_response')
}

function asRecord(value: unknown): JsonRecord {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    return invalidResponse()
  }
  return value as JsonRecord
}

function asText(value: unknown, nullable = false): string | null {
  if (nullable && value === null) return null
  if (typeof value !== 'string' || value.length === 0 || value.length > MAX_CONTENT_LENGTH) {
    return invalidResponse()
  }
  return value
}

function asIdentifier(value: unknown): string {
  if (
    typeof value !== 'string' ||
    value.trim().length === 0 ||
    value.length > MAX_IDENTIFIER_LENGTH
  ) {
    return invalidResponse()
  }
  return value
}

function asStringList(value: unknown): string[] {
  if (!Array.isArray(value) || value.length > MAX_LIST_LENGTH) return invalidResponse()
  return value.map((item) => asText(item) as string)
}

function asIdentifierList(value: unknown): string[] {
  if (!Array.isArray(value) || value.length > MAX_LIST_LENGTH) return invalidResponse()
  return value.map(asIdentifier)
}

function asSources(value: unknown): FeedbackSource[] {
  if (!Array.isArray(value) || value.length > MAX_LIST_LENGTH) return invalidResponse()
  return value.map((item) => {
    const source = asRecord(item)
    return {
      source_id: asIdentifier(source.source_id),
      label: asText(source.label) as string,
    }
  })
}

function asValidatedFeedback(value: unknown): ValidatedFeedback {
  const feedback = asRecord(value)
  const classification = feedback.response_classification
  if (
    classification !== null &&
    classification !== 'correct' &&
    classification !== 'partially_correct' &&
    classification !== 'incorrect'
  ) {
    return invalidResponse()
  }
  if (feedback.kind !== 'validated') return invalidResponse()

  return {
    kind: 'validated',
    feedback_id: asIdentifier(feedback.feedback_id),
    response_classification: classification,
    summary: asText(feedback.summary) as string,
    identified_error: asText(feedback.identified_error, true),
    explanation: asText(feedback.explanation, true),
    improvement_actions: asStringList(feedback.improvement_actions),
    recommended_next_step: asText(feedback.recommended_next_step, true),
    sources: asSources(feedback.sources),
    simulation_references: asIdentifierList(feedback.simulation_references),
    ai_generated_notice: asText(feedback.ai_generated_notice) as string,
  }
}

function asFallbackFeedback(value: unknown): SafeFallbackFeedback {
  const feedback = asRecord(value)
  if (feedback.kind !== 'safe_fallback') return invalidResponse()

  return {
    kind: 'safe_fallback',
    feedback_id: asIdentifier(feedback.feedback_id),
    summary: asText(feedback.summary) as string,
    explanation: asText(feedback.explanation) as string,
    recommended_next_step: asText(feedback.recommended_next_step) as string,
    sources: asSources(feedback.sources),
    simulation_references: asIdentifierList(feedback.simulation_references),
  }
}

const PROCESSING_STAGES = new Set<FeedbackProcessingStage>([
  'pending',
  'context_collection',
  'generating',
  'judging',
  'regenerating',
])

function asProcessingStage(value: unknown): FeedbackProcessingStage {
  if (typeof value !== 'string' || !PROCESSING_STAGES.has(value as FeedbackProcessingStage)) {
    return invalidResponse()
  }
  return value as FeedbackProcessingStage
}

function asFeedbackWorkflow(value: unknown): FeedbackWorkflowResponse {
  const workflow = asRecord(value)
  const workflow_run_id = asIdentifier(workflow.workflow_run_id)
  const submission_id = asIdentifier(workflow.submission_id)

  if (workflow.status === 'processing') {
    if (workflow.feedback !== null || workflow.error !== null) return invalidResponse()
    return {
      workflow_run_id,
      submission_id,
      status: 'processing',
      processing_stage: asProcessingStage(workflow.processing_stage),
      feedback: null,
      error: null,
    }
  }

  if (workflow.status === 'validated') {
    if (workflow.processing_stage !== null || workflow.error !== null) return invalidResponse()
    return {
      workflow_run_id,
      submission_id,
      status: 'validated',
      processing_stage: null,
      feedback: asValidatedFeedback(workflow.feedback),
      error: null,
    }
  }

  if (workflow.status === 'fallback') {
    if (workflow.processing_stage !== null || workflow.error !== null) return invalidResponse()
    return {
      workflow_run_id,
      submission_id,
      status: 'fallback',
      processing_stage: null,
      feedback: asFallbackFeedback(workflow.feedback),
      error: null,
    }
  }

  if (workflow.status === 'failed') {
    const error = asRecord(workflow.error)
    if (
      workflow.processing_stage !== null ||
      workflow.feedback !== null ||
      error.code !== 'feedback_processing_failed' ||
      error.message !== 'Feedback processing could not be completed.' ||
      typeof error.retryable !== 'boolean'
    ) {
      return invalidResponse()
    }
    return {
      workflow_run_id,
      submission_id,
      status: 'failed',
      processing_stage: null,
      feedback: null,
      error: {
        code: 'feedback_processing_failed',
        message: 'Feedback processing could not be completed.',
        retryable: error.retryable,
      },
    }
  }

  return invalidResponse()
}

function asReportResponse(value: unknown): FeedbackReportResponse {
  const report = asRecord(value)
  if (report.status !== 'received') return invalidResponse()
  return {
    report_id: asIdentifier(report.report_id),
    status: 'received',
  }
}

function assertExternalId(value: string): void {
  if (value.trim().length === 0 || value.length > MAX_IDENTIFIER_LENGTH) {
    throw new FeedbackApiError('invalid_request')
  }
}

const REPORT_CATEGORIES = new Set<FeedbackReportCategory>([
  'incorrect',
  'unsafe',
  'unclear',
  'citation_issue',
  'other',
])

function assertReport(report: FeedbackReportInput): void {
  if (
    !REPORT_CATEGORIES.has(report.category) ||
    (report.note !== undefined &&
      (report.note.trim().length === 0 || report.note.length > 2_000))
  ) {
    throw new FeedbackApiError('invalid_request')
  }
}

function parseRetryAfter(value: string | null): number | null {
  if (value === null) return null
  const seconds = Number(value)
  if (Number.isFinite(seconds) && seconds >= 0) {
    return Math.ceil(seconds * 1_000)
  }
  const timestamp = Date.parse(value)
  if (Number.isNaN(timestamp)) return null
  return Math.max(0, timestamp - Date.now())
}

function normalizedBaseUrl(value: string | undefined): string {
  const fallback = '/api/v1'
  const normalized = (value?.trim() || fallback).replace(/\/+$/, '')
  return normalized || fallback
}

function isOffline(): boolean {
  return typeof navigator !== 'undefined' && navigator.onLine === false
}

function aborted(): DOMException {
  return new DOMException('Aborted', 'AbortError')
}

type RequestResult<T> = {
  data: T
  response: Response
}

async function requestJson<T>(
  url: string,
  init: RequestInit,
  validate: (value: unknown) => T,
  options: {
    fetch: typeof fetch
    requestTimeoutMs: number
    getCsrfToken?: () => string | null | undefined
  },
): Promise<RequestResult<T>> {
  if (isOffline()) throw new FeedbackApiError('offline')

  const controller = new AbortController()
  let timedOut = false
  const onAbort = () => controller.abort()
  if (init.signal?.aborted) throw aborted()
  init.signal?.addEventListener('abort', onAbort, { once: true })
  const timeout = globalThis.setTimeout(() => {
    timedOut = true
    controller.abort()
  }, options.requestTimeoutMs)

  try {
    const headers = new Headers(init.headers)
    if (init.body !== undefined && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json')
    }
    if (init.method !== undefined && !['GET', 'HEAD'].includes(init.method.toUpperCase())) {
      let csrfToken: string | null | undefined
      try {
        csrfToken = options.getCsrfToken?.()
      } catch {
        throw new FeedbackApiError('invalid_request')
      }
      if (csrfToken) {
        if (csrfToken.length > 4_096) throw new FeedbackApiError('invalid_request')
        headers.set('X-CSRF-Token', csrfToken)
      }
    }

    const response = await options.fetch(url, {
      ...init,
      credentials: 'include',
      headers,
      signal: controller.signal,
    })
    if (!response.ok) {
      throw new FeedbackApiError('request_failed', response.status)
    }

    let body: unknown
    try {
      body = await response.json()
    } catch {
      throw new FeedbackApiError('invalid_response')
    }
    return { data: validate(body), response }
  } catch (error) {
    if (error instanceof FeedbackApiError) throw error
    if (init.signal?.aborted) throw aborted()
    if (timedOut) throw new FeedbackApiError('timeout')
    if (isOffline()) throw new FeedbackApiError('offline')
    throw new FeedbackApiError('network')
  } finally {
    globalThis.clearTimeout(timeout)
    init.signal?.removeEventListener('abort', onAbort)
  }
}

export function createFeedbackApiClient(
  optionsOrBaseUrl: FeedbackApiClientOptions | string = {},
): FeedbackApiClient {
  const options =
    typeof optionsOrBaseUrl === 'string'
      ? { apiBaseUrl: optionsOrBaseUrl }
      : optionsOrBaseUrl
  const apiBaseUrl = normalizedBaseUrl(
    options.apiBaseUrl ?? import.meta.env.VITE_API_BASE_URL,
  )
  const requestTimeoutMs = options.requestTimeoutMs ?? DEFAULT_REQUEST_TIMEOUT_MS
  if (!Number.isFinite(requestTimeoutMs) || requestTimeoutMs <= 0) {
    throw new FeedbackApiError('invalid_request')
  }
  const fetchImplementation = options.fetch ?? globalThis.fetch.bind(globalThis)
  const requestOptions = {
    fetch: fetchImplementation,
    requestTimeoutMs,
    getCsrfToken: options.getCsrfToken,
  }

  async function workflowRequest(
    submissionId: string,
    method: 'GET' | 'POST',
    signal?: AbortSignal,
  ) {
    assertExternalId(submissionId)
    const result = await requestJson(
      `${apiBaseUrl}/submissions/${encodeURIComponent(submissionId)}/feedback`,
      { method, signal },
      asFeedbackWorkflow,
      requestOptions,
    )
    return {
      response: result.data,
      retryAfterMs: parseRetryAfter(result.response.headers.get('Retry-After')),
    }
  }

  return {
    start(submissionId, signal) {
      return workflowRequest(submissionId, 'POST', signal)
    },
    get(submissionId, signal) {
      return workflowRequest(submissionId, 'GET', signal)
    },
    async report(feedbackId, report, signal) {
      assertExternalId(feedbackId)
      assertReport(report)
      const result = await requestJson(
        `${apiBaseUrl}/feedback/${encodeURIComponent(feedbackId)}/report`,
        { method: 'POST', body: JSON.stringify(report), signal },
        asReportResponse,
        requestOptions,
      )
      return result.data
    },
  }
}
