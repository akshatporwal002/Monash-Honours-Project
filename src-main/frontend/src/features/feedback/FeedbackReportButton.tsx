import { useEffect, useId, useRef, useState } from 'react'
import type { FormEvent } from 'react'

import { FeedbackApiError } from './api'
import type { FeedbackApiClient, FeedbackReportCategory } from './types'
import { Button } from '../../components/ui'
import styles from './feedback.module.css'

type FeedbackReportButtonProps = {
  feedbackId: string
  client: FeedbackApiClient
}

export function FeedbackReportButton({ feedbackId, client }: FeedbackReportButtonProps) {
  const [open, setOpen] = useState(false)
  const [category, setCategory] = useState<FeedbackReportCategory>('incorrect')
  const [note, setNote] = useState('')
  const [status, setStatus] = useState<'idle' | 'submitting' | 'received' | 'error'>('idle')
  const [errorMessage, setErrorMessage] = useState('')
  const categoryId = useId()
  const noteId = useId()
  const requestController = useRef<AbortController | null>(null)

  useEffect(
    () => () => {
      requestController.current?.abort()
    },
    [feedbackId],
  )

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    requestController.current?.abort()
    const controller = new AbortController()
    requestController.current = controller
    setStatus('submitting')
    setErrorMessage('')
    try {
      await client.report(
        feedbackId,
        { category, note: note.trim() || undefined },
        controller.signal,
      )
      if (!controller.signal.aborted) setStatus('received')
    } catch (error) {
      if (!controller.signal.aborted) {
        setErrorMessage(
          error instanceof FeedbackApiError
            ? error.message
            : 'The report could not be sent. Try again.',
        )
        setStatus('error')
      }
    } finally {
      if (requestController.current === controller) requestController.current = null
    }
  }

  if (status === 'received') {
    return <p role="status">Thank you. Your concern has been received.</p>
  }

  return (
    <div className={styles.report}>
      <Button variant="quiet" size="sm" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
        Report a concern
      </Button>
      {open && (
        <form onSubmit={submit} aria-label="Report feedback concern" className={styles.reportForm}>
          <label htmlFor={categoryId} className={styles.reportLabel}>Concern</label>
          <select
            id={categoryId}
            className={styles.reportSelect}
            value={category}
            onChange={(event) => setCategory(event.target.value as FeedbackReportCategory)}
          >
            <option value="incorrect">Incorrect feedback</option>
            <option value="unsafe">Unsafe content</option>
            <option value="unclear">Unclear explanation</option>
            <option value="citation_issue">Source or citation issue</option>
            <option value="other">Other concern</option>
          </select>
          <label htmlFor={noteId} className={styles.reportLabel}>Additional details (optional)</label>
          <textarea
            id={noteId}
            className={styles.reportTextarea}
            value={note}
            maxLength={2_000}
            onChange={(event) => setNote(event.target.value)}
          />
          <div>
            <Button type="submit" variant="secondary" loading={status === 'submitting'}>
              Send report
            </Button>
          </div>
          {status === 'error' && <p role="alert" className={styles.alert}>{errorMessage}</p>}
        </form>
      )}
    </div>
  )
}
