import type { ApiSchemas } from '../../api/generated'

export type ExperimentalCondition = ApiSchemas['ExperimentalCondition']
export type JudgeDecision = ApiSchemas['JudgeDecision']

export type AnalyticsFilterState = {
  courseId: string
  dateFrom: string
  dateTo: string
  experimentalCondition: ExperimentalCondition | ''
  taskType: string
  model: string
  judgeDecision: JudgeDecision | ''
}

export type MetricValue = ApiSchemas['MetricValue']

export type AnalyticsFilterSnapshot = {
  course_ids: string[]
  start_at: string | null
  end_at: string | null
  experimental_conditions: ExperimentalCondition[]
  task_types: string[]
  models: string[]
  judge_decisions: string[]
}

export type FunnelEventType =
  | 'task_view'
  | 'draft_save'
  | 'submission'
  | 'feedback_view'
  | 'completion'

export type FunnelStage = {
  event_type: FunnelEventType
  count: number
  previous_stage_rate: MetricValue
}

export type InactiveLearner = ApiSchemas['InactiveLearner']

export type LearningMetrics = {
  schema_version: 'learning-metrics-v1'
  filters: AnalyticsFilterSnapshot
  generated_at: string
  task_views: MetricValue
  unique_task_views: MetricValue
  submissions: MetricValue
  unique_submissions: MetricValue
  completion_rate: MetricValue
  average_score: MetricValue
  total_attempts: MetricValue
  average_attempts: MetricValue
  feedback_view_rate: MetricValue
  funnel: FunnelStage[]
  inactive_learner_count: MetricValue
  excluded_incomplete_count: number
}

export type ConditionMetrics = ApiSchemas['ConditionMetrics']

export type PairedDifferences = ApiSchemas['PairedDifferences']

export type ResearchMetrics = {
  schema_version: 'research-metrics-v1'
  filters: AnalyticsFilterSnapshot
  generated_at: string
  retrieval_threshold: number
  retrieval_threshold_version: string
  by_condition: Record<ExperimentalCondition, ConditionMetrics>
  first_pass_rate: MetricValue
  regeneration_success_rate: MetricValue
  retrieval_hit_rate: MetricValue
  paired_agentic_minus_baseline: PairedDifferences
  excluded_incomplete_count: number
}

export type AnalyticsFilterOptions = {
  schema_version: string
  generated_at: string
  courses: string[]
  task_types: string[]
  models: string[]
  experimental_conditions: ExperimentalCondition[]
  judge_decisions: JudgeDecision[]
}

export type InactiveLearnerPage = {
  schema_version: 'inactive-learners-v1'
  filters: AnalyticsFilterSnapshot
  generated_at: string
  inactive_learner_count: MetricValue
  excluded_incomplete_count: number
  items: InactiveLearner[]
  page: number
  page_size: number
  total: number
}

export type ResearchExportFormat = 'csv' | 'json'

export interface AnalyticsApiClient {
  getLearning(
    filters: AnalyticsFilterState,
    signal?: AbortSignal,
  ): Promise<LearningMetrics>
  getResearch(
    filters: AnalyticsFilterState,
    signal?: AbortSignal,
  ): Promise<ResearchMetrics>
  getFilterOptions(signal?: AbortSignal): Promise<AnalyticsFilterOptions>
  getInactiveLearners(
    filters: AnalyticsFilterState,
    page: number,
    pageSize: number,
    signal?: AbortSignal,
  ): Promise<InactiveLearnerPage>
  researchExportUrl(
    format: ResearchExportFormat,
    filters: AnalyticsFilterState,
  ): string
}
