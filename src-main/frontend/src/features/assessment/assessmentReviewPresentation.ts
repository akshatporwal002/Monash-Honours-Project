import type { AssessmentReviewAction } from './api'

export const actionLabels: Record<AssessmentReviewAction, string> = {
  CONFIRM: 'Confirm result',
  OVERRIDE: 'Override result',
  WITHHOLD: 'Withhold result',
  VOID: 'Void result',
  RETURN: 'Return for review',
}

export function readable(value: string | null): string {
  return value ? value.toLowerCase().replaceAll('_', ' ') : 'Not set'
}
