import { useEffect, useId, useRef, useState } from 'react'
import type { FormEvent } from 'react'

import { FeedbackApiError } from './api'
import type { FeedbackApiClient, FeedbackReportCategory } from './types'

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
    <div className="feedback-report">
      <button type="button" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
        Report a concern
      </button>
      {open && (
        <form onSubmit={submit} aria-label="Report feedback concern">
          <label htmlFor={categoryId}>Concern</label>
          <select
            id={categoryId}
            value={category}
            onChange={(event) => setCategory(event.target.value as FeedbackReportCategory)}
          >
            <option value="incorrect">Incorrect feedback</option>
            <option value="unsafe">Unsafe content</option>
            <option value="unclear">Unclear explanation</option>
            <option value="citation_issue">Source or citation issue</option>
            <option value="other">Other concern</option>
          </select>
          <label htmlFor={noteId}>Additional details (optional)</label>
          <textarea
            id={noteId}
            value={note}
            maxLength={2_000}
            onChange={(event) => setNote(event.target.value)}
          />
          <button type="submit" disabled={status === 'submitting'}>
            {status === 'submitting' ? 'Sending…' : 'Send report'}
          </button>
          {status === 'error' && <p role="alert">{errorMessage}</p>}
        </form>
      )}
    </div>
  )
}
