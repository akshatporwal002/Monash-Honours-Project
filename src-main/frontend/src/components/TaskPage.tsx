import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { ApiError, api } from '../app/api'
import type { LearningTask } from '../app/types'
import { ScreenState } from './ScreenPrimitives'
import { TaskView } from './TaskView'
import { Button } from './ui'
import { SavedTaskHistory } from './SavedTaskHistory'

/**
 * Routed task workspace (/student/tasks/:taskId, plan 006 Step 6).
 * Loads the task through the event-recording student task endpoint, then
 * renders the TaskView workspace as a full page.
 */
export function TaskPage({ onSubmitted }: { onSubmitted: () => Promise<void> }) {
  const { taskId } = useParams<{ taskId: string }>()
  const navigate = useNavigate()
  const [task, setTask] = useState<LearningTask | null>(null)
  const [error, setError] = useState<{ taskId: string; message: string; status?: number } | null>(null)
  const [historyTaskId, setHistoryTaskId] = useState<string | null>(null)
  const [reload, setReload] = useState(0)

  const close = useCallback(() => navigate('/student'), [navigate])

  useEffect(() => {
    if (!taskId) return
    const controller = new AbortController()
    api.student
      .task(taskId, controller.signal)
      .then((saved) => { if (!controller.signal.aborted) setTask(saved) })
      .catch((loadError: unknown) => {
        if (controller.signal.aborted) return
        setError({ taskId, status: loadError instanceof ApiError ? loadError.status : undefined,
          message: loadError instanceof Error
            ? loadError.message
            : 'This activity could not be opened. Please try again.',
        })
      })
    return () => controller.abort()
  }, [taskId, reload])

  if (error && error.taskId === taskId) {
    return (
      <>
      <ScreenState
        kind="error"
        title="Activity unavailable"
        message={error.message}
        action={
          <div>
            <Button
              variant="primary"
              onClick={() => {
                setTask(null)
                setError(null)
                setHistoryTaskId(null)
                setReload((current) => current + 1)
              }}
            >
              Try again
            </Button>{' '}
            {error.status === 409 && taskId && <Button variant="secondary" onClick={() => setHistoryTaskId((current) => current === taskId ? null : taskId)}>
              {historyTaskId === taskId ? 'Close saved work' : 'View saved work'}
            </Button>}{' '}
            <Button variant="quiet" onClick={close}>
              Close
            </Button>
          </div>
        }
      />
      {taskId && historyTaskId === taskId && <SavedTaskHistory key={taskId} taskId={taskId} />}
      </>
    )
  }

  if (!task || task.id !== taskId) {
    return <ScreenState kind="loading" title="Opening activity" message="Loading the latest task, saved work and feedback." />
  }

  return <TaskView key={task.id} task={task} onClose={close} onSubmitted={onSubmitted} />
}
