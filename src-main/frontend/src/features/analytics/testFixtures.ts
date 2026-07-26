import type {
  AnalyticsFilterOptions,
  AnalyticsFilterSnapshot,
  AnalyticsFilterState,
  ConditionMetrics,
  InactiveLearnerPage,
  LearningMetrics,
  MetricValue,
  ResearchMetrics,
} from './types'

export const FILTERS: AnalyticsFilterState = {
  courseId: 'course-a',
  dateFrom: '2026-06-26',
  dateTo: '2026-07-26',
  experimentalCondition: '',
  taskType: '',
  model: '',
  judgeDecision: '',
}

const SNAPSHOT: AnalyticsFilterSnapshot = {
  course_ids: ['course-a'],
  start_at: '2026-06-26T00:00:00Z',
  end_at: '2026-07-26T00:00:00Z',
  experimental_conditions: [],
  task_types: [],
  models: [],
  judge_decisions: [],
}

export function metric(
  value: number | null,
  unit = 'ratio',
  denominator = value === null ? 0 : 10,
): MetricValue {
  return {
    value,
    numerator: value === null ? 0 : value * denominator,
    denominator,
    sample_size: denominator,
    unit,
  }
}

export function learningMetrics(
  updates: Partial<LearningMetrics> = {},
): LearningMetrics {
  return {
    schema_version: 'learning-metrics-v1',
    filters: SNAPSHOT,
    generated_at: '2026-07-25T12:00:00Z',
    task_views: metric(40, 'events', 40),
    unique_task_views: metric(25, 'actor_task_pairs', 25),
    submissions: metric(20, 'events', 20),
    unique_submissions: metric(16, 'actor_task_pairs', 16),
    completion_rate: metric(0.75),
    average_score: metric(82, 'score'),
    total_attempts: metric(20, 'attempts', 16),
    average_attempts: metric(1.25, 'attempts', 16),
    feedback_view_rate: metric(0.8),
    funnel: [
      { event_type: 'task_view', count: 25, previous_stage_rate: metric(1) },
      { event_type: 'draft_save', count: 22, previous_stage_rate: metric(0.88) },
      { event_type: 'submission', count: 16, previous_stage_rate: metric(16 / 22, 'ratio', 22) },
      { event_type: 'feedback_view', count: 14, previous_stage_rate: metric(0.875, 'ratio', 16) },
      { event_type: 'completion', count: 12, previous_stage_rate: metric(12 / 14, 'ratio', 14) },
    ],
    inactive_learner_count: {
      value: 30,
      numerator: 30,
      denominator: 120,
      sample_size: 120,
      unit: 'learners',
    },
    excluded_incomplete_count: 0,
    ...updates,
  }
}

function conditionMetrics(updates: Partial<ConditionMetrics> = {}): ConditionMetrics {
  return {
    hallucination_rate: metric(0.1),
    overall_pass_rate: metric(0.8),
    average_relevance: metric(86, 'score'),
    average_latency_ms: metric(1_250, 'milliseconds'),
    p95_latency_ms: metric(2_100, 'milliseconds'),
    average_total_tokens: metric(480, 'tokens'),
    average_cost: metric(0.0142, 'currency_units'),
    fallback_rate: metric(0.05),
    ...updates,
  }
}

export function researchMetrics(
  updates: Partial<ResearchMetrics> = {},
): ResearchMetrics {
  return {
    schema_version: 'research-metrics-v1',
    filters: SNAPSHOT,
    generated_at: '2026-07-25T12:01:00Z',
    retrieval_threshold: 0.5,
    retrieval_threshold_version: 'retrieval-relevance-v1',
    by_condition: {
      agentic_rag: conditionMetrics(),
      single_step_baseline: conditionMetrics({
        overall_pass_rate: metric(0.6),
        average_relevance: metric(74, 'score'),
        average_latency_ms: metric(600, 'milliseconds'),
        p95_latency_ms: metric(900, 'milliseconds'),
        average_total_tokens: metric(220, 'tokens'),
        average_cost: metric(0.006, 'currency_units'),
      }),
    },
    first_pass_rate: metric(0.7),
    regeneration_success_rate: metric(0.75, 'ratio', 4),
    retrieval_hit_rate: metric(0.8, 'ratio', 25),
    paired_agentic_minus_baseline: {
      pass_rate: metric(0.2, 'ratio_points'),
      relevance: metric(12, 'score'),
      latency_ms: metric(650, 'milliseconds'),
      total_tokens: metric(260, 'tokens'),
      cost: metric(0.0082, 'currency_units'),
    },
    excluded_incomplete_count: 0,
    ...updates,
  }
}

export const FILTER_OPTIONS: AnalyticsFilterOptions = {
  schema_version: 'analytics-filter-options-v1',
  generated_at: '2026-07-25T12:00:00Z',
  courses: ['course-a', 'course-b', 'course-c'],
  task_types: ['multiple_choice', 'short_answer'],
  models: ['model-a'],
  experimental_conditions: ['agentic_rag', 'single_step_baseline'],
  judge_decisions: ['pass', 'fail'],
}

export function inactivePage(
  updates: Partial<InactiveLearnerPage> = {},
): InactiveLearnerPage {
  return {
    schema_version: 'inactive-learners-v1',
    filters: SNAPSHOT,
    generated_at: '2026-07-25T12:00:00Z',
    inactive_learner_count: {
      value: 30,
      numerator: 30,
      denominator: 120,
      sample_size: 120,
      unit: 'learners',
    },
    excluded_incomplete_count: 0,
    items: [
      {
        pseudonymous_user_id: 'v1_learner_a',
        last_activity_at: '2026-06-01T10:00:00Z',
      },
    ],
    page: 1,
    page_size: 25,
    total: 30,
    ...updates,
  }
}
