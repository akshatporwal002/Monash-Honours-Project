// Generated from contracts/openapi.json. Do not edit by hand.
// Run: uv run --frozen python scripts/generate_frontend_contracts.py

export type ApiSchemas = {
  "AccessDeniedEvidenceReference": {
    "assessment": ApiSchemas["AssessmentVersionReference"]
    "reason_code": string
    "reference_id": string
    "status"?: "ACCESS_DENIED"
  }
  "AccessSupportState": "NOT_DECLARED" | "APPROVED" | "PROVIDED"
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
  "AssessedFeedbackView": {
    "approved_hints": Array<string>
    "assessment": ApiSchemas["AssessmentVersionReference"]
    "assessment_attempt_id": string
    "content_digest": string
    "contract_version"?: "learnlens.assessed-feedback.v1"
    "criteria": Array<ApiSchemas["CriterionFeedback"]>
    "current_human_action_id": (string) | (null)
    "help_use_ids": Array<string>
    "model_version": string
    "permitted_next_action": string
    "prompt_version": string
    "reflection_prompt": string
    "response_version_id": string
    "rule_policy_version": string
    "simulation_evidence": Array<ApiSchemas["SimulationProvenance"]>
    "source_claims": Array<ApiSchemas["GroundedSourceClaim"]>
    "summary": string
    "task_form_id": string
    "task_form_version": number
    "task_form_version_id": (string) | (null)
    "task_revision_id": string
  }
  "AssessmentApprovalState": "DRAFT" | "APPROVED" | "RETIRED"
  "AssessmentAttemptState": "PENDING" | "EVALUATED" | "FAULTED" | "VOID"
  "AssessmentAuthoringTaskRead": {
    "content_digest": (string) | (null)
    "issues": Array<string>
    "outcome_id": string
    "outcome_statement": string
    "reviewed": boolean
    "revision_id": (string) | (null)
    "source_materials": Array<ApiSchemas["AssessmentSourceMaterialRead"]>
    "task_id": string
    "task_type": string
    "title": string
  }
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
    "task_form_version_id": string
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
  "AssessmentEvaluationFailureCategory": "provider_unavailable" | "provider_fault" | "version_conflict" | "persistence_unavailable"
  "AssessmentEvaluationJobState": "pending" | "running" | "retry_scheduled" | "completed" | "review_required"
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
    "approved_anchors"?: (Record<string, unknown>) | (Array<unknown>) | (null)
    "criterion_version": number
    "criterion_version_id": string
    "decision": (ApiSchemas["CriterionDecision"]) | (null)
    "evaluator_reference": string
    "evidence_description"?: string
    "evidence_references": (Record<string, unknown>) | (Array<unknown>)
    "evidence_source_types"?: (Array<string>) | (null)
    "learner_description"?: string
    "mandatory"?: boolean
    "met_rule"?: string
    "model_version": (string) | (null)
    "not_evaluable_rule"?: string
    "not_met_rule"?: string
    "prompt_version": (string) | (null)
    "reason": string
    "retrieval_version": (string) | (null)
  }
  "AssessmentReviewDetailRead": {
    "course_id": string
    "created_at": string
    "criteria": Array<ApiSchemas["AssessmentReviewCriterionRead"]>
    "decision_id": string
    "frozen_context"?: (ApiSchemas["FrozenAssessmentContextRead"]) | (null)
    "historical_evidence"?: Array<ApiSchemas["HistoricalResponseEvidenceRead"]>
    "history": Array<ApiSchemas["AssessmentReviewHistoryRead"]>
    "missing_criterion_version_ids": Array<string>
    "outcome_id": string
    "quality_review_status": string
    "response"?: (ApiSchemas["FrozenResponseRead"]) | (null)
    "response_conditions": (Record<string, unknown>) | (Array<unknown>)
    "response_history"?: Array<ApiSchemas["FrozenResponseRead"]>
    "response_issues"?: Array<string>
    "response_text": string
    "result": (ApiSchemas["AssessmentResult"]) | (null)
    "result_state": ApiSchemas["ResultState"]
    "review_revision": number
    "simulations"?: Array<Record<string, unknown>>
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
  "AssessmentSourceMaterialRead": {
    "label": string
    "material_id": string
  }
  "AssessmentStartWrite": {
    "task_form_version_id": string
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
    "task_revision_id": (string) | (null)
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
  "AssessorCandidateRead": {
    "currently_eligible": boolean
    "full_name": string
    "latest_approval": (ApiSchemas["AssessorEligibilityRead"]) | (null)
    "subject_user_id": number
  }
  "AssessorEligibilityRead": {
    "actor_user_id": number
    "course_id": string
    "created_at": string
    "id": string
    "policy_version": string
    "reason": string
    "state": "APPROVED" | "WITHDRAWN"
    "subject_user_id": number
    "valid_until": (string) | (null)
    "version": number
  }
  "AssessorEligibilityWrite": {
    "expected_version": number
    "reason": string
    "state": "APPROVED" | "WITHDRAWN"
    "subject_user_id": number
    "valid_until"?: (string) | (null)
  }
  "AssessorReviewAction": "CONFIRM" | "OVERRIDE" | "WITHHOLD" | "VOID" | "RETURN"
  "AttemptRead": {
    "answer": string
    "assessment_work_start_id"?: (string) | (null)
    "attempt_number": number
    "circuit": (Record<string, unknown>) | (null)
    "code": (string) | (null)
    "episode"?: (ApiSchemas["EpisodePayloadV1"]) | (null)
    "feedback": string
    "feedback_reference": (string) | (null)
    "formal_assessment"?: (ApiSchemas["FormalAssessmentSummary"]) | (null)
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
  "Body_replace_material_api_v1_courses__course_id__materials__material_id__replacement_post": {
    "file": string
  }
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
  "CorrectionTarget": {
    "estimate_id"?: (string) | (null)
    "evidence_id"?: (string) | (null)
    "target_kind": ApiSchemas["CorrectionTargetKind"]
  }
  "CorrectionTargetKind": "EVIDENCE" | "ESTIMATE"
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
  "CriterionFeedback": {
    "criterion_id": string
    "criterion_version": number
    "criterion_version_id": string
    "evidence": Array<ApiSchemas["ResponseFieldEvidence"]>
    "guidance": string
    "learner_description": string
    "simulation_references": Array<string>
  }
  "DiagnosticConfirm": {
    "decision": "retain" | "advance"
    "independent_verified": boolean
    "reason": string
    "request_key": string
  }
  "DiagnosticRead": {
    "evidence_id": (string) | (null)
    "id": string
    "independent_conditions": string
    "learner_id": number
    "learner_name": string
    "pathway_id": string
    "prompt": string
    "purpose": string
    "reason": (string) | (null)
    "response": (ApiSchemas["DiagnosticSubmit"]) | (null)
    "state": "started" | "needs_review" | "retain" | "advance"
    "target_task_id": string
    "target_title": string
  }
  "DiagnosticStart": {
    "pathway_id": string
    "purpose": "initial" | "prior_mastery"
    "request_key": string
    "target_task_id": string
  }
  "DiagnosticSubmit": {
    "concept_uncertainty": "none_reported" | "needs_checking" | "unsure"
    "confidence": "unsure" | "somewhat_sure" | "sure"
    "independent_conditions_met": boolean
    "prior_knowledge": string
    "reasoning": string
    "request_key": string
    "requested_support": "none" | "concept_cue" | "guided"
  }
  "DraftRead": {
    "answer": string
    "assessment_work_start_id"?: (string) | (null)
    "circuit": (Record<string, unknown>) | (null)
    "code": (string) | (null)
    "episode"?: (ApiSchemas["EpisodePayloadV1"]) | (null)
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
    "assessment_work_start_id"?: (string) | (null)
    "circuit"?: (Record<string, unknown>) | (null)
    "code"?: (string) | (null)
    "episode"?: (ApiSchemas["EpisodePayloadV1"]) | (null)
  }
  "EducatorCorrectionReviewPayload": {
    "action": "ACCEPTED" | "REJECTED" | "NEEDS_REVIEW"
    "actor_reference": string
    "annotation_id": string
    "contract_version"?: "learnlens.educator-correction-review.v1"
    "correlation_id": string
    "course_id": string
    "expected_latest_review_version": number
    "idempotency_key": string
    "learner_id": string
    "occurred_at": string
    "outcome_id": string
    "prior_review_id"?: (string) | (null)
    "reason": string
    "review_id": string
    "review_version": number
    "target": ApiSchemas["CorrectionTarget"]
  }
  "EducatorCorrectionReviewRequest": {
    "action": "ACCEPTED" | "REJECTED" | "NEEDS_REVIEW"
    "annotation_id": string
    "expected_latest_review_version": number
    "idempotency_key": string
    "occurred_at": string
    "reason": string
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
    "average_score": (number) | (null)
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
  "EffectivePreferences": {
    "limitations": Array<string>
    "pathway_support_level"?: ("guided" | "concept_cue" | "independent") | (null)
    "repeat_allowed": boolean
    "requested": ApiSchemas["PreferenceValues"]
    "transfer": boolean
    "values": ApiSchemas["PreferenceValues"]
    "version": number
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
  "EpisodeCheckpointPage": {
    "items": Array<ApiSchemas["EpisodeCheckpointRead"]>
    "next_offset": (number) | (null)
  }
  "EpisodeCheckpointRead": {
    "created_at": string
    "input_content": ApiSchemas["ResponseContent"]
    "part_id": string
    "prediction": ApiSchemas["ResponseContent"]
  }
  "EpisodeCheckpointReceipt": {
    "checkpoint_id": string
    "draft": ApiSchemas["DraftRead"]
  }
  "EpisodeCheckpointWrite": {
    "part_id": string
    "response": ApiSchemas["DraftWrite"]
    "stage_start_id"?: (string) | (null)
  }
  "EpisodeHelpUsePage": {
    "items": Array<ApiSchemas["EpisodeHelpUseRead"]>
    "next_offset": (number) | (null)
  }
  "EpisodeHelpUseRead": {
    "assessment_work_start_id": string
    "created_at": string
    "id": string
    "item_index": number
    "kind": "conceptual_hint" | "accessibility"
    "part_id": string
    "stage_start_id": (string) | (null)
    "task_form_version_id": string
  }
  "EpisodeHelpUseReceipt": {
    "content": (string) | (null)
    "record": ApiSchemas["EpisodeHelpUseRead"]
  }
  "EpisodeHelpUseWrite": {
    "assessment_work_start_id": string
    "item_index": number
    "kind": "conceptual_hint" | "accessibility"
    "request_key": string
    "stage_start_id"?: (string) | (null)
  }
  "EpisodePayloadV1": {
    "schema_version"?: "learnlens.episode.v1"
    "supported": ApiSchemas["EpisodeStageResponseV1"]
    "transfer"?: (ApiSchemas["TransferResponseV1"]) | (null)
  }
  "EpisodeRevision": {
    "previous_response_version_id": string
    "reason": string
  }
  "EpisodeStageResponseV1": {
    "explanation"?: (string) | (null)
    "prediction"?: (ApiSchemas["ResponseContent"]) | (null)
    "prediction_checkpoint_id"?: (string) | (null)
    "reasoning"?: (string) | (null)
    "reflection"?: (string) | (null)
    "revision"?: (ApiSchemas["EpisodeRevision"]) | (null)
    "simulation_references"?: Array<ApiSchemas["SimulationReference"]>
  }
  "EpisodeStateRead": {
    "accessibility_support"?: Array<string>
    "prediction_required": boolean
    "required_responses": Array<"prediction" | "reasoning" | "explanation" | "reflection">
    "schema_version"?: "learnlens.episode-plan.v1"
    "supported_hints"?: Array<string>
    "supported_part_id": string
    "transfer"?: (ApiSchemas["EpisodeTransferRead"]) | (null)
    "transfer_part_id": string
  }
  "EpisodeTransferRead": {
    "instructions": string
    "part_id": string
    "prompt": string
    "stage_start_id": string
    "starter_circuit"?: (Partial<Record<string, ApiSchemas["JsonValue"]>>) | (null)
    "starter_code"?: (string) | (null)
  }
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
  "EvidenceType": "PREDICTION" | "EXPLANATION" | "REASONING" | "RESPONSE" | "REVISION" | "CONFIDENCE" | "HINT" | "SCAFFOLD" | "FEEDBACK_INTERACTION" | "REFLECTION" | "SIMULATION" | "MISCONCEPTION_CHECK" | "TRANSFER" | "DIAGNOSTIC" | "SYSTEM_FAULT"
  "ExperimentalCondition": "agentic_rag" | "single_step_baseline"
  "FeedbackAcknowledgement": {
    "feedback_id": string
  }
  "FeedbackAcknowledgementRead": {
    "acknowledged"?: boolean
    "evidence_id": string
  }
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
  "FormalAssessmentSummary": {
    "result"?: null
    "visibility"?: "withheld"
  }
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
  "FrozenAssessmentContextRead": {
    "bloom_process": string
    "knowledge_dimension": string
    "outcome_statement": string
    "outcome_title": string
    "pass_rule_expression": Record<string, unknown>
    "starter_circuit"?: (Record<string, unknown>) | (null)
    "starter_code"?: (string) | (null)
    "supported_instructions": string
    "supported_prompt": string
    "task_revision_id": string
    "task_title": string
    "transfer_instructions"?: (string) | (null)
    "transfer_prompt"?: (string) | (null)
    "transfer_starter_circuit"?: (Record<string, unknown>) | (null)
    "transfer_starter_code"?: (string) | (null)
  }
  "FrozenResponseRead": {
    "assessment_work_start_id": (string) | (null)
    "content": ApiSchemas["ResponseContent"]
    "declared_conditions": (Record<string, unknown>) | (Array<unknown>)
    "episode": (ApiSchemas["EpisodePayloadV1"]) | (null)
    "reference": ApiSchemas["EvidenceReference"]
    "task_form_version_id": (string) | (null)
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
  "GroundedSourceClaim": {
    "approval_id": string
    "chunk_id": string
    "claim": string
    "document_id": string
    "end_offset": number
    "passage_digest": string
    "retrieval_request_id": string
    "retrieval_version": string
    "source_digest": string
    "source_id": string
    "source_label": string
    "source_revision_id": string
    "start_offset": number
    "support_quote": string
  }
  "HTTPValidationError": {
    "detail"?: Array<ApiSchemas["ValidationError"]>
  }
  "HealthResponse": {
    "status": "ok"
  }
  "HistoricalResponseEvidenceRead": {
    "issues"?: Array<string>
    "response"?: (ApiSchemas["FrozenResponseRead"]) | (null)
    "response_version_id": string
    "simulations"?: Array<Record<string, unknown>>
  }
  "HumanActionHistoryRead": {
    "action_id": string
    "assessor_user_id": number
    "created_at": string
    "criteria": Array<ApiSchemas["HumanCriterionHistoryRead"]>
    "reason": string
    "result": ApiSchemas["AssessmentResult"]
    "result_state": ApiSchemas["ResultState"]
    "revision": number
  }
  "HumanAssessmentReceipt": {
    "action_id": string
    "assessment_attempt_id": string
    "decision_id": string
    "replayed": boolean
    "result": ApiSchemas["AssessmentResult"]
    "result_state": ApiSchemas["ResultState"]
    "revision": number
  }
  "HumanAssessmentWrite": {
    "criteria": Array<ApiSchemas["HumanCriterionWrite"]>
    "expected_token": string
    "idempotency_key": string
    "reason": string
  }
  "HumanCriterionHistoryRead": {
    "criterion_version_id": string
    "decision": ApiSchemas["CriterionDecision"]
    "evaluator_reference": string
    "evidence_references": Array<Record<string, unknown>>
    "reason": string
  }
  "HumanCriterionWrite": {
    "criterion_version_id": string
    "decision": ApiSchemas["CriterionDecision"]
    "evidence_ids": Array<string>
    "reason": string
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
  "InferenceStatus": "UNCERTAIN" | "SUPPORTED" | "CONTRADICTED" | "NEEDS_REVIEW"
  "InvalidEvidenceReference": {
    "reason_code": string
    "reference_id"?: (string) | (null)
    "status"?: "INVALID"
  }
  "JsonValue": unknown
  "JudgeDecision": "pass" | "fail"
  "LabelScoreRead": {
    "label": string
    "score": number
  }
  "LatestAttemptSummary": {
    "attempt_number": number
    "formal_assessment"?: (ApiSchemas["FormalAssessmentSummary"]) | (null)
    "id": string
    "score": (number) | (null)
    "status": ApiSchemas["AttemptStatus"]
    "submitted_at": string
  }
  "LeaderboardEntryRead": {
    "completed_tasks": number
    "display_name": string
    "points": number
    "student_id": string
  }
  "LearnerAnnotationPayload": {
    "action"?: "ANNOTATED"
    "actor_reference": string
    "annotation_id": string
    "contract_version"?: "learnlens.learner-annotation.v1"
    "correlation_id": string
    "course_id": string
    "idempotency_key": string
    "learner_id": string
    "note": string
    "occurred_at": string
    "outcome_id": string
    "record_version": number
    "target": ApiSchemas["CorrectionTarget"]
  }
  "LearnerAnnotationRequest": {
    "course_id": string
    "idempotency_key": string
    "note": string
    "occurred_at": string
    "outcome_id": string
    "target": ApiSchemas["CorrectionTarget"]
  }
  "LearnerModelDimension": "PRIOR_KNOWLEDGE" | "REASONING_STRENGTH" | "REASONING_GAP" | "POSSIBLE_MISCONCEPTION" | "CONFIDENCE_CALIBRATION" | "FEEDBACK_USE" | "SCAFFOLD_DEPENDENCE" | "INDEPENDENCE" | "TRANSFER" | "EXPLICIT_PREFERENCE"
  "LearnerModelTimelineCorrection": {
    "annotation": ApiSchemas["LearnerAnnotationPayload"]
    "reviews": Array<ApiSchemas["EducatorCorrectionReviewPayload"]>
  }
  "LearnerModelTimelineEntry": {
    "entry_type": "OBSERVATION" | "INFERENCE" | "ANNOTATION" | "REVIEW"
    "occurred_at": string
    "reference_id": string
  }
  "LearnerModelTimelineEstimate": {
    "dimension": ApiSchemas["LearnerModelDimension"]
    "estimate_id": string
    "evidence_links": Array<Array<string>>
    "evidence_observed_at": string
    "inference_status": ApiSchemas["InferenceStatus"]
    "reason_code": string
    "uncertainty": number
  }
  "LearnerModelTimelineEvidence": {
    "id": string
    "occurred_at": string
    "provenance": string
    "type": string
  }
  "LearnerModelTimelineResponse": {
    "corrections": Array<ApiSchemas["LearnerModelTimelineCorrection"]>
    "entries": Array<ApiSchemas["LearnerModelTimelineEntry"]>
    "evidence": Array<ApiSchemas["LearnerModelTimelineEvidence"]>
    "next_cursor"?: (string) | (null)
    "snapshots": Array<ApiSchemas["LearnerModelTimelineSnapshot"]>
  }
  "LearnerModelTimelineSnapshot": {
    "estimates": Array<ApiSchemas["LearnerModelTimelineEstimate"]>
    "model_source": ApiSchemas["ModelSource"]
    "model_version": string
    "occurred_at": string
    "prior_snapshot_id"?: (string) | (null)
    "record_version": number
    "rule_version": string
    "snapshot_id": string
    "validation_classification": string
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
    "current_source_revision_id"?: (string) | (null)
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
    "processing_attempts"?: number
    "processing_backend"?: string
    "processing_lease_expires_at"?: (string) | (null)
    "processing_retry_at"?: (string) | (null)
    "processing_revision"?: number
    "retired_at"?: (string) | (null)
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
  "LiveEvidencePage": {
    "items": Array<ApiSchemas["LiveEvidenceRead"]>
    "next_offset": (number) | (null)
  }
  "LiveEvidenceRead": {
    "access_support_state": ApiSchemas["AccessSupportState"]
    "content_digest": string
    "evidence_id": string
    "evidence_type": ApiSchemas["EvidenceType"]
    "instructional_support_level": number
    "observation_type": ApiSchemas["ObservationType"]
    "occurred_at": string
    "outcome_id": string
    "related_evidence_ids": Array<string>
    "response_version_id": (string) | (null)
    "source_interaction_id": (string) | (null)
    "task_id": string
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
    "error_code"?: (string) | (null)
    "extraction_error"?: (string) | (null)
    "file_size_bytes": (number) | (null)
    "id": string
    "indexing_status": ApiSchemas["MaterialIndexStatus"]
    "mime_type": string
    "module_id": (string) | (null)
    "original_filename": (string) | (null)
    "processing_attempts"?: number
    "processing_lease_expires_at"?: (string) | (null)
    "processing_retry_at"?: (string) | (null)
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
  "ModelSource": "RULE_BASED" | "ADVISORY_MODEL" | "EDUCATOR" | "LEARNER"
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
  "ObservationType": "DIRECT" | "SELF_REPORTED" | "SYSTEM_CAPTURED" | "EDUCATOR_RECORDED"
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
  "PathBinding": {
    "assessment": (Partial<Record<string, string>>) | (null)
    "difficulty": string
    "review_event_id": string
    "source_approvals": Partial<Record<string, string>>
    "task_form": string
    "task_revision_id": string
    "title": string
  }
  "PathStep": {
    "concept": string
    "evidence_rule": string
    "exit_rule"?: "accepted_response"
    "faded_support_level": "guided" | "concept_cue" | "independent"
    "prerequisites": Array<string>
    "support_level": "guided" | "concept_cue" | "independent"
    "task_id": string
  }
  "PathwayPublish": {
    "diagnostic_prompt": string
    "diagnostic_task_id": string
    "expected_version": number
    "independent_conditions": string
    "reason": string
    "request_key": string
    "steps": Array<ApiSchemas["PathStep"]>
    "title": string
  }
  "PathwayRead": {
    "bindings": Partial<Record<string, ApiSchemas["PathBinding"]>>
    "course_id": string
    "diagnostic_prompt": string
    "diagnostic_task_id": string
    "id": string
    "independent_conditions": string
    "outcome_id": string
    "steps": Array<ApiSchemas["PathStep"]>
    "title": string
    "version": number
  }
  "PreferenceHistory": {
    "items": Array<ApiSchemas["PreferenceRevision"]>
    "next_offset": (number) | (null)
  }
  "PreferenceRead": {
    "values": ApiSchemas["PreferenceValues"]
    "version": number
  }
  "PreferenceReset": {
    "expected_version": number
    "request_key": string
  }
  "PreferenceRevision": {
    "action": "save" | "reset"
    "created_at": string
    "values": ApiSchemas["PreferenceValues"]
    "version": number
  }
  "PreferenceUpdate": {
    "expected_version": number
    "request_key": string
    "values": ApiSchemas["PreferenceValues"]
  }
  "PreferenceValues": {
    "breaks"?: boolean
    "explanation_detail"?: "brief" | "detailed"
    "feedback_form"?: "inline" | "expandable"
    "format"?: "text" | "stepwise"
    "pace"?: "self_paced" | "stepwise"
    "personalisation_enabled"?: boolean
    "repeat_practice"?: boolean
    "support_amount"?: "standard" | "on_request"
  }
  "QualityReviewDecision": "APPROVED" | "REJECTED"
  "ReadinessResponse": {
    "checks": Partial<Record<string, "ready" | "not_ready">>
    "status": "ready" | "not_ready"
  }
  "RecentActivityRead": {
    "formal_assessment"?: (ApiSchemas["FormalAssessmentSummary"]) | (null)
    "occurred_at": string
    "score": (number) | (null)
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
  "ResponseContent": {
    "answer"?: string
    "circuit"?: (Partial<Record<string, ApiSchemas["JsonValue"]>>) | (null)
    "code"?: (string) | (null)
  }
  "ResponseFieldEvidence": {
    "content_digest": string
    "path": string
    "recorded": boolean
    "response_version_id": string
    "statement": string
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
    "valid_from"?: (string) | (null)
    "valid_until"?: (string) | (null)
  }
  "ScopedRoleAssignmentHistoryRead": {
    "assigned_at": string
    "assigned_by_user_id": number
    "course_id": string
    "currently_active": boolean
    "eligibility_approval_id": (string) | (null)
    "id": string
    "reason": string
    "revocation_reason": (string) | (null)
    "revoked_at": (string) | (null)
    "revoked_by_user_id": (number) | (null)
    "role": ApiSchemas["ScopedRole"]
    "subject_user_id": number
    "valid_from": string
    "valid_until": (string) | (null)
    "version": number
  }
  "ScopedRoleAssignmentRead": {
    "assigned_at": string
    "assigned_by_user_id": number
    "course_id": string
    "eligibility_approval_id": (string) | (null)
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
  "SimulationProvenance": {
    "circuit_version_id": string
    "engine_versions": Partial<Record<string, string>>
    "episode_stage_start_id": (string) | (null)
    "policy_version": string
    "prediction_checkpoint_id": (string) | (null)
    "result_digest": string
    "run_id": string
    "status": string
  }
  "SimulationRead": {
    "circuit_text": string
    "counts": Partial<Record<string, number>>
    "engine": string
    "engine_versions"?: Partial<Record<string, string>>
    "measurement_mapping"?: Array<Array<number>>
    "policy_version"?: string
    "probabilities": Partial<Record<string, number>>
    "probability_method"?: "exact_statevector"
    "qubit_order"?: Array<number>
    "sampled_frequencies"?: Partial<Record<string, number>>
    "seed"?: number
    "shots"?: number
    "statevector"?: Array<Array<number>>
  }
  "SimulationReference": {
    "circuit_version_id": string
    "run_id": string
  }
  "SimulationRequest": {
    "episode_part_id"?: (string) | (null)
    "episode_stage_start_id"?: (string) | (null)
    "operations"?: Array<ApiSchemas["GateOperation"]>
    "prediction_checkpoint_id"?: (string) | (null)
    "qubits"?: number
    "request_key"?: (string) | (null)
    "seed"?: number
    "shots"?: number
    "task_id"?: (string) | (null)
  }
  "SimulationRunRead": {
    "circuit": Record<string, unknown>
    "circuit_version_id": string
    "content_digest": string
    "course_id": (string) | (null)
    "created_at": string
    "deadline_at": string
    "engine_versions": Partial<Record<string, string>>
    "episode_stage_start_id"?: (string) | (null)
    "error_code": (string) | (null)
    "finished_at": (string) | (null)
    "owner_id": number
    "policy_version": string
    "prediction_checkpoint_id"?: (string) | (null)
    "purpose": "practice" | "task" | "feedback"
    "result": (ApiSchemas["SimulationRead"]) | (null)
    "run_id": string
    "seed": number
    "shots": number
    "status": "pending" | "completed" | "failed" | "timed_out" | "interrupted"
    "submission_id": (string) | (null)
    "task_id": (string) | (null)
  }
  "SourceApprovalRead": {
    "actor_id": string
    "created_at": string
    "id": string
    "reason": string
    "revision_id": string
    "sequence": number
    "state": string
  }
  "SourceApprovalRequest": {
    "expected_sequence"?: (number) | (null)
    "reason": string
    "state": string
  }
  "SourcePassageRead": {
    "chunk_hash": string
    "chunk_index": number
    "chunk_text": string
    "course_id": string
    "heading": (string) | (null)
    "id": string
    "location_label": (string) | (null)
    "revision_id": string
  }
  "SourceRevisionRead": {
    "approval_state"?: string
    "approvals"?: Array<ApiSchemas["SourceApprovalRead"]>
    "content_hash": string
    "course_id": string
    "created_at": string
    "extraction_version": string
    "id": string
    "material_id": string
    "mime_type": string
    "module_id": (string) | (null)
    "passages"?: Array<ApiSchemas["SourcePassageRead"]>
    "provenance": string
    "source_label": string
    "storage_key": (string) | (null)
    "version": number
  }
  "SourceUseRead": {
    "approval_id": (string) | (null)
    "course_id": string
    "created_at": string
    "id": string
    "material_id": string
    "output_id": string
    "output_type": string
    "output_version": string
    "passage_id": string
    "revision_id": string
    "source_id": string
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
    "average_score": (number) | (null)
    "completed_tasks": number
    "completion_percentage": number
    "level": number
    "next_level_points": number
    "points": number
    "total_tasks": number
  }
  "SubmissionCreate": {
    "answer"?: string
    "assessment_work_start_id"?: (string) | (null)
    "circuit"?: (Record<string, unknown>) | (null)
    "code"?: (string) | (null)
    "episode"?: (ApiSchemas["EpisodePayloadV1"]) | (null)
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
    "episode_plan"?: (Record<string, unknown>) | (null)
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
  "TaskReviewEventRead": {
    "actor_user_id": number
    "course_id": string
    "created_at": string
    "id": string
    "policy_version": string
    "reason": string
    "source_approvals": Partial<Record<string, string>>
    "state": "SUBMITTED" | "APPROVED" | "REJECTED" | "WITHDRAWN"
    "task_revision_id": string
    "version": number
  }
  "TaskReviewHistoryRead": {
    "events": Array<ApiSchemas["TaskReviewEventRead"]>
    "revision": ApiSchemas["TaskRevisionRead"]
  }
  "TaskReviewSummary": {
    "available": boolean
    "content_digest": (string) | (null)
    "issues": Array<string>
    "review_version": number
    "revision": number
    "revision_id": (string) | (null)
    "state": "DRAFT" | "SUBMITTED" | "APPROVED" | "REJECTED" | "WITHDRAWN"
  }
  "TaskReviewWrite": {
    "expected_review_version": number
    "expected_revision_id": string
    "reason": string
    "state": "SUBMITTED" | "APPROVED" | "REJECTED" | "WITHDRAWN"
  }
  "TaskRevisionRead": {
    "actor_user_id": (number) | (null)
    "content_digest": string
    "course_id": string
    "created_at": string
    "id": string
    "provenance": "AUTHORED" | "GENERATED" | "LEGACY"
    "snapshot": Record<string, unknown>
    "task_id": string
    "version": number
  }
  "TaskType": "prediction" | "reasoning" | "explanation" | "revision" | "reflection" | "transfer" | "multiple_choice" | "multiple_answer" | "short_answer" | "code_explanation" | "code_completion" | "quantum_circuit" | "quiz" | "code" | "circuit"
  "TaskUpdate": {
    "difficulty"?: ("beginner" | "intermediate" | "advanced") | (null)
    "due_at"?: (string) | (null)
    "expected_answer"?: (string) | (null)
    "expected_revision_id"?: (string) | (null)
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
  "TransferResponseV1": {
    "content": ApiSchemas["ResponseContent"]
    "part_id": string
    "process": ApiSchemas["EpisodeStageResponseV1"]
    "stage_start_id": string
  }
  "UnresolvedAssessmentRead": {
    "assessment_attempt_id": string
    "can_finalise": boolean
    "course_id": string
    "created_at": string
    "criteria": Array<ApiSchemas["UnresolvedCriterionRead"]>
    "expected_token": string
    "failure_category": (ApiSchemas["AssessmentEvaluationFailureCategory"]) | (null)
    "frozen_context"?: (ApiSchemas["FrozenAssessmentContextRead"]) | (null)
    "historical_evidence"?: Array<ApiSchemas["HistoricalResponseEvidenceRead"]>
    "history": Array<ApiSchemas["HumanActionHistoryRead"]>
    "issues": Array<string>
    "job_state": (ApiSchemas["AssessmentEvaluationJobState"]) | (null)
    "response": (ApiSchemas["FrozenResponseRead"]) | (null)
    "response_history"?: Array<ApiSchemas["FrozenResponseRead"]>
    "simulations": Array<Record<string, unknown>>
    "state": ApiSchemas["AssessmentAttemptState"]
    "versions": Record<string, unknown>
  }
  "UnresolvedCriterionRead": {
    "approved_anchors": (Record<string, unknown>) | (Array<unknown>)
    "criterion_version": number
    "criterion_version_id": string
    "critical_error_rules": (Record<string, unknown>) | (Array<unknown>)
    "decision": (ApiSchemas["CriterionDecision"]) | (null)
    "evaluator_type": ApiSchemas["CriterionEvaluatorType"]
    "evidence_description": string
    "evidence_source_types": Array<string>
    "learner_description": string
    "mandatory": boolean
    "met_rule": string
    "not_evaluable_rule": string
    "not_met_rule": string
    "reason": (string) | (null)
  }
  "UserRole": "student" | "educator" | "administrator"
  "ValidatedFeedbackView": {
    "ai_generated_notice": string
    "assessed"?: (ApiSchemas["AssessedFeedbackView"]) | (null)
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
