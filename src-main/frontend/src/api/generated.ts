// Generated from contracts/openapi.json. Do not edit by hand.
// Run: uv run --frozen python scripts/generate_frontend_contracts.py

export type ApiSchemas = {
  "AccessDeniedEvidenceReference": {
    "assessment": ApiSchemas["AssessmentVersionReference"]
    "reason_code": string
    "reference_id": string
    "status"?: "ACCESS_DENIED"
  }
  "AchievementRead": {
    "code": string
    "description": string
    "earned_at": string
    "icon": string
    "name": string
  }
  "ActiveScopedRoleAssignmentResponse": {
    "course_id": string
    "id": string
    "role": ApiSchemas["ScopedRole"]
    "valid_from": string
    "valid_until": (string) | (null)
    "version": number
  }
  "AdminUserCreate": {
    "email": string
    "full_name": string
    "password": string
    "role": ApiSchemas["UserRole"]
  }
  "AdminUserRead": {
    "created_at": string
    "email": string
    "full_name": string
    "id": number
    "is_active": boolean
    "role": ApiSchemas["UserRole"]
    "student_profile_id"?: (string) | (null)
    "updated_at": string
  }
  "AdminUserUpdate": {
    "email"?: (string) | (null)
    "full_name"?: (string) | (null)
    "role"?: (ApiSchemas["UserRole"]) | (null)
  }
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
  "AssessmentApprovalState": "DRAFT" | "APPROVED" | "RETIRED"
  "AssessmentConditionsRead": {
    "access_conditions": (Record<string, unknown>) | (Array<unknown>)
    "bloom_process": ApiSchemas["BloomProcess"]
    "claim": string
    "criteria": Array<ApiSchemas["AssessmentCriterionRead"]>
    "instructional_support": (Record<string, unknown>) | (Array<unknown>)
    "knowledge_dimension": ApiSchemas["BloomKnowledge"]
    "permitted_tools": (Record<string, unknown>) | (Array<unknown>)
    "purpose": ApiSchemas["AssessmentPurpose"]
    "review_rule": string
    "task_conditions": (Record<string, unknown>) | (Array<unknown>)
    "transfer_rule": (Record<string, unknown>) | (Array<unknown>)
  }
  "AssessmentCriterionDraft": {
    "approved_anchors": (Record<string, unknown>) | (Array<unknown>)
    "critical_error_rules": (Record<string, unknown>) | (Array<unknown>)
    "evaluator_type"?: ApiSchemas["CriterionEvaluatorType"]
    "evidence_description": string
    "evidence_source_types": Array<string>
    "learner_description": string
    "mandatory": boolean
    "met_rule": string
    "not_evaluable_rule": string
    "not_met_rule": string
    "stable_key": string
  }
  "AssessmentCriterionRead": {
    "description": string
    "mandatory": boolean
  }
  "AssessmentDefinitionApproval": {
    "expected_version": number
    "reason": string
  }
  "AssessmentDefinitionDraftCreate": {
    "access_conditions": (Record<string, unknown>) | (Array<unknown>)
    "bloom_process": ApiSchemas["BloomProcess"]
    "claim": string
    "contradicting_evidence": (Record<string, unknown>) | (Array<unknown>)
    "criteria": Array<ApiSchemas["AssessmentCriterionDraft"]>
    "evidence_sufficiency": (Record<string, unknown>) | (Array<unknown>)
    "formal_result_eligible": boolean
    "instructional_support": (Record<string, unknown>) | (Array<unknown>)
    "insufficient_evidence": (Record<string, unknown>) | (Array<unknown>)
    "knowledge_dimension": ApiSchemas["BloomKnowledge"]
    "next_action_contract": (Record<string, unknown>) | (Array<unknown>)
    "pass_rule_expression": Record<string, unknown>
    "permitted_tools": (Record<string, unknown>) | (Array<unknown>)
    "purpose": ApiSchemas["AssessmentPurpose"]
    "supporting_evidence": (Record<string, unknown>) | (Array<unknown>)
    "task_conditions": (Record<string, unknown>) | (Array<unknown>)
    "task_forms": Array<ApiSchemas["AssessmentTaskFormDraft"]>
    "transfer_rule": (Record<string, unknown>) | (Array<unknown>)
  }
  "AssessmentDefinitionDraftUpdate": {
    "access_conditions": (Record<string, unknown>) | (Array<unknown>)
    "bloom_process": ApiSchemas["BloomProcess"]
    "claim": string
    "contradicting_evidence": (Record<string, unknown>) | (Array<unknown>)
    "criteria": Array<ApiSchemas["AssessmentCriterionDraft"]>
    "evidence_sufficiency": (Record<string, unknown>) | (Array<unknown>)
    "expected_version": number
    "formal_result_eligible": boolean
    "instructional_support": (Record<string, unknown>) | (Array<unknown>)
    "insufficient_evidence": (Record<string, unknown>) | (Array<unknown>)
    "knowledge_dimension": ApiSchemas["BloomKnowledge"]
    "next_action_contract": (Record<string, unknown>) | (Array<unknown>)
    "pass_rule_expression": Record<string, unknown>
    "permitted_tools": (Record<string, unknown>) | (Array<unknown>)
    "purpose": ApiSchemas["AssessmentPurpose"]
    "supporting_evidence": (Record<string, unknown>) | (Array<unknown>)
    "task_conditions": (Record<string, unknown>) | (Array<unknown>)
    "task_forms": Array<ApiSchemas["AssessmentTaskFormDraft"]>
    "transfer_rule": (Record<string, unknown>) | (Array<unknown>)
  }
  "AssessmentDefinitionRead": {
    "access_conditions": (Record<string, unknown>) | (Array<unknown>)
    "approval_state": ApiSchemas["AssessmentApprovalState"]
    "approved_at": (string) | (null)
    "approved_by_user_id": (number) | (null)
    "assessment_definition_id": string
    "bloom_process": ApiSchemas["BloomProcess"]
    "claim": string
    "contradicting_evidence": (Record<string, unknown>) | (Array<unknown>)
    "course_id": string
    "criteria": Array<ApiSchemas["AssessmentTaskCriterionRead"]>
    "evidence_sufficiency": (Record<string, unknown>) | (Array<unknown>)
    "formal_result_eligible": (boolean) | (null)
    "id": string
    "instructional_support": (Record<string, unknown>) | (Array<unknown>)
    "insufficient_evidence": (Record<string, unknown>) | (Array<unknown>)
    "knowledge_dimension": ApiSchemas["BloomKnowledge"]
    "next_action_contract": (Record<string, unknown>) | (Array<unknown>)
    "outcome_version_id": string
    "pass_rule_expression": Record<string, unknown>
    "permitted_tools": (Record<string, unknown>) | (Array<unknown>)
    "purpose": ApiSchemas["AssessmentPurpose"]
    "supporting_evidence": (Record<string, unknown>) | (Array<unknown>)
    "task_conditions": (Record<string, unknown>) | (Array<unknown>)
    "task_forms": Array<ApiSchemas["AssessmentTaskFormRead"]>
    "transfer_rule": (Record<string, unknown>) | (Array<unknown>)
    "version": number
  }
  "AssessmentEvaluationCreate": {
    "evaluation_idempotency_key": string
  }
  "AssessmentEvaluationRead": {
    "decision_id": string
    "reason_code": ApiSchemas["AssessmentReasonCode"]
    "replayed": boolean
    "result": ApiSchemas["AssessmentResult"]
    "result_state": ApiSchemas["ResultState"]
  }
  "AssessmentPurpose": "DIAGNOSTIC" | "FORMATIVE" | "AS_LEARNING" | "SUMMATIVE" | "RESEARCH"
  "AssessmentReasonCode": "TARGET_EVIDENCE_MET" | "MISSING_REQUIRED_EVIDENCE" | "CRITERIA_NOT_MET" | "TARGET_BLOOM_ACTION_NOT_SHOWN" | "CRITICAL_CONCEPT_GAP" | "INDEPENDENT_EVIDENCE_NOT_SHOWN" | "TRANSFER_EVIDENCE_NOT_SHOWN" | "UNRESOLVED_EVIDENCE_CONFLICT" | "TASK_UNDER_HUMAN_REVIEW"
  "AssessmentResult": "PASS" | "INCOMPLETE"
  "AssessmentReviewActionCreate": {
    "action": ApiSchemas["AssessorReviewAction"]
    "expected_result_state": ApiSchemas["ResultState"]
    "expected_review_revision": number
    "new_result"?: (ApiSchemas["AssessmentResult"]) | (null)
    "reason": string
  }
  "AssessmentReviewActionRead": {
    "decision_id": string
    "replayed": boolean
    "result": (ApiSchemas["AssessmentResult"]) | (null)
    "result_state": ApiSchemas["ResultState"]
    "review_id": string
    "review_revision": number
  }
  "AssessmentReviewCriterionRead": {
    "criterion_version": number
    "criterion_version_id": string
    "decision": ApiSchemas["CriterionDecision"]
    "evaluator_reference": string
    "evidence_references": (Record<string, unknown>) | (Array<unknown>)
    "model_version": (string) | (null)
    "prompt_version": (string) | (null)
    "reason": string
    "retrieval_version": (string) | (null)
  }
  "AssessmentReviewDetailRead": {
    "course_id": string
    "created_at": string
    "criteria": Array<ApiSchemas["AssessmentReviewCriterionRead"]>
    "decision_id": string
    "history": Array<ApiSchemas["AssessmentReviewHistoryRead"]>
    "missing_criterion_version_ids": Array<string>
    "outcome_id": string
    "quality_review_status": string
    "response_conditions": (Record<string, unknown>) | (Array<unknown>)
    "response_text": string
    "result": (ApiSchemas["AssessmentResult"]) | (null)
    "result_state": ApiSchemas["ResultState"]
    "review_revision": number
    "system_reason": ApiSchemas["AssessmentReasonCode"]
    "versions": Partial<Record<string, (string) | (number)>>
  }
  "AssessmentReviewHistoryRead": {
    "action": ApiSchemas["AssessorReviewAction"]
    "assessor_user_id": number
    "id": string
    "new_result": (ApiSchemas["AssessmentResult"]) | (null)
    "prior_result": (ApiSchemas["AssessmentResult"]) | (null)
    "reason": string
    "review_revision": number
    "reviewed_at": string
  }
  "AssessmentTaskCriterionRead": {
    "evaluator_type": ApiSchemas["CriterionEvaluatorType"]
    "evidence_description": string
    "evidence_source_types": Array<string>
    "id": string
    "learner_description": string
    "mandatory": boolean
    "met_rule": string
    "not_evaluable_rule": string
    "not_met_rule": string
    "stable_key": string
    "version": number
  }
  "AssessmentTaskFormDraft": {
    "constraints": (Record<string, unknown>) | (Array<unknown>)
    "context": (Record<string, unknown>) | (Array<unknown>)
    "learning_task_id": string
    "source_digest": string
    "source_version": string
    "task_family": string
  }
  "AssessmentTaskFormRead": {
    "constraints": (Record<string, unknown>) | (Array<unknown>)
    "context": (Record<string, unknown>) | (Array<unknown>)
    "id": string
    "learning_task_id": string
    "source_digest": string
    "source_version": string
    "task_family": string
    "version": number
  }
  "AssessmentVersionReference": {
    "assessment_attempt_id": string
    "assessment_definition_id": string
    "assessment_definition_version": number
    "bloom_target_id": string
    "bloom_target_version": number
    "course_id": string
    "criterion_set_id": string
    "criterion_set_version": number
    "outcome_id": string
    "outcome_version": number
    "pass_rule_id": string
    "pass_rule_version": number
    "response_version_id": string
    "task_form_version": number
    "task_id": string
  }
  "AssessorReviewAction": "CONFIRM" | "OVERRIDE" | "WITHHOLD" | "VOID" | "RETURN"
  "AttemptRead": {
    "answer": string
    "attempt_number": number
    "circuit": (Record<string, unknown>) | (null)
    "code": (string) | (null)
    "feedback": string
    "feedback_reference": (string) | (null)
    "id": string
    "points_awarded": number
    "score": (number) | (null)
    "status": ApiSchemas["AttemptStatus"]
    "submitted_at": string
    "task_id": string
  }
  "AttemptStatus": "submitted" | "completed"
  "AuthenticatedUserResponse": {
    "email": string
    "full_name": string
    "id": number
    "role": ApiSchemas["UserRole"]
    "scoped_assignments": Array<ApiSchemas["ActiveScopedRoleAssignmentResponse"]>
  }
  "BloomKnowledge": "FACTUAL" | "CONCEPTUAL" | "PROCEDURAL" | "METACOGNITIVE"
  "BloomProcess": "REMEMBER" | "UNDERSTAND" | "APPLY" | "ANALYSE" | "EVALUATE" | "CREATE"
  "Body_upload_course_material_api_v1_courses__course_id__materials_upload_post": {
    "file": string
  }
  "Body_upload_material_api_v1_courses__course_id__materials_uploads_post": {
    "file": string
  }
  "BootstrapRead": {
    "course": ApiSchemas["CourseRead"]
    "users": Array<ApiSchemas["AdminUserRead"]>
  }
  "BulkReminderCreate": {
    "message": string
    "student_ids": Array<string>
    "task_id"?: (string) | (null)
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
  "ConflictingEvidenceReference": {
    "assessment": ApiSchemas["AssessmentVersionReference"]
    "evidence_ids": Array<string>
    "reason_code": string
    "status"?: "CONFLICT"
  }
  "CourseCreate": {
    "code"?: (string) | (null)
    "description"?: string
    "enrollment_open"?: boolean
    "title": string
  }
  "CourseProgressRead": {
    "code": string
    "description": string
    "id": string
    "progress_percentage": number
    "state": ApiSchemas["CourseState"]
    "title": string
  }
  "CourseRead": {
    "code": string
    "created_at": string
    "description": string
    "educator_id": number
    "enrollment_open": boolean
    "id": string
    "module_count"?: number
    "progress_percentage"?: number
    "state": ApiSchemas["CourseState"]
    "student_count"?: number
    "title": string
    "updated_at": string
  }
  "CourseState": "draft" | "published" | "archived"
  "CourseUpdate": {
    "code"?: (string) | (null)
    "description"?: (string) | (null)
    "enrollment_open"?: (boolean) | (null)
    "title"?: (string) | (null)
  }
  "CriterionDecision": "MET" | "NOT_MET" | "NOT_EVALUABLE"
  "CriterionEvaluatorType": "rules" | "human" | "validated_ai" | "mixed"
  "DraftRead": {
    "answer": string
    "circuit": (Record<string, unknown>) | (null)
    "code": (string) | (null)
    "id": string
    "task_id": string
    "updated_at": string
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
  "DraftWrite": {
    "answer"?: string
    "circuit"?: (Record<string, unknown>) | (null)
    "code"?: (string) | (null)
  }
  "EducatorDashboardRead": {
    "at_risk_students": number
    "completion_percentage": number
    "concept_mastery": Array<ApiSchemas["LabelScoreRead"]>
    "courses": Array<ApiSchemas["CourseRead"]>
    "leaderboard": Array<ApiSchemas["LeaderboardEntryRead"]>
    "recent_activity": Array<ApiSchemas["RecentActivityRead"]>
    "task_type_performance": Array<ApiSchemas["LabelScoreRead"]>
    "total_students": number
    "weekly_engagement": Array<ApiSchemas["WeeklyEngagementRead"]>
  }
  "EducatorStudentRead": {
    "at_risk": boolean
    "average_score": number
    "completed_tasks": number
    "completion_percentage": number
    "course_id": string
    "course_title": string
    "display_name": string
    "email": string
    "last_active": (string) | (null)
    "overdue_tasks": number
    "student_id": string
    "total_tasks": number
    "user_id": number
  }
  "EnrollmentCreate": {
    "student_id": number
  }
  "EnrollmentRead": {
    "course_id": string
    "enrolled_at": string
    "id": string
    "status": ApiSchemas["EnrollmentStatus"]
    "student_email": string
    "student_id": number
    "student_name": string
  }
  "EnrollmentStatus": "active" | "completed" | "withdrawn"
  "EvidenceReference": {
    "assessment": ApiSchemas["AssessmentVersionReference"]
    "content_digest": string
    "contract_version"?: "learnlens.assessment-evidence.v1"
    "evidence_id": string
    "evidence_type": string
    "occurred_at": string
    "record_version": number
    "schema_version": string
    "source_record_id": string
    "source_record_version": number
  }
  "EvidenceReferenceResolutionEnvelope": {
    "resolution": (ApiSchemas["ResolvedEvidenceReference"]) | (ApiSchemas["MissingEvidenceReference"]) | (ApiSchemas["StaleEvidenceReference"]) | (ApiSchemas["ConflictingEvidenceReference"]) | (ApiSchemas["AccessDeniedEvidenceReference"]) | (ApiSchemas["InvalidEvidenceReference"])
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
  "FormalResultSummary": {
    "assessment_attempt_id": string
    "assessment_definition_id": string
    "assessor_reviewed_at"?: (string) | (null)
    "contract_version"?: "learnlens.formal-result-summary.v1"
    "course_id": string
    "decided_at"?: (string) | (null)
    "decision_id"?: (string) | (null)
    "reason_code"?: (ApiSchemas["AssessmentReasonCode"]) | (null)
    "response_version_id": string
    "result"?: (ApiSchemas["AssessmentResult"]) | (null)
    "result_state": ApiSchemas["ResultState"]
  }
  "FunnelStage": {
    "count": number
    "event_type": ApiSchemas["LearningEventType"]
    "previous_stage_rate": ApiSchemas["MetricValue"]
  }
  "GateOperation": {
    "gate": "h" | "x" | "cx"
    "targets": Array<number>
  }
  "GenerateTasksRequest": {
    "allowed_task_types": Array<ApiSchemas["TaskType"]>
    "difficulty_levels": Array<string>
    "learning_outcome_id": string
    "learning_outcome_text": string
    "module_id"?: (string) | (null)
    "task_count"?: number
  }
  "GeneratedTaskRead": {
    "difficulty": string
    "id": string
    "instructions": string
    "learning_outcome_id": string
    "prompt": string
    "source_references": Array<string>
    "task_type": ApiSchemas["TaskType"]
    "title": string
  }
  "HTTPValidationError": {
    "detail"?: Array<ApiSchemas["ValidationError"]>
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
  "InvalidEvidenceReference": {
    "reason_code": string
    "reference_id"?: (string) | (null)
    "status"?: "INVALID"
  }
  "JudgeDecision": "pass" | "fail"
  "LabelScoreRead": {
    "label": string
    "score": number
  }
  "LatestAttemptSummary": {
    "attempt_number": number
    "id": string
    "score": number
    "status": ApiSchemas["AttemptStatus"]
    "submitted_at": string
  }
  "LeaderboardEntryRead": {
    "completed_tasks": number
    "display_name": string
    "points": number
    "student_id": string
  }
  "LearningEventReceipt": {
    "learning_event_id": string
    "occurred_at": string
    "status"?: "recorded"
  }
  "LearningEventType": "task_view" | "draft_save" | "submission" | "feedback_view" | "completion"
  "LearningMaterialLinkCreate": {
    "module_id"?: (string) | (null)
    "source_url": string
  }
  "LearningMaterialRead": {
    "content_hash": string
    "course_id": string
    "created_at": string
    "error_code"?: (string) | (null)
    "extracted_at"?: (string) | (null)
    "extraction_error"?: (string) | (null)
    "failure_stage"?: (string) | (null)
    "file_size_bytes"?: (number) | (null)
    "id": string
    "indexed_at"?: (string) | (null)
    "indexing_status"?: ApiSchemas["MaterialIndexStatus"]
    "mime_type": string
    "module_id"?: (string) | (null)
    "original_filename"?: (string) | (null)
    "processing_revision"?: number
    "source_url"?: (string) | (null)
    "storage_key"?: (string) | (null)
  }
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
  "LoginRequest": {
    "email": string
    "password": string
  }
  "MaterialIndexStatus": "pending" | "processing" | "extracted" | "indexed" | "failed"
  "MaterialLinkCreate": {
    "module_id"?: (string) | (null)
    "source_url": string
  }
  "MaterialProcessingRead": {
    "chunk_count": number
    "indexed_chunk_count": number
    "material": ApiSchemas["LearningMaterialRead"]
    "processing_revision": number
  }
  "MaterialRead": {
    "course_id": string
    "created_at": string
    "file_size_bytes": (number) | (null)
    "id": string
    "indexing_status": ApiSchemas["MaterialIndexStatus"]
    "mime_type": string
    "module_id": (string) | (null)
    "original_filename": (string) | (null)
    "source_url": (string) | (null)
  }
  "MetricValue": {
    "denominator": number
    "numerator": number
    "sample_size": number
    "unit": string
    "value": (number) | (null)
  }
  "MisconceptionState": "PERSISTED" | "WEAKENED" | "CORRECTED" | "UNCERTAIN"
  "MissingEvidenceReference": {
    "assessment": ApiSchemas["AssessmentVersionReference"]
    "evidence_id": string
    "reason_code": string
    "status"?: "MISSING"
  }
  "ModuleCreate": {
    "description"?: string
    "position": number
    "title": string
  }
  "ModuleRead": {
    "course_id": string
    "created_at": string
    "description": string
    "id": string
    "position": number
    "title": string
    "updated_at": string
  }
  "ModuleUpdate": {
    "description"?: (string) | (null)
    "position"?: (number) | (null)
    "title"?: (string) | (null)
  }
  "OutcomeCreate": {
    "kind": ApiSchemas["OutcomeKind"]
    "position": number
    "statement": string
    "title": string
    "week_number"?: (number) | (null)
  }
  "OutcomeKind": "weekly" | "topic"
  "OutcomeRead": {
    "created_at": string
    "id": string
    "kind": ApiSchemas["OutcomeKind"]
    "module_id": string
    "position": number
    "statement": string
    "title": string
    "updated_at": string
    "week_number": (number) | (null)
  }
  "OutcomeUpdate": {
    "kind"?: (ApiSchemas["OutcomeKind"]) | (null)
    "position"?: (number) | (null)
    "statement"?: (string) | (null)
    "title"?: (string) | (null)
    "week_number"?: (number) | (null)
  }
  "PairedDifferences": {
    "cost": ApiSchemas["MetricValue"]
    "latency_ms": ApiSchemas["MetricValue"]
    "pass_rate": ApiSchemas["MetricValue"]
    "relevance": ApiSchemas["MetricValue"]
    "total_tokens": ApiSchemas["MetricValue"]
  }
  "QualityReviewDecision": "APPROVED" | "REJECTED"
  "ReadinessResponse": {
    "checks": Partial<Record<string, "ready" | "not_ready">>
    "status": "ready" | "not_ready"
  }
  "RecentActivityRead": {
    "occurred_at": string
    "score": number
    "student_name": string
    "task_title": string
  }
  "RecommendationRead": {
    "priority": "high" | "medium" | "low"
    "reason": string
    "task_id": string
    "title": string
    "updated_at": string
  }
  "ReminderRead": {
    "created_at": string
    "id": string
    "is_read": boolean
    "message": string
    "task_id": string
    "title": string
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
  "ResolvedEvidenceReference": {
    "reference": ApiSchemas["EvidenceReference"]
    "status"?: "RESOLVED"
  }
  "ResultState": "NOT_ASSESSED" | "PROVISIONAL" | "CONFIRMED" | "OVERRIDDEN" | "VOID"
  "RetrievalHitRead": {
    "chunk_id": string
    "chunk_text": string
    "material_id": string
    "relevance_score": number
    "source_label": string
  }
  "RetrievalResultRead": {
    "embedding_model": string
    "found": boolean
    "hits": Array<ApiSchemas["RetrievalHitRead"]>
    "latency_ms": number
    "message"?: (string) | (null)
    "request_id": string
  }
  "RetrievalSearchRequest": {
    "minimum_relevance"?: number
    "module_id"?: (string) | (null)
    "query": string
    "top_k"?: number
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
  "ScopedRole": "assessor" | "research"
  "ScopedRoleAssignmentCreate": {
    "reason": string
    "role": ApiSchemas["ScopedRole"]
    "subject_user_id": number
  }
  "ScopedRoleAssignmentRead": {
    "assigned_at": string
    "assigned_by_user_id": number
    "course_id": string
    "id": string
    "reason": string
    "revoked_at": (string) | (null)
    "role": ApiSchemas["ScopedRole"]
    "subject_user_id": number
    "valid_from": string
    "valid_until": (string) | (null)
    "version": number
  }
  "ScopedRoleAssignmentRevoke": {
    "reason": string
  }
  "SettingsRead": {
    "at_risk_threshold": number
    "llm_model": string
    "llm_provider": string
    "passing_score": number
    "points_per_level": number
    "reminders_enabled": boolean
  }
  "SettingsUpdate": {
    "at_risk_threshold"?: (number) | (null)
    "llm_model"?: (string) | (null)
    "llm_provider"?: (string) | (null)
    "passing_score"?: (number) | (null)
    "points_per_level"?: (number) | (null)
    "reminders_enabled"?: (boolean) | (null)
  }
  "SimulationRead": {
    "circuit_text": string
    "counts": Partial<Record<string, number>>
    "engine": string
    "probabilities": Partial<Record<string, number>>
  }
  "SimulationRequest": {
    "operations"?: Array<ApiSchemas["GateOperation"]>
    "qubits"?: number
    "shots"?: number
  }
  "StaleEvidenceReference": {
    "mismatched_fields": Array<string>
    "reason_code": string
    "reference": ApiSchemas["EvidenceReference"]
    "status"?: "STALE"
  }
  "StudentDashboardRead": {
    "achievements": Array<ApiSchemas["AchievementRead"]>
    "courses": Array<ApiSchemas["CourseProgressRead"]>
    "recommendations": Array<ApiSchemas["RecommendationRead"]>
    "reminders": Array<ApiSchemas["ReminderRead"]>
    "student": ApiSchemas["StudentIdentityRead"]
    "summary": ApiSchemas["StudentSummaryRead"]
    "tasks": Array<ApiSchemas["TaskRead"]>
  }
  "StudentIdentityRead": {
    "display_name": string
    "id": string
    "user_id": number
  }
  "StudentSummaryRead": {
    "average_score": number
    "completed_tasks": number
    "completion_percentage": number
    "level": number
    "next_level_points": number
    "points": number
    "total_tasks": number
  }
  "SubmissionCreate": {
    "answer"?: string
    "circuit"?: (Record<string, unknown>) | (null)
    "code"?: (string) | (null)
    "idempotency_key"?: (string) | (null)
  }
  "SubmissionState": "NOT_STARTED" | "DRAFT" | "SUBMITTED" | "UNDER_REVIEW" | "RETURNED" | "COMPLETED"
  "TaskChoice": {
    "id": string
    "text": string
  }
  "TaskCreate": {
    "difficulty": "beginner" | "intermediate" | "advanced"
    "due_at"?: (string) | (null)
    "expected_answer"?: (string) | (null)
    "instructions": string
    "learning_outcome_id": string
    "marking_criteria"?: Record<string, unknown>
    "module_id": string
    "points"?: number
    "position": number
    "prerequisite_task_ids"?: Array<string>
    "prompt": string
    "source_references"?: Array<string>
    "starter_code"?: (string) | (null)
    "task_type": ApiSchemas["TaskType"]
    "title": string
  }
  "TaskGenerateRequest": {
    "due_at"?: (string) | (null)
    "learning_outcome_id": string
    "task_count"?: number
    "task_types"?: Array<ApiSchemas["TaskType"]>
  }
  "TaskRead": {
    "access_status": "locked" | "available" | "in_progress" | "completed"
    "assessment"?: (ApiSchemas["AssessmentConditionsRead"]) | (null)
    "attempt_count"?: number
    "choices"?: Array<ApiSchemas["TaskChoice"]>
    "course_id": string
    "difficulty": string
    "due_at": (string) | (null)
    "id": string
    "instructions": string
    "latest_attempt"?: (ApiSchemas["LatestAttemptSummary"]) | (null)
    "latest_score"?: (number) | (null)
    "learning_outcome_id": string
    "module_id": string
    "module_title": string
    "points": number
    "position": number
    "prerequisite_task_ids": Array<string>
    "prompt": string
    "source_references": Array<string>
    "starter_circuit"?: (Record<string, unknown>) | (null)
    "starter_code": (string) | (null)
    "task_type": ApiSchemas["TaskType"]
    "title": string
  }
  "TaskType": "multiple_choice" | "multiple_answer" | "short_answer" | "code_explanation" | "code_completion" | "quantum_circuit" | "quiz" | "code" | "circuit"
  "TaskUpdate": {
    "difficulty"?: ("beginner" | "intermediate" | "advanced") | (null)
    "due_at"?: (string) | (null)
    "expected_answer"?: (string) | (null)
    "instructions"?: (string) | (null)
    "marking_criteria"?: (Record<string, unknown>) | (null)
    "points"?: (number) | (null)
    "position"?: (number) | (null)
    "prerequisite_task_ids"?: (Array<string>) | (null)
    "prompt"?: (string) | (null)
    "source_references"?: (Array<string>) | (null)
    "starter_code"?: (string) | (null)
    "title"?: (string) | (null)
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
  "UserRole": "student" | "educator" | "administrator"
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
  "ValidationError": {
    "ctx"?: Record<string, never>
    "input"?: unknown
    "loc": Array<(string) | (number)>
    "msg": string
    "type": string
  }
  "WeeklyEngagementRead": {
    "active_students": number
    "label": string
    "submissions": number
  }
  "WorkflowStage": "pending" | "context_collection" | "generating" | "judging" | "regenerating" | "completed" | "failed"
}
