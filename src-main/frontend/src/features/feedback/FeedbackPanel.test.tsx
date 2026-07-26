import axe from 'axe-core'
import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'

import { FeedbackApiError } from './api'
import { FeedbackPanel } from './FeedbackPanel'
import type {
  FeedbackApiClient,
  FeedbackReportInput,
  FeedbackReportResponse,
  FeedbackWorkflowResponse,
  FeedbackWorkflowResult,
} from './types'

const processing = (): FeedbackWorkflowResponse => ({
  workflow_run_id: 'workflow-1',
  submission_id: 'submission-1',
  status: 'processing',
  processing_stage: 'generating',
  feedback: null,
  error: null,
})

const validated = (): FeedbackWorkflowResponse => ({
  workflow_run_id: 'workflow-1',
  submission_id: 'submission-1',
  status: 'validated',
  processing_stage: null,
  error: null,
  feedback: {
    kind: 'validated',
    feedback_id: 'feedback-1',
    response_classification: 'partially_correct',
    summary: 'Your explanation has a useful start.',
    identified_error: 'Measurement is missing.',
    explanation: 'Preserve this code:\n\n```python\nstate = measure(qubit)\n```',
    improvement_actions: ['Explain what measurement does.'],
    recommended_next_step: 'Review **measurement**.',
    sources: [{ source_id: 'source-1', label: 'Week 2 course notes' }],
    simulation_references: [],
    ai_generated_notice: 'AI-generated feedback. Verify important details and report any concerns.',
  },
})

const fallback = (): FeedbackWorkflowResponse => ({
  workflow_run_id: 'workflow-1',
  submission_id: 'submission-1',
  status: 'fallback',
  processing_stage: null,
  error: null,
  feedback: {
    kind: 'safe_fallback',
    feedback_id: 'feedback-1',
    summary: 'Personalized feedback is temporarily unavailable.',
    explanation: 'No feedback passed validation.',
    recommended_next_step: 'Review course material or ask an educator.',
    sources: [],
    simulation_references: [],
  },
})

const failed = (): FeedbackWorkflowResponse => ({
  workflow_run_id: 'workflow-1',
  submission_id: 'submission-1',
  status: 'failed',
  processing_stage: null,
  feedback: null,
  error: {
    code: 'feedback_processing_failed',
    message: 'Feedback processing could not be completed.',
    retryable: true,
  },
})

const result = (
  response: FeedbackWorkflowResponse,
  retryAfterMs: number | null = null,
): FeedbackWorkflowResult => ({ response, retryAfterMs })

class FakeClient implements FeedbackApiClient {
  starts: Array<FeedbackWorkflowResult | Error>
  gets: FeedbackWorkflowResult[]
  reports: FeedbackReportInput[] = []
  getCalls = 0

  constructor(
    starts: Array<FeedbackWorkflowResult | Error>,
    gets: FeedbackWorkflowResult[] = [],
  ) {
    this.starts = [...starts]
    this.gets = [...gets]
  }

  async start(): Promise<FeedbackWorkflowResult> {
    const next = this.starts.shift()
    if (next instanceof Error) throw next
    if (!next) throw new Error('No start response configured')
    return next
  }

  async get(): Promise<FeedbackWorkflowResult> {
    this.getCalls += 1
    const next = this.gets.shift()
    if (!next) throw new Error('No poll response configured')
    return next
  }

  async report(
    feedbackId: string,
    report: FeedbackReportInput,
  ): Promise<FeedbackReportResponse> {
    this.reports.push(report)
    return { report_id: `${feedbackId}-report`, status: 'received' }
  }
}

afterEach(() => {
  vi.useRealTimers()
})

test('polls processing feedback and renders sources, actions, safe markdown, and notice', async () => {
  const client = new FakeClient([result(processing())], [result(validated())])
  const { container } = render(
    <FeedbackPanel submissionId="submission-1" client={client} pollIntervalMs={1} />,
  )

  expect(screen.getByRole('status')).toHaveTextContent('Preparing your feedback')
  expect(await screen.findByText('Your explanation has a useful start.')).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Ways to improve' })).toBeInTheDocument()
  expect(screen.getByText('Week 2 course notes')).toBeInTheDocument()
  expect(screen.getByText('state = measure(qubit)')).toBeInTheDocument()
  expect(screen.getByText(/AI-generated feedback/)).toBeInTheDocument()
  expect((await axe.run(container)).violations).toEqual([])
})

test('honors Retry-After before polling', async () => {
  vi.useFakeTimers()
  const client = new FakeClient([result(processing(), 500)], [result(validated())])
  render(<FeedbackPanel submissionId="submission-1" client={client} pollIntervalMs={1} />)

  await act(async () => undefined)
  await act(async () => vi.advanceTimersByTimeAsync(499))
  expect(client.getCalls).toBe(0)

  await act(async () => vi.advanceTimersByTimeAsync(1))
  expect(client.getCalls).toBe(1)
  expect(screen.getByText('Your explanation has a useful start.')).toBeInTheDocument()
})

test('stops polling after the bounded workflow window', async () => {
  const client = new FakeClient([result(processing())])
  render(
    <FeedbackPanel
      submissionId="submission-1"
      client={client}
      pollIntervalMs={10}
      maxPollingDurationMs={1}
    />,
  )

  expect(await screen.findByRole('alert')).toHaveTextContent('taking longer than expected')
  expect(client.getCalls).toBe(0)
})

test('aborts obsolete and unmounted requests', async () => {
  const abortedSubmissionIds: string[] = []
  const hangingClient: FeedbackApiClient = {
    start(submissionId, signal) {
      return new Promise((_resolve, reject) => {
        signal?.addEventListener(
          'abort',
          () => {
            abortedSubmissionIds.push(submissionId)
            reject(new DOMException('Aborted', 'AbortError'))
          },
          { once: true },
        )
      })
    },
    async get() {
      throw new Error('Unexpected poll')
    },
    async report() {
      return { report_id: 'report-1', status: 'received' }
    },
  }
  const view = render(
    <FeedbackPanel submissionId="submission-1" client={hangingClient} />,
  )

  view.rerender(<FeedbackPanel submissionId="submission-2" client={hangingClient} />)
  await waitFor(() => expect(abortedSubmissionIds).toContain('submission-1'))
  view.unmount()
  await waitFor(() => expect(abortedSubmissionIds).toContain('submission-2'))
})

test('renders distinct ids for multiple instances and has no detectable accessibility violations', async () => {
  const firstClient = new FakeClient([result(validated())])
  const secondClient = new FakeClient([result(validated())])
  const { container } = render(
    <>
      <FeedbackPanel submissionId="submission-1" client={firstClient} />
      <FeedbackPanel submissionId="submission-2" client={secondClient} />
    </>,
  )

  expect(await screen.findAllByText('Your explanation has a useful start.')).toHaveLength(2)
  const ids = [...container.querySelectorAll<HTMLElement>('[id]')].map((element) => element.id)
  expect(new Set(ids).size).toBe(ids.length)
})

test('does not render hostile raw HTML or unsafe Markdown links', async () => {
  const hostile = validated()
  if (hostile.feedback?.kind !== 'validated') throw new Error('Invalid fixture')
  hostile.feedback.summary =
    '<img src=x onerror="alert(1)"><script>alert(2)</script>[unsafe](javascript:alert(3))'
  const { container } = render(
    <FeedbackPanel
      submissionId="submission-1"
      client={new FakeClient([result(hostile)])}
    />,
  )

  expect(await screen.findByText('unsafe')).toBeInTheDocument()
  expect(container.querySelector('img')).not.toBeInTheDocument()
  expect(container.querySelector('script')).not.toBeInTheDocument()
  expect(container.querySelector('a[href^="javascript:"]')).not.toBeInTheDocument()
})

test('renders the non-assessing fallback without sources or an AI notice', async () => {
  render(
    <FeedbackPanel
      submissionId="submission-1"
      client={new FakeClient([result(fallback())])}
    />,
  )

  expect(await screen.findByText('Personalized feedback is temporarily unavailable.')).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Sources' })).not.toBeInTheDocument()
  expect(screen.queryByText(/AI-generated feedback/)).not.toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Ways to improve' })).not.toBeInTheDocument()
})

test('retries failed processing and sanitizes unknown request errors', async () => {
  const user = userEvent.setup()
  const client = new FakeClient([
    result(failed()),
    new Error('private provider error'),
    result(validated()),
  ])
  render(<FeedbackPanel submissionId="submission-1" client={client} />)

  await user.click(await screen.findByRole('button', { name: 'Retry feedback' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Feedback could not be loaded.')
  expect(screen.queryByText(/private provider error/)).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Try again' }))

  expect(await screen.findByText('Your explanation has a useful start.')).toBeInTheDocument()
})

test('does not offer a retry for a terminal non-retryable failure', async () => {
  const response = failed()
  if (response.error === null) throw new Error('test fixture must contain an error')
  response.error.retryable = false

  render(
    <FeedbackPanel
      submissionId="submission-1"
      client={new FakeClient([result(response)])}
    />,
  )

  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Feedback processing could not be completed.',
  )
  expect(
    screen.queryByRole('button', { name: 'Retry feedback' }),
  ).not.toBeInTheDocument()
})

test.each([
  ['offline', 'offline'],
  ['timeout', 'taking longer'],
  ['network', 'Check your connection'],
] as const)('renders the %s request state', async (code, message) => {
  const client = new FakeClient([new FeedbackApiError(code)])
  render(<FeedbackPanel submissionId="submission-1" client={client} />)

  expect(await screen.findByRole('alert')).toHaveTextContent(message)
})

test('submits an accessible keyboard-operated concern report', async () => {
  const user = userEvent.setup()
  const client = new FakeClient([result(validated())])
  const { container } = render(
    <FeedbackPanel submissionId="submission-1" client={client} />,
  )

  const reportButton = await screen.findByRole('button', { name: 'Report a concern' })
  reportButton.focus()
  await user.keyboard('{Enter}')
  await user.selectOptions(screen.getByLabelText('Concern'), 'citation_issue')
  await user.type(screen.getByLabelText('Additional details (optional)'), 'Wrong source.')
  await user.click(screen.getByRole('button', { name: 'Send report' }))

  expect(await screen.findByRole('status')).toHaveTextContent('concern has been received')
  expect(client.reports).toEqual([
    { category: 'citation_issue', note: 'Wrong source.' },
  ])
  await waitFor(async () => {
    expect((await axe.run(container)).violations).toEqual([])
  })
})
