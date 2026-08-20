import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { FeedbackPanel } from './FeedbackPanel'
import type { FeedbackApiClient, FeedbackWorkflowResponse } from './types'

function clientFor(response: FeedbackWorkflowResponse): FeedbackApiClient {
  return {
    start: vi.fn().mockResolvedValue({ response, retryAfterMs: null }),
    get: vi.fn().mockResolvedValue({ response, retryAfterMs: null }),
    report: vi.fn(),
  }
}

const base = {
  workflow_run_id: 'workflow-1',
  submission_id: 'attempt-1',
  status: 'validated' as const,
  processing_stage: null,
  error: null,
}

// Plan 006 Step 6: the validated and safe-fallback states must be visibly and
// programmatically distinct (FR18) — previously both modifier classes were undefined.
describe('feedback state presentation', () => {
  it('renders validated feedback as "Your feedback" with the AI-generated marker', async () => {
    const response: FeedbackWorkflowResponse = {
      ...base,
      feedback: {
        kind: 'validated',
        feedback_id: 'feedback-1',
        response_classification: 'correct',
        summary: 'Well reasoned.',
        identified_error: null,
        explanation: null,
        improvement_actions: [],
        recommended_next_step: null,
        sources: [],
        simulation_references: [],
        ai_generated_notice: 'AI-generated feedback validated against authorised course material.',
      },
    }
    render(<FeedbackPanel submissionId="attempt-1" client={clientFor(response)} />)
    const heading = await screen.findByRole('heading', { name: 'Your feedback' })
    expect(heading.closest('section')).toHaveAttribute('data-kind', 'validated')
    expect(screen.getByText('AI-generated')).toBeInTheDocument()
  })

  it('renders the safe fallback as "Feedback unavailable" in a distinct state', async () => {
    const response: FeedbackWorkflowResponse = {
      ...base,
      status: 'fallback',
      feedback: {
        kind: 'safe_fallback',
        feedback_id: 'feedback-2',
        summary: 'Feedback could not be validated. Review the course notes for this task.',
        explanation: 'A validated explanation is not available for this attempt.',
        recommended_next_step: 'Review the worked example, then try again.',
        sources: [],
        simulation_references: [],
      },
    }
    render(<FeedbackPanel submissionId="attempt-1" client={clientFor(response)} />)
    const heading = await screen.findByRole('heading', { name: 'Feedback unavailable' })
    expect(heading.closest('section')).toHaveAttribute('data-kind', 'safe_fallback')
    expect(screen.queryByRole('heading', { name: 'Your feedback' })).not.toBeInTheDocument()
  })
})
