// Generated from contracts/openapi.json. Do not edit by hand.
// Run: uv run --frozen python scripts/generate_frontend_contracts.py

export type ApiSchemas = {
  "AnalyticsFilterOptions": {
    "courses"?: Array<string>
    "experimental_conditions"?: Array<string>
    "generated_at": string
    "judge_decisions"?: Array<string>
    "models"?: Array<string>
    "schema_version"?: string
    "task_types"?: Array<string>
  }
  "AnalyticsFilterSnapshot": {
    "course_ids"?: Array<string>
    "end_at"?: (string) | (null)
    "experimental_conditions"?: Array<ApiSchemas["ExperimentalCondition"]>
    "judge_decisions"?: Array<string>
    "models"?: Array<string>
    "start_at"?: (string) | (null)
    "task_types"?: Array<string>
  }
  "ConditionMetrics": {
    "average_cost": ApiSchemas["MetricValue"]
    "average_latency_ms": ApiSchemas["MetricValue"]
    "average_relevance": ApiSchemas["MetricValue"]
    "average_total_tokens": ApiSchemas["MetricValue"]
    "fallback_rate": ApiSchemas["MetricValue"]
    "hallucination_rate": ApiSchemas["MetricValue"]
    "overall_pass_rate": ApiSchemas["MetricValue"]
    "p95_latency_ms": ApiSchemas["MetricValue"]
  }
  "DraftSaveLearningEventRequest": {
    "event_id": string
    "event_type": "draft_save"
    "metadata"?: ApiSchemas["DraftSaveMetadata"]
    "task_id": string
  }
  "DraftSaveMetadata": {
    "duration_ms"?: (number) | (null)
  }
  "ExperimentalCondition": "agentic_rag" | "single_step_baseline"
  "FeedbackApiErrorDetail": {
    "code": string
    "message": string
  }
  "FeedbackApiErrorResponse": {
    "error": ApiSchemas["FeedbackApiErrorDetail"]
  }
  "FeedbackFailureView": {
    "code"?: "feedback_processing_failed"
    "message"?: "Feedback processing could not be completed."
    "retryable": boolean
  }
  "FeedbackReportCategory": "incorrect" | "unsafe" | "unclear" | "citation_issue" | "other"
  "FeedbackReportRequest": {
    "category": ApiSchemas["FeedbackReportCategory"]
    "note"?: (string) | (null)
  }
  "FeedbackReportResponse": {
    "report_id": string
    "status"?: "received"
  }
  "FeedbackResponseClassification": "correct" | "partially_correct" | "incorrect"
  "FeedbackSourceView": {
    "label": string
    "source_id": string
  }
  "FeedbackWorkflowResponse": {
    "error"?: (ApiSchemas["FeedbackFailureView"]) | (null)
    "feedback"?: (ApiSchemas["ValidatedFeedbackView"]) | (ApiSchemas["SafeFallbackView"]) | (null)
    "processing_stage"?: (ApiSchemas["WorkflowStage"]) | (null)
    "status": ApiSchemas["FeedbackWorkflowStatus"]
    "submission_id": string
    "workflow_run_id": string
  }
  "FeedbackWorkflowStatus": "processing" | "validated" | "fallback" | "failed"
  "FunnelStage": {
    "count": number
    "event_type": ApiSchemas["LearningEventType"]
    "previous_stage_rate": ApiSchemas["MetricValue"]
  }
  "HealthResponse": {
    "status": "ok"
  }
  "InactiveLearner": {
    "last_activity_at": (string) | (null)
    "pseudonymous_user_id": string
  }
  "InactiveLearnerPage": {
    "excluded_incomplete_count"?: number
    "filters"?: ApiSchemas["AnalyticsFilterSnapshot"]
    "generated_at": string
    "inactive_learner_count": ApiSchemas["MetricValue"]
    "items": Array<ApiSchemas["InactiveLearner"]>
    "page": number
    "page_size": number
    "schema_version"?: string
    "total": number
  }
  "JudgeDecision": "pass" | "fail"
  "LearningEventReceipt": {
    "learning_event_id": string
    "occurred_at": string
    "status"?: "recorded"
  }
  "LearningEventType": "task_view" | "draft_save" | "submission" | "feedback_view" | "completion"
  "LearningMetricsResult": {
    "average_attempts": ApiSchemas["MetricValue"]
    "average_score": ApiSchemas["MetricValue"]
    "completion_rate": ApiSchemas["MetricValue"]
    "excluded_incomplete_count"?: number
    "feedback_view_rate": ApiSchemas["MetricValue"]
    "filters"?: ApiSchemas["AnalyticsFilterSnapshot"]
    "funnel": Array<ApiSchemas["FunnelStage"]>
    "generated_at": string
    "inactive_learner_count": ApiSchemas["MetricValue"]
    "schema_version"?: string
    "submissions": ApiSchemas["MetricValue"]
    "task_views": ApiSchemas["MetricValue"]
    "total_attempts": ApiSchemas["MetricValue"]
    "unique_submissions": ApiSchemas["MetricValue"]
    "unique_task_views": ApiSchemas["MetricValue"]
  }
  "MetricValue": {
    "denominator": number
    "numerator": number
    "sample_size": number
    "unit": string
    "value": (number) | (null)
  }
  "PairedDifferences": {
    "cost": ApiSchemas["MetricValue"]
    "latency_ms": ApiSchemas["MetricValue"]
    "pass_rate": ApiSchemas["MetricValue"]
    "relevance": ApiSchemas["MetricValue"]
    "total_tokens": ApiSchemas["MetricValue"]
  }
  "ReadinessResponse": {
    "checks": Partial<Record<string, "ready" | "not_ready">>
    "status": "ready" | "not_ready"
  }
  "ResearchExportFormat": "csv" | "json"
  "ResearchMetricsResult": {
    "by_condition": Partial<Record<ApiSchemas["ExperimentalCondition"], ApiSchemas["ConditionMetrics"]>>
    "excluded_incomplete_count": number
    "filters"?: ApiSchemas["AnalyticsFilterSnapshot"]
    "first_pass_rate": ApiSchemas["MetricValue"]
    "generated_at": string
    "paired_agentic_minus_baseline": ApiSchemas["PairedDifferences"]
    "regeneration_success_rate": ApiSchemas["MetricValue"]
    "retrieval_hit_rate": ApiSchemas["MetricValue"]
    "retrieval_threshold"?: number
    "retrieval_threshold_version"?: string
    "schema_version"?: string
  }
  "SafeFallbackView": {
    "explanation": string
    "feedback_id": string
    "kind"?: "safe_fallback"
    "recommended_next_step": string
    "simulation_references"?: Array<string>
    "sources"?: Array<ApiSchemas["FeedbackSourceView"]>
    "summary": string
  }
  "TaskViewLearningEventRequest": {
    "event_id": string
    "event_type": "task_view"
    "metadata"?: ApiSchemas["TaskViewMetadata"]
    "task_id": string
  }
  "TaskViewMetadata": {
    "source"?: (string) | (null)
  }
  "ValidatedFeedbackView": {
    "ai_generated_notice": string
    "explanation"?: (string) | (null)
    "feedback_id": string
    "identified_error"?: (string) | (null)
    "improvement_actions"?: Array<string>
    "kind"?: "validated"
    "recommended_next_step"?: (string) | (null)
    "response_classification"?: (ApiSchemas["FeedbackResponseClassification"]) | (null)
    "simulation_references"?: Array<string>
    "sources"?: Array<ApiSchemas["FeedbackSourceView"]>
    "summary": string
  }
  "WorkflowStage": "pending" | "context_collection" | "generating" | "judging" | "regenerating" | "completed" | "failed"
}
