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
  "ActivityAction": {
    "action": "accept" | "defer" | "replace" | "educator_override"
    "expected_version": number
    "reason"?: string
    "request_key": string
    "task_id"?: (string) | (null)
  }
  "ActivityHistory": {
    "action": string
    "created_at": string
    "educator": boolean
    "reason": string
    "task_id": (string) | (null)
    "version": number
  }
  "ActivityOption": {
    "support_level": (string) | (null)
    "task_id": string
    "title": string
  }
  "ActivityRead": {
    "can_override"?: boolean
    "evidence_ids"?: Array<string>
    "history"?: Array<ApiSchemas["ActivityHistory"]>
    "learner_label"?: string
    "next_task_id"?: (string) | (null)
    "options"?: Array<ApiSchemas["ActivityOption"]>
    "pathway_id"?: (string) | (null)
    "preference_version"?: (number) | (null)
    "reason": string
    "rule_version"?: string
    "snapshot_id"?: (string) | (null)
    "state": string
    "uncertainty"?: (number) | (null)
    "version"?: number
    "workflow_id": string
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
  "AppealResolutionWrite": {
    "expected_decision_revision": number
    "learner_notice": string
    "reason": string
  }
  "ApprovalDecision": {
    "authority_reference": string
    "evidence_reference": string
    "kind"?: "approval"
    "scope_id": string
    "state": "approved" | "suspended" | "revoked" | "pending"
    "valid_from": string
    "valid_until": string
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
  "ConsentDecision": {
    "consent_version": string
    "course_id": string
    "decision": "consented" | "declined" | "withdrawn"
    "fields"?: Array<("case_id" | "pseudonymous_user_id" | "course_id" | "task_id" | "task_type" | "submission_reference" | "experimental_condition" | "judge_decision" | "correctness_score" | "relevance_score" | "grounding_score" | "actionability_score" | "safety_score" | "unsupported_claim_count" | "latency_ms" | "input_tokens" | "output_tokens" | "total_tokens" | "estimated_cost" | "regeneration_count" | "fallback_used" | "status" | "comparable" | "usage_complete" | "measurement_schema_version" | "created_at" | "completed_at" | "processing.technical_pair" | "processing.provider_input" | "processing.generated_output" | "processing.judge_result" | "processing.input_references" | "processing.retrieved_sources" | "processing.simulation_reference") | ("instrument.define" | "instrument.collect" | "instrument.read" | "instrument.export" | "instrument.record_id" | "instrument.participant_id" | "instrument.course_ref" | "instrument.sequence_id" | "instrument.form_id" | "instrument.form_version" | "instrument.item_id" | "instrument.stage" | "instrument.outcome_ref" | "instrument.task_ref" | "instrument.response_ref" | "instrument.choice_code" | "instrument.integer_value" | "instrument.response_text" | "instrument.missing_reason" | "instrument.event_kind" | "instrument.reason_code" | "instrument.revision" | "instrument.supersedes_id" | "instrument.correction_reason_code")>
    "kind"?: "consent"
    "purposes"?: Array<"technical_pair" | "provider_processing" | "study_instruments">
    "scope_id": string
    "subject_user_id": number
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
    "time_zone"?: string
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
    "time_zone"?: string
    "title": string
    "updated_at": string
  }
  "CourseState": "draft" | "published" | "archived"
  "CourseUpdate": {
    "code"?: (string) | (null)
    "description"?: (string) | (null)
    "enrollment_open"?: (boolean) | (null)
    "time_zone"?: (string) | (null)
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
  "DeadlineArrangementRead": {
    "active": boolean
    "created_at": string
    "due_at": (string) | (null)
    "id": string
    "kind": "EXTENSION" | "ACCESS_PLAN"
    "learner_notice": string
    "reason": string
    "reminders_paused": boolean
    "revision": number
    "time_zone": string
  }
  "DeadlineArrangementWrite": {
    "active"?: boolean
    "expected_revision": number
    "fold"?: (0 | 1) | (null)
    "idempotency_key": string
    "kind": "EXTENSION" | "ACCESS_PLAN"
    "learner_notice": string
    "local_due_at"?: (string) | (null)
    "reason": string
    "reminders_paused"?: boolean
    "time_zone": string
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
    "courses": Array<ApiSchemas["CourseRead"]>
    "leaderboard": Array<ApiSchemas["LeaderboardEntryRead"]>
    "recent_activity": Array<ApiSchemas["RecentActivityRead"]>
    "total_students": number
    "weekly_engagement": Array<ApiSchemas["WeeklyEngagementRead"]>
  }
  "EducatorStudentRead": {
    "at_risk": boolean
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
  "EligibilityDecision": {
    "course_id": string
    "eligible": boolean
    "evidence_reference": string
    "kind"?: "eligibility"
    "rule_version": string
    "scope_id": string
    "subject_user_id": number
    "valid_until": string
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
  "EquivalentFormRead": {
    "id": string
    "task_id": string
    "task_title": string
  }
  "EquivalentFormWrite": {
    "reason": string
    "revision_id": string
    "task_id": string
    "template_form_id": string
  }
  "EscalationActionWrite": {
    "acknowledgement_due_at": string
    "expected_revision": number
    "idempotency_key": string
    "learner_notice": string
    "owner_user_id": number
    "reason": string
    "resolution_due_at": string
    "severity": "NORMAL" | "HIGH" | "CRITICAL"
    "status": "OPEN" | "ACKNOWLEDGED" | "ACTIONED" | "RESOLVED" | "CLOSED"
  }
  "EscalationHistoryEntry": {
    "actor_user_id": number
    "at": string
    "owner_user_id": number
    "queue_revision_id": string
    "reason": string
    "revision": number
    "status": "OPEN" | "ACKNOWLEDGED" | "ACTIONED" | "RESOLVED" | "CLOSED"
  }
  "EscalationNotice": {
    "created_at": string
    "learner_notice": string
    "revision": number
    "status": "OPEN" | "ACKNOWLEDGED" | "ACTIONED" | "RESOLVED" | "CLOSED"
  }
  "EscalationQueueRead": {
    "configuration": (ApiSchemas["QueueRead"]) | (null)
    "course_id": string
    "course_title": string
    "eligible_members": Array<ApiSchemas["QueueMember"]>
    "kind": "ASSESSOR" | "TECHNICAL"
  }
  "EscalationRead": {
    "acknowledgement_due_at": (string) | (null)
    "created_at": string
    "id": string
    "notices": Array<ApiSchemas["EscalationNotice"]>
    "queue_kind": "ASSESSOR" | "TECHNICAL"
    "resolution_due_at": (string) | (null)
    "revision": number
    "severity": "NORMAL" | "HIGH" | "CRITICAL"
    "source_id": string
    "source_kind": "FEEDBACK" | "TUTOR" | "ASSESSMENT"
    "status": "OPEN" | "ACKNOWLEDGED" | "ACTIONED" | "RESOLVED" | "CLOSED"
    "task_id": string
  }
  "EscalationStaffRead": {
    "acknowledgement_due_at": (string) | (null)
    "attention": "NEEDS_TRIAGE" | "ACKNOWLEDGEMENT_OVERDUE" | "RESOLUTION_OVERDUE" | "ON_TARGET" | "COMPLETE"
    "backup_user_id": (number) | (null)
    "created_at": string
    "history": Array<ApiSchemas["EscalationHistoryEntry"]>
    "id": string
    "notices": Array<ApiSchemas["EscalationNotice"]>
    "owner_user_id": (number) | (null)
    "queue_kind": "ASSESSOR" | "TECHNICAL"
    "reason": string
    "resolution_due_at": (string) | (null)
    "revision": number
    "severity": "NORMAL" | "HIGH" | "CRITICAL"
    "source_id": string
    "source_kind": "FEEDBACK" | "TUTOR" | "ASSESSMENT"
    "status": "OPEN" | "ACKNOWLEDGED" | "ACTIONED" | "RESOLVED" | "CLOSED"
    "task_id": string
    "trigger": string
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
  "ExplanationDetail": "BRIEF" | "STANDARD" | "DETAILED"
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
  "FeedbackResponseClassification": "not_evaluated" | "correct" | "partially_correct" | "incorrect"
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
  "FormFreeze": {
    "content_digest": string
    "request_key": string
    "synthetic_review_reference": string
  }
  "FormRead": {
    "content_digest": string
    "definition": ApiSchemas["InstrumentDefinition"]
    "frozen_for_synthetic_validation": boolean
    "id": string
    "production_active"?: false
    "version": number
  }
  "FormWrite": {
    "definition": ApiSchemas["InstrumentDefinition"]
    "expected_version": number
    "request_key": string
  }
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
  "FreshTaskRead": {
    "instructions": string
    "prompt": string
    "revision_id": string
    "task_id": string
    "title": string
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
    "recorded_teaching"?: Array<ApiSchemas["RecordedTeachingRead"]>
    "reference": ApiSchemas["EvidenceReference"]
    "task_form_version_id": (string) | (null)
  }
  "FunnelStage": {
    "count": number
    "event_type": ApiSchemas["LearningEventType"]
    "previous_stage_rate": ApiSchemas["MetricValue"]
  }
  "GamificationPreferenceRead": {
    "enabled": boolean
    "revision": number
  }
  "GamificationPreferenceWrite": {
    "enabled": boolean
    "expected_revision": number
    "idempotency_key": string
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
  "GovernanceCommand": {
    "decision": (ApiSchemas["StudyScope"]) | (ApiSchemas["ApprovalDecision"]) | (ApiSchemas["ConsentDecision"]) | (ApiSchemas["EligibilityDecision"]) | (ApiSchemas["ResearchGrant"]) | (ApiSchemas["RetentionHold"])
    "expected_revision": number
    "reason": string
    "request_key": string
  }
  "GovernanceHistoryEntry": {
    "actor_user_id": number
    "command": ApiSchemas["GovernanceCommand"]
    "id": string
    "kind": string
    "production_active"?: false
    "recorded_at": string
    "revision": number
    "study_id": string
  }
  "GovernanceReceipt": {
    "id": string
    "kind": string
    "production_active"?: false
    "recorded_at": string
    "revision": number
    "study_id": string
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
  "InstructionalSupportLevel": 0 | 1 | 2 | 3 | 4 | 5
  "InstrumentAnswer": {
    "choice_code"?: (string) | (null)
    "integer_value"?: (number) | (null)
    "item_id": string
    "missing_reason"?: ("not_collected" | "not_applicable" | "participant_skipped" | "technical_failure" | "not_evaluable" | "outside_window" | "withdrawn" | "not_approved") | (null)
    "response_text"?: (string) | (null)
  }
  "InstrumentDefinition": {
    "event_reason_codes": Array<string>
    "instrument_kind": "conceptual" | "transfer" | "retention" | "learner_experience" | "educator_review" | "process"
    "items": Array<ApiSchemas["InstrumentItem"]>
    "review_status"?: "DRAFT_FOR_REVIEW"
    "schema_version"?: "learnlens.instrument-definition.v1"
    "stages": Array<"T0_BASELINE" | "T1_STUDY_ACTIVITY" | "T1_FORMAL_SUPPORTED" | "T1_FORMAL_UNAIDED" | "T2_CONCEPTUAL" | "T2_TRANSFER" | "T3_CONCEPTUAL" | "T3_TRANSFER">
    "support_manifest_reference": string
    "synthetic_only"?: true
    "title": string
  }
  "InstrumentExportRequest": {
    "fields": Array<"instrument.record_id" | "instrument.participant_id" | "instrument.course_ref" | "instrument.sequence_id" | "instrument.form_id" | "instrument.form_version" | "instrument.item_id" | "instrument.stage" | "instrument.outcome_ref" | "instrument.task_ref" | "instrument.response_ref" | "instrument.choice_code" | "instrument.integer_value" | "instrument.missing_reason" | "instrument.event_kind" | "instrument.reason_code" | "instrument.revision" | "instrument.supersedes_id" | "instrument.correction_reason_code">
    "format": "csv" | "json"
    "stages": Array<"T0_BASELINE" | "T1_STUDY_ACTIVITY" | "T1_FORMAL_SUPPORTED" | "T1_FORMAL_UNAIDED" | "T2_CONCEPTUAL" | "T2_TRANSFER" | "T3_CONCEPTUAL" | "T3_TRANSFER">
  }
  "InstrumentItem": {
    "choices"?: Array<string>
    "item_id": string
    "max_characters"?: (number) | (null)
    "maximum"?: (number) | (null)
    "minimum"?: (number) | (null)
    "prompt": string
    "response_type": "choice" | "integer" | "text"
  }
  "InstrumentReceipt": {
    "id": string
    "production_active"?: false
    "recorded_at": string
    "revision": number
  }
  "InstrumentRecordWrite": {
    "answers"?: Array<ApiSchemas["InstrumentAnswer"]>
    "correction_reason_code"?: (string) | (null)
    "form_version_id": string
    "kind": "response" | "missingness" | "attrition" | "deviation"
    "links"?: ApiSchemas["LearningStageLinks"]
    "missing_reason"?: ("not_collected" | "not_applicable" | "participant_skipped" | "technical_failure" | "not_evaluable" | "outside_window" | "withdrawn" | "not_approved") | (null)
    "reason_code"?: (string) | (null)
    "request_key": string
    "sequence_key": string
    "stage": "T0_BASELINE" | "T1_STUDY_ACTIVITY" | "T1_FORMAL_SUPPORTED" | "T1_FORMAL_UNAIDED" | "T2_CONCEPTUAL" | "T2_TRANSFER" | "T3_CONCEPTUAL" | "T3_TRANSFER"
    "subject_user_id": number
    "supersedes_id"?: (string) | (null)
  }
  "InvalidEvidenceReference": {
    "reason_code": string
    "reference_id"?: (string) | (null)
    "status"?: "INVALID"
  }
  "JsonValue": unknown
  "JudgeDecision": "pass" | "fail"
  "LatestAttemptSummary": {
    "attempt_number": number
    "formal_assessment"?: (ApiSchemas["FormalAssessmentSummary"]) | (null)
    "id": string
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
  "LearnerAppealRead": {
    "decision_id": string
    "decision_revision": number
    "id": string
    "learner_notice"?: (string) | (null)
    "reason": string
    "request_kind": string
    "requested_at": string
    "resolved_at"?: (string) | (null)
    "response_version_id": string
    "state": string
  }
  "LearnerAppealWrite": {
    "idempotency_key": string
    "reason": string
    "request_kind"?: "REVIEW" | "CORRECTION" | "APPEAL"
  }
  "LearnerCriterionRead": {
    "decision"?: (ApiSchemas["CriterionDecision"]) | (null)
    "description": string
    "evidence_description": string
    "id": string
    "mandatory": boolean
  }
  "LearnerDeadlineRead": {
    "arrangement_active"?: boolean
    "effective_due_at": (string) | (null)
    "learner_notice"?: (string) | (null)
    "original_due_at": (string) | (null)
    "reminders_paused": boolean
    "task_id": string
    "time_zone": string
  }
  "LearnerDecisionEventRead": {
    "action": string
    "at": string
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
  "LearnerPreferencesRead": {
    "explanation_detail": ApiSchemas["ExplanationDetail"]
    "format": ApiSchemas["PreferenceFormat"]
    "optional_breaks_enabled": boolean
    "pace": ApiSchemas["PreferencePace"]
    "personalisation_enabled": boolean
    "repeat_practice_enabled": boolean
    "revision": number
    "saved": boolean
    "saved_at"?: (string) | (null)
    "schema_version"?: string
  }
  "LearnerPreferencesWrite": {
    "expected_revision": number
    "explanation_detail": ApiSchemas["ExplanationDetail"]
    "format": ApiSchemas["PreferenceFormat"]
    "idempotency_key": string
    "optional_breaks_enabled": boolean
    "pace": ApiSchemas["PreferencePace"]
    "personalisation_enabled": boolean
    "repeat_practice_enabled": boolean
  }
  "LearnerResultRead": {
    "assessment_attempt_id": string
    "bloom_process": ApiSchemas["BloomProcess"]
    "can_request_review": boolean
    "criteria": Array<ApiSchemas["LearnerCriterionRead"]>
    "decision_id": (string) | (null)
    "evidence_response_id": string
    "history": Array<ApiSchemas["LearnerDecisionEventRead"]>
    "next_action": string
    "outcome": string
    "reason": string
    "requests": Array<ApiSchemas["LearnerAppealRead"]>
    "response_version_id": string
    "result": (ApiSchemas["AssessmentResult"]) | (null)
    "review_revision": number
    "status": string
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
  "LearningProgressPage": {
    "cohort_observations": Partial<Record<string, number>>
    "cohort_weekly_observations": Partial<Record<string, Partial<Record<string, number>>>>
    "cohort_weekly_trends": Partial<Record<string, Partial<Record<string, number>>>>
    "course_id": string
    "course_title": string
    "generated_at": string
    "history_limit"?: number
    "items": Array<ApiSchemas["ProgressScopeRead"]>
    "next_offset": (number) | (null)
  }
  "LearningStageLinks": {
    "outcome_id"?: (string) | (null)
    "response_id"?: (string) | (null)
    "task_id"?: (string) | (null)
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
  "MisconceptionAnswer": {
    "answer": string
    "confidence": number
    "expected_version": number
    "help_used": boolean
    "reasoning": string
    "request_key": string
    "stage": "PROBE" | "REVISION" | "TRANSFER"
    "start_fresh_check"?: boolean
  }
  "MisconceptionCandidateRead": {
    "course_title": string
    "evidence": Array<ApiSchemas["MisconceptionEvidenceRead"]>
    "feedback_id": string
    "response": string
    "student_id": number
    "student_name": string
    "task_id": string
    "task_title": string
  }
  "MisconceptionClosureRead": {
    "actor_id": number
    "created_at": string
    "disposition": "DEFERRED" | "INVALIDATED"
    "reason": string
  }
  "MisconceptionEvidenceRead": {
    "content": string
    "id": string
    "kind": string
  }
  "MisconceptionExit": {
    "disposition": "DEFERRED" | "INVALIDATED"
    "expected_version": number
    "reason": string
    "request_key": string
  }
  "MisconceptionOpen": {
    "confidence": number
    "content_approval_reason": string
    "evidence_ids": Array<string>
    "explanation": string
    "explanation_support_level": ApiSchemas["InstructionalSupportLevel"]
    "feedback_id": string
    "fresh_question": string
    "hypothesis": string
    "persistence_stages": Array<"PROBE" | "REVISION" | "TRANSFER">
    "probe": string
    "request_key": string
    "selection_reason": string
  }
  "MisconceptionRead": {
    "approved_at": string
    "approved_by": number
    "closure": (ApiSchemas["MisconceptionClosureRead"]) | (null)
    "confidence": number
    "content_approval_reason": string
    "course_id": string
    "evidence_ids": Array<string>
    "explanation": (string) | (null)
    "fresh_question": (string) | (null)
    "hypothesis": string
    "id": string
    "initial_evidence": Array<ApiSchemas["MisconceptionEvidenceRead"]>
    "next_stage": ("PROBE" | "REVISION" | "TRANSFER") | (null)
    "outcome_id": string
    "persistence_stages": Array<"PROBE" | "REVISION" | "TRANSFER">
    "probe": (string) | (null)
    "responses": Array<ApiSchemas["MisconceptionResponseRead"]>
    "reviews": Array<ApiSchemas["MisconceptionReviewRead"]>
    "selection_reason": string
    "state": ApiSchemas["MisconceptionState"]
    "student_id": number
    "task_id": string
    "teaching_available": boolean
    "version": number
  }
  "MisconceptionResponseRead": {
    "answer": string
    "confidence": number
    "created_at": string
    "evidence_id": string
    "help_used": boolean
    "id": string
    "reasoning": string
    "stage": "PROBE" | "REVISION" | "TRANSFER"
    "version": number
  }
  "MisconceptionReview": {
    "confidence": number
    "contradicts"?: Array<string>
    "expected_version": number
    "next_action": string
    "reason": string
    "request_key": string
    "state": ApiSchemas["MisconceptionState"]
    "supports"?: Array<string>
  }
  "MisconceptionReviewRead": {
    "actor_id": number
    "confidence": number
    "contradicts": Array<string>
    "created_at": string
    "escalation_id": (string) | (null)
    "evidence_id": string
    "id": string
    "next_action": string
    "reason": string
    "snapshot_id": string
    "state": ApiSchemas["MisconceptionState"]
    "supports": Array<string>
    "version": number
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
  "OutcomePolicyRead": {
    "created_at": string
    "definition_version_id": string
    "id": string
    "reason": string
    "required_form_ids"?: Array<string>
    "selection_rule": "LATEST_VALID" | "ANY_VALID_PASS" | "ALL_REQUIRED_FORMS"
  }
  "OutcomePolicyWrite": {
    "reason": string
    "required_form_ids"?: Array<string>
    "selection_rule": "LATEST_VALID" | "ANY_VALID_PASS" | "ALL_REQUIRED_FORMS"
  }
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
  "OutcomeResultRead": {
    "authorisations": Array<ApiSchemas["ReassessmentRead"]>
    "definition_version_id": string
    "evidence_response_ids": Array<string>
    "explanation": string
    "result": (ApiSchemas["AssessmentResult"]) | (null)
    "selection_rule": ("LATEST_VALID" | "ANY_VALID_PASS" | "ALL_REQUIRED_FORMS") | (null)
    "status": string
  }
  "OutcomeUpdate": {
    "kind"?: (ApiSchemas["OutcomeKind"]) | (null)
    "position"?: (number) | (null)
    "statement"?: (string) | (null)
    "title"?: (string) | (null)
    "week_number"?: (number) | (null)
  }
  "OutputReportWrite": {
    "idempotency_key": string
    "queue_kind": "ASSESSOR" | "TECHNICAL"
    "reason": string
    "severity"?: "NORMAL" | "HIGH" | "CRITICAL"
    "source_id": string
    "source_kind": "FEEDBACK" | "TUTOR"
  }
  "PairedDifferences": {
    "cost": ApiSchemas["MetricValue"]
    "latency_ms": ApiSchemas["MetricValue"]
    "pass_rate": ApiSchemas["MetricValue"]
    "relevance": ApiSchemas["MetricValue"]
    "total_tokens": ApiSchemas["MetricValue"]
  }
  "ParticipationRead": {
    "consent": (ApiSchemas["ConsentDecision"]) | (null)
    "production_active"?: false
    "revision": number
    "scope": ApiSchemas["StudyScope"]
    "scope_id": string
    "study_id": string
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
  "PreferenceFormat": "NO_PREFERENCE" | "TEXT" | "VISUAL" | "WORKED_EXAMPLE" | "CIRCUIT" | "STEPWISE"
  "PreferenceHistory": {
    "items": Array<ApiSchemas["PreferenceRevision"]>
    "next_offset": (number) | (null)
  }
  "PreferencePace": "DEFAULT" | "SLOWER" | "FASTER"
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
  "ProgressAdaptation": {
    "choices": Array<ApiSchemas["ProgressChoice"]>
    "evidence_ids": Array<string>
    "occurred_at": string
    "reason": string
    "snapshot_id": (string) | (null)
    "state": string
    "uncertainty": number
    "workflow_id": string
  }
  "ProgressChoice": {
    "action": string
    "created_at": string
    "educator": boolean
    "reason": string
    "task_id": (string) | (null)
    "version": number
  }
  "ProgressEstimate": {
    "dimension": string
    "estimate_id": string
    "evidence": Array<ApiSchemas["ProgressEvidenceLink"]>
    "occurred_at": string
    "prior_snapshot_id": (string) | (null)
    "reason": string
    "snapshot_id": string
    "status": string
    "uncertainty": number
  }
  "ProgressEvidenceDetail": {
    "confidence"?: (number) | (string) | (null)
    "course_id": string
    "evidence_id": string
    "fields": Array<ApiSchemas["ProgressEvidenceField"]>
    "kind": string
    "learner_id": number
    "occurred_at": string
    "outcome_id": string
    "related_evidence_ids": Array<string>
    "response_id": (string) | (null)
    "status": string
    "support_level": number
    "task_id": string
  }
  "ProgressEvidenceField": {
    "label": string
    "text": string
  }
  "ProgressEvidenceLink": {
    "evidence_id": string
    "relation": string
  }
  "ProgressObservation": {
    "confidence"?: (number) | (string) | (null)
    "evidence_id": string
    "kind": string
    "occurred_at": string
    "response_id": (string) | (null)
    "support_level": number
    "task_id": string
  }
  "ProgressOutcome": {
    "definition_version_id": string
    "evidence_response_ids": Array<string>
    "explanation": string
    "result": (ApiSchemas["AssessmentResult"]) | (null)
    "selection_rule": (string) | (null)
    "status": string
  }
  "ProgressResult": {
    "occurred_at": string
    "response_id": string
    "result": (ApiSchemas["AssessmentResult"]) | (null)
    "status": string
    "task_id": string
  }
  "ProgressScopeRead": {
    "adaptations": Array<ApiSchemas["ProgressAdaptation"]>
    "estimates": Array<ApiSchemas["ProgressEstimate"]>
    "independent_responses": number
    "learner_id": number
    "learner_name": string
    "misconception_ids": Array<string>
    "observations": Partial<Record<string, number>>
    "outcome_id": string
    "outcome_results": Array<ApiSchemas["ProgressOutcome"]>
    "outcome_title": string
    "recent_evidence": Array<ApiSchemas["ProgressObservation"]>
    "results": Array<ApiSchemas["ProgressResult"]>
    "supported_responses": number
    "weekly_observations": Partial<Record<string, Partial<Record<string, number>>>>
  }
  "ProgressTrendPage": {
    "items": Array<ApiSchemas["ProgressTrendRecord"]>
    "next_offset": (number) | (null)
  }
  "ProgressTrendRecord": {
    "estimate_id": (string) | (null)
    "evidence_id": (string) | (null)
    "evidence_ids": Array<string>
    "id": string
    "kind": string
    "learner_id": number
    "learner_name": string
    "occurred_at": string
    "outcome_id": string
    "reason": (string) | (null)
    "response_id": (string) | (null)
    "task_id": (string) | (null)
    "uncertainty": (number) | (null)
    "workflow_id": (string) | (null)
  }
  "QualityReviewDecision": "APPROVED" | "REJECTED"
  "QueueMember": {
    "id": number
    "name": string
  }
  "QueueRead": {
    "acknowledgement_target": string
    "backup_user_id": number
    "id": string
    "primary_user_id": number
    "resolution_target": string
    "revision": number
  }
  "QueueWrite": {
    "acknowledgement_target": string
    "backup_user_id": number
    "expected_revision": number
    "primary_user_id": number
    "reason": string
    "resolution_target": string
  }
  "ReadinessResponse": {
    "checks": Partial<Record<string, "ready" | "not_ready">>
    "status": "ready" | "not_ready"
  }
  "ReassessmentRead": {
    "available": boolean
    "created_at": string
    "id": string
    "learner_notice": string
    "replacement_response_id": (string) | (null)
    "task_id": string
    "task_title": string
  }
  "ReassessmentSetup": {
    "authorisation": (ApiSchemas["ReassessmentRead"]) | (null)
    "definition_version_id": string
    "forms": Array<ApiSchemas["EquivalentFormRead"]>
    "fresh_tasks": Array<ApiSchemas["FreshTaskRead"]>
    "policy": (ApiSchemas["OutcomePolicyRead"]) | (null)
    "policy_forms": Array<ApiSchemas["EquivalentFormRead"]>
  }
  "ReassessmentWrite": {
    "expected_decision_revision": number
    "learner_notice": string
    "reason": string
    "task_form_version_id": string
  }
  "RecentActivityRead": {
    "formal_assessment"?: (ApiSchemas["FormalAssessmentSummary"]) | (null)
    "occurred_at": string
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
  "RecordedTeachingRead": {
    "during_transfer": boolean
    "evidence_id": string
    "explanation": string
    "hypothesis_id": string
    "instructional_support_level": number
    "occurred_at": string
  }
  "ReminderPreferenceRead": {
    "enabled"?: boolean
    "paused_until"?: (string) | (null)
    "revision"?: number
  }
  "ReminderPreferenceWrite": {
    "enabled": boolean
    "expected_revision": number
    "idempotency_key": string
    "paused_until"?: (string) | (null)
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
  "ResearchGrant": {
    "authority_reference": string
    "course_id": string
    "evidence_reference": string
    "fields": Array<("case_id" | "pseudonymous_user_id" | "course_id" | "task_id" | "task_type" | "submission_reference" | "experimental_condition" | "judge_decision" | "correctness_score" | "relevance_score" | "grounding_score" | "actionability_score" | "safety_score" | "unsupported_claim_count" | "latency_ms" | "input_tokens" | "output_tokens" | "total_tokens" | "estimated_cost" | "regeneration_count" | "fallback_used" | "status" | "comparable" | "usage_complete" | "measurement_schema_version" | "created_at" | "completed_at" | "processing.technical_pair" | "processing.provider_input" | "processing.generated_output" | "processing.judge_result" | "processing.input_references" | "processing.retrieved_sources" | "processing.simulation_reference") | ("instrument.define" | "instrument.collect" | "instrument.read" | "instrument.export" | "instrument.record_id" | "instrument.participant_id" | "instrument.course_ref" | "instrument.sequence_id" | "instrument.form_id" | "instrument.form_version" | "instrument.item_id" | "instrument.stage" | "instrument.outcome_ref" | "instrument.task_ref" | "instrument.response_ref" | "instrument.choice_code" | "instrument.integer_value" | "instrument.response_text" | "instrument.missing_reason" | "instrument.event_kind" | "instrument.reason_code" | "instrument.revision" | "instrument.supersedes_id" | "instrument.correction_reason_code")>
    "kind"?: "grant"
    "revoked"?: boolean
    "scope_id": string
    "subject_user_id": number
    "valid_from": string
    "valid_until": string
  }
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
  "RetentionClass": {
    "authority_reference": string
    "authority_version": string
    "owner_reference": string
    "record_class": string
    "retention_rule": string
    "review_at": string
    "trigger": string
  }
  "RetentionHold": {
    "active": boolean
    "authority_reference": string
    "hold_reference": string
    "kind"?: "hold"
    "record_class": string
    "scope_id": string
  }
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
  "SamplingWrite": {
    "feedback_id": string
    "reason": string
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
    "llm_model": string
    "llm_provider": string
    "max_infrastructure_attempts": number
    "points_per_level": number
    "provider_timeout_seconds": number
    "reminders_enabled": boolean
  }
  "SettingsUpdate": {
    "llm_model"?: (string) | (null)
    "llm_provider"?: (string) | (null)
    "max_infrastructure_attempts"?: number
    "points_per_level"?: (number) | (null)
    "provider_timeout_seconds"?: number
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
    "gamification_enabled"?: boolean
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
    "completed_tasks": number
    "completion_percentage": number
    "level": number
    "next_level_points": number
    "points": number
    "total_tasks": number
  }
  "StudyScope": {
    "consent_version": string
    "course_ids": Array<string>
    "data_plan_version": string
    "eligibility_rule_version": string
    "fields": Array<("case_id" | "pseudonymous_user_id" | "course_id" | "task_id" | "task_type" | "submission_reference" | "experimental_condition" | "judge_decision" | "correctness_score" | "relevance_score" | "grounding_score" | "actionability_score" | "safety_score" | "unsupported_claim_count" | "latency_ms" | "input_tokens" | "output_tokens" | "total_tokens" | "estimated_cost" | "regeneration_count" | "fallback_used" | "status" | "comparable" | "usage_complete" | "measurement_schema_version" | "created_at" | "completed_at" | "processing.technical_pair" | "processing.provider_input" | "processing.generated_output" | "processing.judge_result" | "processing.input_references" | "processing.retrieved_sources" | "processing.simulation_reference") | ("instrument.define" | "instrument.collect" | "instrument.read" | "instrument.export" | "instrument.record_id" | "instrument.participant_id" | "instrument.course_ref" | "instrument.sequence_id" | "instrument.form_id" | "instrument.form_version" | "instrument.item_id" | "instrument.stage" | "instrument.outcome_ref" | "instrument.task_ref" | "instrument.response_ref" | "instrument.choice_code" | "instrument.integer_value" | "instrument.response_text" | "instrument.missing_reason" | "instrument.event_kind" | "instrument.reason_code" | "instrument.revision" | "instrument.supersedes_id" | "instrument.correction_reason_code")>
    "kind"?: "scope"
    "processing_researcher_id": number
    "protocol_version": string
    "purposes": Array<"technical_pair" | "provider_processing" | "study_instruments">
    "retention": Array<ApiSchemas["RetentionClass"]>
    "valid_from": string
    "valid_until": string
    "withdrawal_rule_reference": string
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
  "TutorConversationRead": {
    "context_token": string
    "instructional_help_available": boolean
    "next_offset"?: (number) | (null)
    "revision": number
    "status": string
    "turns": Array<ApiSchemas["TutorTurnRead"]>
  }
  "TutorTurnRead": {
    "created_at": string
    "id": string
    "kind": string
    "message": string
    "reply": string
    "revision": number
    "source_references": Array<string>
  }
  "TutorTurnWrite": {
    "context_token": string
    "expected_revision": number
    "idempotency_key": string
    "message": string
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
