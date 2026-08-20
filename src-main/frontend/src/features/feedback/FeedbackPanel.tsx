import { useEffect, useId, useMemo, useState } from 'react'

import { createFeedbackApiClient, FeedbackApiError } from './api'
import { FeedbackMarkdown } from './FeedbackMarkdown'
import { FeedbackReportButton } from './FeedbackReportButton'
import { FeedbackSources } from './FeedbackSources'
import { FeedbackStatus } from './FeedbackStatus'
import { ImprovementActions } from './ImprovementActions'
import type { FeedbackApiClient, FeedbackWorkflowResponse } from './types'
import { Button, Tag, cx } from '../../components/ui'
import styles from './feedback.module.css'

type FeedbackPanelProps = {
  submissionId: string
  client?: FeedbackApiClient
  pollIntervalMs?: number
  maxPollingDurationMs?: number
}

const DEFAULT_MAX_POLLING_DURATION_MS = 330_000
const MIN_SERVER_RETRY_DELAY_MS = 250

const wait = (milliseconds: number, signal: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    const onAbort = () => {
      window.clearTimeout(timeout)
      reject(new DOMException('Aborted', 'AbortError'))
    }
    const timeout = window.setTimeout(() => {
      signal.removeEventListener('abort', onAbort)
      resolve()
    }, milliseconds)
    signal.addEventListener('abort', onAbort, { once: true })
  })

type RequestFailure =
  | 'offline'
  | 'timeout'
  | 'network'
  | 'invalid_response'
  | 'request_failed'
  | 'invalid_request'
  | 'polling_timeout'

function requestFailure(error: unknown): RequestFailure {
  if (error instanceof FeedbackApiError) return error.code
  return 'request_failed'
}

function requestFailureMessage(failure: RequestFailure): string {
  if (failure === 'offline') return 'You appear to be offline. Reconnect and try again.'
  if (failure === 'timeout' || failure === 'polling_timeout') {
    return 'Feedback is taking longer than expected. Try again.'
  }
  if (failure === 'network') {
    return 'Feedback could not be loaded. Check your connection and try again.'
  }
  if (failure === 'invalid_response') {
    return 'The feedback service returned an unexpected response. Try again.'
  }
  return 'Feedback could not be loaded.'
}

function isAbortError(error: unknown): boolean {
  return (
    typeof error === 'object' &&
    error !== null &&
    'name' in error &&
    error.name === 'AbortError'
  )
}

export function FeedbackPanel({
  submissionId,
  client,
  pollIntervalMs = 1_000,
  maxPollingDurationMs = DEFAULT_MAX_POLLING_DURATION_MS,
}: FeedbackPanelProps) {
  const apiClient = useMemo(() => client ?? createFeedbackApiClient(), [client])
  const [workflow, setWorkflow] = useState<FeedbackWorkflowResponse | null>(null)
  const [requestError, setRequestError] = useState<RequestFailure | null>(null)
  const [requestVersion, setRequestVersion] = useState(0)
  const headingId = useId()
  const identifiedErrorHeadingId = useId()
  const nextStepHeadingId = useId()

  useEffect(() => {
    const controller = new AbortController()

    async function load() {
      setRequestError(null)
      setWorkflow(null)
      const pollingDurationMs =
        Number.isFinite(maxPollingDurationMs) && maxPollingDurationMs > 0
          ? Math.min(maxPollingDurationMs, DEFAULT_MAX_POLLING_DURATION_MS)
          : DEFAULT_MAX_POLLING_DURATION_MS
      const deadline = performance.now() + pollingDurationMs
      try {
        let result = await apiClient.start(submissionId, controller.signal)
        let next = result.response
        if (!controller.signal.aborted) setWorkflow(next)
        while (next.status === 'processing' && !controller.signal.aborted) {
          const remainingMs = deadline - performance.now()
          if (remainingMs <= 0) {
            setRequestError('polling_timeout')
            return
          }
          const requestedDelay =
            result.retryAfterMs === null
              ? Math.max(1, pollIntervalMs)
              : Math.max(MIN_SERVER_RETRY_DELAY_MS, result.retryAfterMs)
          await wait(Math.min(requestedDelay, remainingMs), controller.signal)
          if (requestedDelay >= remainingMs || performance.now() >= deadline) {
            setRequestError('polling_timeout')
            return
          }
          result = await apiClient.get(submissionId, controller.signal)
          next = result.response
          if (!controller.signal.aborted) setWorkflow(next)
        }
      } catch (error) {
        if (!controller.signal.aborted && !isAbortError(error)) {
          setRequestError(requestFailure(error))
        }
      }
    }

    void load()
    return () => controller.abort()
  }, [apiClient, maxPollingDurationMs, pollIntervalMs, requestVersion, submissionId])

  if (requestError !== null) {
    return (
      <section className={cx('ll-root', styles.panel)} aria-labelledby={headingId}>
        <h2 id={headingId} className={styles.heading}>Feedback</h2>
        <p role="alert" className={styles.alert}>{requestFailureMessage(requestError)}</p>
        <div>
          <Button variant="secondary" onClick={() => setRequestVersion((value) => value + 1)}>
            Try again
          </Button>
        </div>
      </section>
    )
  }

  if (workflow === null || workflow.status === 'processing') {
    return (
      <section className={cx('ll-root', styles.panel)} aria-labelledby={headingId}>
        <h2 id={headingId} className={styles.heading}>Feedback</h2>
        <FeedbackStatus stage={workflow?.processing_stage} />
      </section>
    )
  }

  if (workflow.status === 'failed' || workflow.feedback === null) {
    const retryable = workflow.status === 'failed' && workflow.error?.retryable === true
    return (
      <section className={cx('ll-root', styles.panel, styles.fallback)} aria-labelledby={headingId}>
        <h2 id={headingId} className={styles.heading}>Feedback</h2>
        <p role="alert" className={styles.alert}>Feedback processing could not be completed.</p>
        {retryable && (
          <div>
            <Button variant="secondary" onClick={() => setRequestVersion((value) => value + 1)}>
              Retry feedback
            </Button>
          </div>
        )}
      </section>
    )
  }

  const feedback = workflow.feedback
  return (
    <section
      className={cx('ll-root', styles.panel, feedback.kind === 'safe_fallback' && styles.fallback)}
      data-kind={feedback.kind}
      aria-labelledby={headingId}
    >
      <h2 id={headingId} className={styles.heading}>
        {feedback.kind === 'safe_fallback' ? 'Feedback unavailable' : 'Your feedback'}
      </h2>
      <FeedbackMarkdown>{feedback.summary}</FeedbackMarkdown>
      {feedback.kind === 'validated' && feedback.identified_error && (
        <section aria-labelledby={identifiedErrorHeadingId}>
          <h3 id={identifiedErrorHeadingId}>What to revisit</h3>
          <FeedbackMarkdown>{feedback.identified_error}</FeedbackMarkdown>
        </section>
      )}
      {feedback.explanation && <FeedbackMarkdown>{feedback.explanation}</FeedbackMarkdown>}
      {feedback.kind === 'validated' && (
        <ImprovementActions actions={feedback.improvement_actions} />
      )}
      {feedback.recommended_next_step && (
        <section aria-labelledby={nextStepHeadingId}>
          <h3 id={nextStepHeadingId}>Recommended next step</h3>
          <FeedbackMarkdown>{feedback.recommended_next_step}</FeedbackMarkdown>
        </section>
      )}
      <FeedbackSources sources={feedback.sources} />
      {feedback.kind === 'validated' && (
        <p className={styles.notice}>
          <Tag>AI-generated</Tag>
          {feedback.ai_generated_notice}
        </p>
      )}
      <FeedbackReportButton feedbackId={feedback.feedback_id} client={apiClient} />
    </section>
  )
}
