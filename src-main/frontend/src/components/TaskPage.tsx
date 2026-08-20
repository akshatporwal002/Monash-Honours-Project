import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { api } from '../app/api'
import type { LearningTask } from '../app/types'
import { ScreenState } from './ScreenPrimitives'
import { TaskView } from './TaskView'
import { Button } from './ui'

/**
 * Routed task workspace (/student/tasks/:taskId, plan 006 Step 6).
 * Loads the task through the event-recording student task endpoint, then
 * renders the TaskView workspace as a full page.
 */
export function TaskPage({ onSubmitted }: { onSubmitted: () => Promise<void> }) {
  const { taskId } = useParams<{ taskId: string }>()
  const navigate = useNavigate()
  const [task, setTask] = useState<LearningTask | null>(null)
  const [error, setError] = useState('')
  const [reload, setReload] = useState(0)

  const close = useCallback(() => navigate('/student'), [navigate])

  useEffect(() => {
    if (!taskId) return
    const controller = new AbortController()
    api.student
      .task(taskId, controller.signal)
      .then(setTask)
      .catch((loadError: unknown) => {
        if (controller.signal.aborted) return
        setError(
          loadError instanceof Error
            ? loadError.message
            : 'This activity could not be opened. Please try again.',
        )
      })
    return () => controller.abort()
  }, [taskId, reload])

  if (error) {
    return (
      <ScreenState
        kind="error"
        title="Activity unavailable"
        message={error}
        action={
          <div>
            <Button
              variant="primary"
              onClick={() => {
                setTask(null)
                setError('')
                setReload((current) => current + 1)
              }}
            >
              Try again
            </Button>{' '}
            <Button variant="quiet" onClick={close}>
              Close
            </Button>
          </div>
        }
      />
    )
  }

  if (!task) {
    return <ScreenState kind="loading" title="Opening activity" message="Loading the latest task, saved work and feedback." />
  }

  return <TaskView key={task.id} task={task} onClose={close} onSubmitted={onSubmitted} />
}
