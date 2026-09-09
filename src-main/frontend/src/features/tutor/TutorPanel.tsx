import { useEffect, useId, useState } from 'react'
import type { ApiSchemas } from '../../api/generated'
import { ApiError, request } from '../../app/api'
import { Button, Card, Textarea } from '../../components/ui'
import { OutputReport } from '../escalation/OutputReport'

type Conversation = ApiSchemas['TutorConversationRead']
type Turn = ApiSchemas['TutorTurnRead']

export function TutorPanel({ taskId }: { taskId: string }) {
  const [conversation, setConversation] = useState<Conversation | null>(null)
  const [message, setMessage] = useState('')
  const [key, setKey] = useState(() => crypto.randomUUID())
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [refresh, setRefresh] = useState(0)
  const fieldId = useId()
  const path = `/students/me/tasks/${encodeURIComponent(taskId)}/tutor`
  useEffect(() => {
    const controller = new AbortController()
    request<Conversation>(path, { signal: controller.signal })
      .then((value) => {
        if (!Array.isArray(value.turns))
          throw new Error('Conversation could not be loaded. Please reload.')
        setConversation(value)
        setError('')
      })
      .catch((caught) => {
        if (controller.signal.aborted) return
        setConversation(null)
        setError(caught instanceof Error ? caught.message : 'Conversation could not be loaded.')
      })
    return () => controller.abort()
  }, [path, refresh])

  async function send() {
    if (!conversation) return
    setBusy(true)
    setError('')
    try {
      const turn = await request<Turn>(path, {
        method: 'POST',
        body: JSON.stringify({
          message: message.trim(),
          idempotency_key: key,
          expected_revision: conversation.revision,
          context_token: conversation.context_token,
        }),
      })
      setConversation(
        (current) =>
          current && {
            ...current,
            revision: turn.revision,
            turns: [...current.turns.filter((item) => item.id !== turn.id), turn],
          },
      )
      setMessage('')
      setKey(crypto.randomUUID())
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : 'Your message could not be saved. Try again.',
      )
      if (caught instanceof ApiError && [409, 422].includes(caught.status))
        setRefresh((value) => value + 1)
    } finally {
      setBusy(false)
    }
  }

  async function earlier() {
    if (conversation?.next_offset == null) return
    setBusy(true)
    try {
      const page = await request<Conversation>(`${path}?offset=${conversation.next_offset}`)
      setConversation((current) => {
        if (!current || page.context_token !== current.context_token) return page
        const seen = new Set(page.turns.map((turn) => turn.id))
        return {
          ...page,
          turns: page.instructional_help_available
            ? [...page.turns, ...current.turns.filter((turn) => !seen.has(turn.id))]
            : [],
        }
      })
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Earlier messages could not be loaded.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card heading="Work through your reasoning" aria-label="Work through your reasoning">
      {error && <p role="alert">{error}</p>}
      <Button variant="secondary" disabled={busy} onClick={() => setRefresh((value) => value + 1)}>
        Reload conversation
      </Button>
      {!conversation && !error && <p role="status">Loading conversation…</p>}
      {conversation && (
        <>
          <p>{conversation.status}</p>
          {conversation.next_offset !== null && (
            <Button variant="secondary" disabled={busy} onClick={() => void earlier()}>
              Earlier messages
            </Button>
          )}
          <ol aria-label="Tutor conversation" aria-live="polite">
            {conversation.turns.map((turn) => (
              <li key={turn.id}>
                <p>
                  <strong>You:</strong> {turn.message}
                </p>
                <p>
                  <strong>Tutor:</strong> {turn.reply}
                </p>
                <small>
                  {turn.kind === 'hint'
                    ? 'Educator-reviewed conceptual hint'
                    : turn.kind === 'fallback'
                      ? 'Checked help unavailable'
                      : 'Reasoning prompt'}
                </small>
                <OutputReport sourceId={turn.id} />
              </li>
            ))}
          </ol>
          {conversation.instructional_help_available && (
            <form
              onSubmit={(event) => {
                event.preventDefault()
                void send()
              }}
            >
              <label htmlFor={fieldId}>Your reasoning or question</label>
              <Textarea
                id={fieldId}
                rows={4}
                maxLength={4000}
                required
                value={message}
                disabled={busy}
                onChange={(event) => {
                  setMessage(event.target.value)
                  setKey(crypto.randomUUID())
                }}
              />
              <Button type="submit" disabled={busy || !message.trim()}>
                {busy ? 'Saving message…' : 'Send to tutor'}
              </Button>
            </form>
          )}
        </>
      )}
    </Card>
  )
}
