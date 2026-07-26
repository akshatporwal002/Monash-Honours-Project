import type { ApiSchemas } from '../../api/generated'

export type FeedbackWorkflowStatus = ApiSchemas['FeedbackWorkflowStatus']

export type FeedbackProcessingStage =
  | 'pending'
  | 'context_collection'
  | 'generating'
  | 'judging'
  | 'regenerating'

export type FeedbackSource = ApiSchemas['FeedbackSourceView']

export type ValidatedFeedback = ApiSchemas['ValidatedFeedbackView'] & {
  kind: 'validated'
  feedback_id: string
  response_classification: 'correct' | 'partially_correct' | 'incorrect' | null
  summary: string
  identified_error: string | null
  explanation: string | null
  improvement_actions: string[]
  recommended_next_step: string | null
  sources: FeedbackSource[]
  simulation_references: string[]
  ai_generated_notice: string
}

export type SafeFallbackFeedback = ApiSchemas['SafeFallbackView'] & {
  kind: 'safe_fallback'
  feedback_id: string
  summary: string
  explanation: string
  recommended_next_step: string
  sources: FeedbackSource[]
  simulation_references: string[]
}

export type FeedbackWorkflowResponse = ApiSchemas['FeedbackWorkflowResponse'] & {
  workflow_run_id: string
  submission_id: string
  status: FeedbackWorkflowStatus
  processing_stage: FeedbackProcessingStage | null
  feedback: ValidatedFeedback | SafeFallbackFeedback | null
  error: {
    code: 'feedback_processing_failed'
    message: 'Feedback processing could not be completed.'
    retryable: boolean
  } | null
}

export type FeedbackWorkflowResult = {
  response: FeedbackWorkflowResponse
  retryAfterMs: number | null
}

export type FeedbackReportCategory = ApiSchemas['FeedbackReportCategory']

export type FeedbackReportInput = ApiSchemas['FeedbackReportRequest'] & {
  category: FeedbackReportCategory
  note?: string
}

export type FeedbackReportResponse = ApiSchemas['FeedbackReportResponse'] & {
  report_id: string
  status: 'received'
}

export interface FeedbackApiClient {
  start(submissionId: string, signal?: AbortSignal): Promise<FeedbackWorkflowResult>
  get(submissionId: string, signal?: AbortSignal): Promise<FeedbackWorkflowResult>
  report(
    feedbackId: string,
    report: FeedbackReportInput,
    signal?: AbortSignal,
  ): Promise<FeedbackReportResponse>
}
