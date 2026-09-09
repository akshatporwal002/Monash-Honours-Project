import { useEffect, useState } from 'react'
import type { ApiSchemas } from '../../api/generated'
import { api } from '../../app/api'
import { Button, Card } from '../../components/ui'

export function formatDeadline(value: string, timeZone: string): string {
  return new Intl.DateTimeFormat('en-AU', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone,
  }).format(new Date(value))
}

export function LearnerDeadline({ taskId }: { taskId: string }) {
  const [value, setValue] = useState<ApiSchemas['LearnerDeadlineRead'] | null>(
    null,
  )
  const [failed, setFailed] = useState(false)
  const [reload, setReload] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    void api.reminders
      .deadline(taskId, controller.signal)
      .then((result) => {
        if (result.task_id !== taskId || typeof result.time_zone !== 'string')
          throw new Error('Invalid deadline details')
        if (!controller.signal.aborted) {
          setValue(result)
          setFailed(false)
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) setFailed(true)
      })
    return () => controller.abort()
  }, [taskId, reload])
  if (failed)
    return (
      <Card heading="Your deadline" aria-label="Your deadline">
        <p role="status">Deadline details could not be loaded.</p>
        <Button variant="quiet" onClick={() => setReload((value) => value + 1)}>
          Reload deadline
        </Button>
      </Card>
    )
  if (!value) return <p role="status">Loading deadline details…</p>
  if (
    !value.effective_due_at &&
    !value.learner_notice &&
    !value.reminders_paused
  )
    return null
  return (
    <Card heading="Your deadline" aria-label="Your deadline">
      <p>
        {value.effective_due_at
          ? `${formatDeadline(value.effective_due_at, value.time_zone)} (${value.time_zone})`
          : 'No deadline is set.'}
      </p>
      {value.arrangement_active &&
        value.original_due_at &&
        value.original_due_at !== value.effective_due_at && (
          <p>
            Course deadline:{' '}
            {formatDeadline(value.original_due_at, value.time_zone)}
          </p>
        )}
      {value.learner_notice && <p>{value.learner_notice}</p>}
      {value.reminders_paused && (
        <p>Task reminders are paused under your access arrangement.</p>
      )}
    </Card>
  )
}
