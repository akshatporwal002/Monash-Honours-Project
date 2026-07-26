import { useId } from 'react'

import { MetricCard } from './MetricCard'
import type { LearningMetrics } from './types'

export function LearningSummary({ metrics }: { metrics: LearningMetrics }) {
  const headingId = useId()
  return (
    <section className="analytics-section" aria-labelledby={headingId}>
      <h2 id={headingId}>Learning activity</h2>
      <div className="analytics-card-grid">
        <MetricCard label="Task views" metric={metrics.task_views} />
        <MetricCard label="Unique task views" metric={metrics.unique_task_views} />
        <MetricCard label="Submissions" metric={metrics.submissions} />
        <MetricCard label="Unique submissions" metric={metrics.unique_submissions} />
        <MetricCard label="Completion rate" metric={metrics.completion_rate} />
        <MetricCard label="Average score" metric={metrics.average_score} />
        <MetricCard label="Total attempts" metric={metrics.total_attempts} />
        <MetricCard label="Average attempts" metric={metrics.average_attempts} />
        <MetricCard label="Feedback-view rate" metric={metrics.feedback_view_rate} />
        <MetricCard label="Inactive learners" metric={metrics.inactive_learner_count} />
      </div>
    </section>
  )
}
