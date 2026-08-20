import { createRoot } from 'react-dom/client'

import { AnalyticsDashboard } from '../features/analytics/AnalyticsDashboard'
import type { AnalyticsFilterState } from '../features/analytics/types'
import { FeedbackPanel } from '../features/feedback/FeedbackPanel'
import '../styles/tokens.css'
import '../styles/globals.css'

const filters: AnalyticsFilterState = {
  courseId: 'course-e2e',
  dateFrom: '2026-06-26',
  dateTo: '2026-07-27',
  experimentalCondition: '',
  taskType: '',
  model: '',
  judgeDecision: '',
}

createRoot(document.getElementById('root')!).render(
  <main>
    <FeedbackPanel
      submissionId="submission-e2e"
      pollIntervalMs={10}
      maxPollingDurationMs={5_000}
    />
    <AnalyticsDashboard initialFilters={filters} />
  </main>,
)
