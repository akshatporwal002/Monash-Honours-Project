import { CircleDashed, FileEdit, Send, Eye, Undo2, CheckCircle2 } from 'lucide-react'
import type { ReactNode } from 'react'

import type { SubmissionState } from '../../../features/assessment/types'
import { cx } from '../cx'
import styles from './StepText.module.css'

export interface StepTextProps {
  state: SubmissionState
  className?: string
}

const presentation: Record<SubmissionState, { label: string; icon: ReactNode }> = {
  NOT_STARTED: { label: 'Not started', icon: <CircleDashed size={14} /> },
  DRAFT: { label: 'Draft in progress', icon: <FileEdit size={14} /> },
  SUBMITTED: { label: 'Submitted', icon: <Send size={14} /> },
  UNDER_REVIEW: { label: 'Under review', icon: <Eye size={14} /> },
  RETURNED: { label: 'Returned for revision', icon: <Undo2 size={14} /> },
  COMPLETED: { label: 'Completed', icon: <CheckCircle2 size={14} /> },
}

/**
 * Submission workflow narration — plain ink text with a small icon.
 * Deliberately quiet: workflow state is never an outcome (D1 §3.3).
 */
export function StepText({ state, className }: StepTextProps) {
  const { label, icon } = presentation[state]
  return (
    <span className={cx(styles.step, className)}>
      <span className={styles.icon} aria-hidden="true">
        {icon}
      </span>
      {label}
    </span>
  )
}
