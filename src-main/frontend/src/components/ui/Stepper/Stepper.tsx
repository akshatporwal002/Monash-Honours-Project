import { Check } from 'lucide-react'

import { cx } from '../cx'
import styles from './Stepper.module.css'

export interface StepperProps {
  steps: Array<{ label: string; disabled?: boolean }>
  /** Zero-based index of the current step. */
  current: number
  /**
   * When provided, steps render as buttons so completed or enabled steps can be
   * revisited (wizard back-navigation). Omitted, the stepper is purely visual.
   */
  onSelectStep?: (index: number) => void
  className?: string
}

export function Stepper({ steps, current, onSelectStep, className }: StepperProps) {
  return (
    <ol className={cx(styles.stepper, className)}>
      {steps.map((step, index) => {
        const state = index < current ? 'done' : index === current ? 'current' : 'todo'
        const content = (
          <>
            <span className={styles.marker} aria-hidden="true">
              {state === 'done' ? <Check size={14} /> : index + 1}
            </span>
            <span className={styles.label}>{step.label}</span>
          </>
        )
        return (
          <li
            key={step.label}
            className={cx(styles.step, styles[state])}
            aria-current={state === 'current' ? 'step' : undefined}
          >
            {onSelectStep ? (
              <button
                type="button"
                className={styles.stepButton}
                disabled={step.disabled}
                onClick={() => onSelectStep(index)}
              >
                {content}
              </button>
            ) : (
              content
            )}
          </li>
        )
      })}
    </ol>
  )
}
