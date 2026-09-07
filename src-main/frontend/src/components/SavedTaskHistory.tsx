import { EpisodeSnapshot } from "./EpisodeSnapshot"
import { useEffect, useState } from 'react'

import { api } from '../app/api'
import type { TaskDraft, TaskSubmission } from '../app/types'
import { Card } from './ui'
import styles from './SavedTaskHistory.module.css'

function SavedResponse({ response }: { response: Pick<TaskDraft, 'answer' | 'code' | 'circuit' | 'episode'> }) {
  return <div className={styles.response}>
    {response.answer && <pre style={{ whiteSpace: 'pre-wrap' }}>{response.answer}</pre>}
    {response.episode && <EpisodeSnapshot episode={response.episode} />}
    {response.code && <pre>{response.code}</pre>}
    {response.circuit && <div>
      <p>Circuit: {response.circuit.qubits} qubits</p>
      <ol>{response.circuit.operations.map((operation, index) => <li key={index}>
        {operation.gate.toUpperCase()} on qubit {operation.targets.join(', ')}
      </li>)}</ol>
    </div>}
  </div>
}

export function SavedTaskHistory({ taskId }: { taskId: string }) {
  const [draft, setDraft] = useState<TaskDraft | null>(null)
  const [attempts, setAttempts] = useState<TaskSubmission[] | null>(null)
  const [attemptsFailed, setAttemptsFailed] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    void Promise.allSettled([
      api.student.draft(taskId, controller.signal),
      api.student.attempts(taskId, controller.signal),
    ]).then(([savedDraft, savedAttempts]) => {
      if (controller.signal.aborted) return
      if (savedDraft.status === 'fulfilled') setDraft(savedDraft.value)
      if (savedAttempts.status === 'fulfilled') setAttempts(savedAttempts.value)
      else { setAttempts([]); setAttemptsFailed(true) }
      if (savedDraft.status === 'rejected' || savedAttempts.status === 'rejected') {
        setError('Some saved work could not be loaded. Reopen this history to try again.')
      }
    })
    return () => controller.abort()
  }, [taskId])

  return <section aria-label="Saved activity records" className={styles.history}>
    {error && <p role="alert">{error}</p>}
    {attempts === null && <p role="status">Loading saved activity records...</p>}
    {draft && <Card heading="Saved draft"><SavedResponse response={draft} /></Card>}
    {attempts !== null && <Card heading="Previous attempts">
      {attemptsFailed ? <p>Attempt history could not be loaded.</p> : attempts.length === 0 ? <p>No saved attempts are available.</p> : <ol>
        {attempts.map((attempt, index) => <li key={attempt.id ?? index} className={styles.attempt}>
          <h3>Attempt {attempt.attempt_number ?? attempts.length - index}</h3>
          <p>{attempt.formal_assessment ? 'Assessment response saved' : 'Response saved'}</p>
          {attempt.submitted_at && <time dateTime={attempt.submitted_at}>{new Date(attempt.submitted_at).toLocaleString()}</time>}
          <SavedResponse response={{ episode: attempt.episode, answer: attempt.answer ?? '', code: attempt.code ?? null, circuit: attempt.circuit ?? null }} />
          {attempt.feedback && <p>{attempt.feedback}</p>}
        </li>)}
      </ol>}
    </Card>}
  </section>
}
