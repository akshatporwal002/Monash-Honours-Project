import type { FeedbackProcessingStage } from './types'

type FeedbackStatusProps = {
  stage?: FeedbackProcessingStage | null
}

const STAGE_LABELS: Record<FeedbackProcessingStage, string> = {
  pending: 'waiting to start',
  context_collection: 'collecting task context',
  generating: 'generating feedback',
  judging: 'checking feedback quality',
  regenerating: 'improving feedback',
}

export function FeedbackStatus({ stage }: FeedbackStatusProps) {
  const stageLabel = stage ? ` Current stage: ${STAGE_LABELS[stage]}.` : ''
  return (
    <div className="feedback-status" role="status" aria-live="polite">
      <span className="feedback-status__spinner" aria-hidden="true" />
      <span>Preparing your feedback.{stageLabel}</span>
    </div>
  )
}
