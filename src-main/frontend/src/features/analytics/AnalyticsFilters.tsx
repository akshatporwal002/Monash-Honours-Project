import { useId, useState } from 'react'
import type { FormEvent } from 'react'

import { conditionLabel } from './format'
import type {
  AnalyticsFilterOptions,
  AnalyticsFilterState,
  ExperimentalCondition,
  JudgeDecision,
} from './types'

type AnalyticsFiltersProps = {
  filters: AnalyticsFilterState
  options: AnalyticsFilterOptions
  disabled?: boolean
  onApply: (filters: AnalyticsFilterState) => void
}

function includeCurrent(options: string[], current: string): string[] {
  return current && !options.includes(current) ? [current, ...options] : options
}

export function AnalyticsFilters({
  filters,
  options,
  disabled = false,
  onApply,
}: AnalyticsFiltersProps) {
  const [draft, setDraft] = useState(filters)
  const [validationError, setValidationError] = useState('')
  const formId = useId()

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!draft.dateFrom || !draft.dateTo || draft.dateFrom >= draft.dateTo) {
      setValidationError('End date must be later than start date.')
      return
    }
    const duration =
      Date.parse(`${draft.dateTo}T00:00:00Z`) -
      Date.parse(`${draft.dateFrom}T00:00:00Z`)
    if (duration > 365 * 24 * 60 * 60 * 1_000) {
      setValidationError('Analytics date ranges cannot exceed 365 days.')
      return
    }
    setValidationError('')
    onApply(draft)
  }

  return (
    <form className="analytics-filters" aria-label="Analytics filters" onSubmit={submit}>
      <div className="analytics-filters__grid">
        <label htmlFor={`${formId}-course`}>
          Course
          <select
            id={`${formId}-course`}
            value={draft.courseId}
            disabled={disabled}
            onChange={(event) =>
              setDraft((current) => ({ ...current, courseId: event.target.value }))
            }
          >
            <option value="">All authorized courses</option>
            {includeCurrent(options.courses, draft.courseId).map((course) => (
              <option key={course} value={course}>
                {course}
              </option>
            ))}
          </select>
        </label>

        <label htmlFor={`${formId}-from`}>
          Start date
          <input
            id={`${formId}-from`}
            type="date"
            required
            value={draft.dateFrom}
            disabled={disabled}
            onChange={(event) =>
              setDraft((current) => ({ ...current, dateFrom: event.target.value }))
            }
          />
        </label>

        <label htmlFor={`${formId}-to`}>
          End date (exclusive)
          <input
            id={`${formId}-to`}
            type="date"
            required
            value={draft.dateTo}
            disabled={disabled}
            onChange={(event) =>
              setDraft((current) => ({ ...current, dateTo: event.target.value }))
            }
          />
        </label>

        <label htmlFor={`${formId}-condition`}>
          Research condition
          <select
            id={`${formId}-condition`}
            value={draft.experimentalCondition}
            disabled={disabled}
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                experimentalCondition: event.target.value as ExperimentalCondition | '',
              }))
            }
          >
            <option value="">All conditions</option>
            {options.experimental_conditions.map((condition) => (
              <option key={condition} value={condition}>
                {conditionLabel(condition)}
              </option>
            ))}
          </select>
        </label>

        <label htmlFor={`${formId}-task-type`}>
          Task type
          <select
            id={`${formId}-task-type`}
            value={draft.taskType}
            disabled={disabled}
            onChange={(event) =>
              setDraft((current) => ({ ...current, taskType: event.target.value }))
            }
          >
            <option value="">All task types</option>
            {includeCurrent(options.task_types, draft.taskType).map((taskType) => (
              <option key={taskType} value={taskType}>
                {conditionLabel(taskType)}
              </option>
            ))}
          </select>
        </label>

        <label htmlFor={`${formId}-model`}>
          Model
          <select
            id={`${formId}-model`}
            value={draft.model}
            disabled={disabled}
            onChange={(event) =>
              setDraft((current) => ({ ...current, model: event.target.value }))
            }
          >
            <option value="">All models</option>
            {includeCurrent(options.models, draft.model).map((model) => (
              <option key={model} value={model}>
                {model}
              </option>
            ))}
          </select>
        </label>

        <label htmlFor={`${formId}-decision`}>
          Judge decision
          <select
            id={`${formId}-decision`}
            value={draft.judgeDecision}
            disabled={disabled}
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                judgeDecision: event.target.value as JudgeDecision | '',
              }))
            }
          >
            <option value="">All decisions</option>
            {options.judge_decisions.map((decision) => (
              <option key={decision} value={decision}>
                {conditionLabel(decision)}
              </option>
            ))}
          </select>
        </label>
      </div>
      {validationError && <p role="alert">{validationError}</p>}
      <button type="submit" disabled={disabled}>
        Apply filters
      </button>
    </form>
  )
}
