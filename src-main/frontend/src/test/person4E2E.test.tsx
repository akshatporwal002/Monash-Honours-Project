import axe from 'axe-core'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'

import App from '../App'
import { AnalyticsDashboard } from '../features/analytics/AnalyticsDashboard'
import {
  FILTER_OPTIONS,
  FILTERS,
  inactivePage,
  learningMetrics,
  researchMetrics,
} from '../features/analytics/testFixtures'
import type { AnalyticsApiClient } from '../features/analytics/types'
import { FeedbackPanel } from '../features/feedback/FeedbackPanel'
import type {
  FeedbackApiClient,
  FeedbackReportInput,
  FeedbackWorkflowResponse,
} from '../features/feedback/types'

const processing: FeedbackWorkflowResponse = {
  workflow_run_id: 'workflow-e2e',
  submission_id: 'submission-e2e',
  status: 'processing',
  processing_stage: 'generating',
  feedback: null,
  error: null,
}

const terminal: FeedbackWorkflowResponse = {
  workflow_run_id: 'workflow-e2e',
  submission_id: 'submission-e2e',
  status: 'validated',
  processing_stage: null,
  feedback: {
    kind: 'validated',
    feedback_id: 'feedback-e2e',
    response_classification: 'partially_correct',
    summary: 'The revised feedback is ready.',
    identified_error: 'The measurement step is incomplete.',
    explanation: 'Connect superposition to the measurement probabilities.',
    improvement_actions: ['Explain both possible measurement outcomes.'],
    recommended_next_step: 'Review the measurement postulate.',
    sources: [{ source_id: 'source-safe-1', label: 'Week 2 course notes' }],
    simulation_references: ['simulation-safe-1'],
    ai_generated_notice:
      'AI-generated feedback. Verify important details and report any concerns.',
  },
  error: null,
}

test('mounts the route-ready feedback and analytics modules only in the E2E harness', async () => {
  const placeholder = render(<App />)
  expect(screen.queryByRole('heading', { name: 'Your feedback' })).not.toBeInTheDocument()
  expect(
    screen.queryByRole('heading', { name: 'Learning and research analytics' }),
  ).not.toBeInTheDocument()
  placeholder.unmount()

  const reports: FeedbackReportInput[] = []
  const feedbackClient: FeedbackApiClient = {
    async start() {
      return { response: processing, retryAfterMs: 1 }
    },
    async get() {
      return { response: terminal, retryAfterMs: null }
    },
    async report(_feedbackId, report) {
      reports.push(report)
      return { report_id: 'report-e2e', status: 'received' }
    },
  }
  const analyticsClient: AnalyticsApiClient = {
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
    researchExportUrl(format) {
      return `/api/v1/research/exports?format=${format}&course_id=${FILTERS.courseId}`
    },
  }
  const onFiltersChange = vi.fn()
  const { container } = render(
    <main>
      <FeedbackPanel
        submissionId="submission-e2e"
        client={feedbackClient}
        pollIntervalMs={1}
      />
      <AnalyticsDashboard
        client={analyticsClient}
        initialFilters={FILTERS}
        onFiltersChange={onFiltersChange}
      />
    </main>,
  )

  expect(await screen.findByText('The revised feedback is ready.')).toBeInTheDocument()
  expect(
    await screen.findByRole('heading', { name: 'Learning activity' }),
  ).toBeInTheDocument()
  expect(
    screen.getByRole('heading', { name: /Paired agentic/ }),
  ).toBeInTheDocument()
  expect(
    screen.getByRole('link', { name: 'Download JSON' }),
  ).toHaveAttribute(
    'href',
    '/api/v1/research/exports?format=json&course_id=course-a',
  )

  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Report a concern' }))
  await user.selectOptions(screen.getByLabelText('Concern'), 'citation_issue')
  await user.type(
    screen.getByLabelText('Additional details (optional)'),
    'Please review the source label.',
  )
  await user.click(screen.getByRole('button', { name: 'Send report' }))

  expect(
    await screen.findByText('Thank you. Your concern has been received.'),
  ).toBeInTheDocument()
  expect(reports).toEqual([
    {
      category: 'citation_issue',
      note: 'Please review the source label.',
    },
  ])
  expect((await axe.run(container)).violations).toEqual([])
})
