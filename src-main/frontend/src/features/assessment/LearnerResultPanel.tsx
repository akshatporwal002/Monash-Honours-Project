import { useEffect, useId, useState } from 'react'
import type { ApiSchemas } from '../../api/generated'
import { ApiError, request } from '../../app/api'
import { Button, Card, Textarea, bloomProcessPlain } from '../../components/ui'

type Result = ApiSchemas['LearnerResultRead']

export function LearnerResultPanel({ responseId }: { responseId: string }) {
  const [result, setResult] = useState<Result | null>(null)
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')
  const [busy, setBusy] = useState(false)
  const [refresh, setRefresh] = useState(0)
  const [requestKey, setRequestKey] = useState(() => crypto.randomUUID())
  const fieldId = useId()
  const path = `/students/me/responses/${encodeURIComponent(responseId)}`

  useEffect(() => {
    const controller = new AbortController()
    request<Result>(`${path}/result`, { signal: controller.signal })
      .then((value) => {
        if (!Array.isArray(value.criteria) || !Array.isArray(value.requests))
          throw new Error('The result could not be loaded. Please refresh.')
        setResult(value)
        setError('')
      })
      .catch((caught) => {
        if (controller.signal.aborted) return
        if (caught instanceof ApiError && [401, 403, 404].includes(caught.status)) setResult(null)
        setError(caught instanceof Error ? caught.message : 'The result could not be loaded.')
      })
    return () => controller.abort()
  }, [path, refresh])

  async function submitReview() {
    setBusy(true)
    setError('')
    try {
      await request(`${path}/review-requests`, {
        method: 'POST',
        body: JSON.stringify({
          reason: reason.trim(),
          request_kind: 'REVIEW',
          idempotency_key: requestKey,
        }),
      })
      setReason('')
      setRequestKey(crypto.randomUUID())
      setStatus('Your review request is saved. Your assessor can now respond.')
      setRefresh((value) => value + 1)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The request could not be saved.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card heading="Assessment result and review" aria-label="Assessment result and review">
      {error && <p role="alert">{error}</p>}
      {status && <p role="status">{status}</p>}
      <Button variant="secondary" onClick={() => setRefresh((value) => value + 1)}>
        Refresh result
      </Button>
      {!result && !error && <p role="status">Loading assessment result…</p>}
      {result && (
        <>
          <p>
            <strong>{result.result ?? result.status}</strong>
            {result.result && ` · ${result.status}`}
          </p>
          <p>{result.outcome}</p>
          <p>Target: {bloomProcessPlain(result.bloom_process)}</p>
          <p>{result.reason}</p>
          <ul>
            {result.criteria.map((criterion) => (
              <li key={criterion.id}>
                <strong>{criterion.description}</strong>
                {criterion.mandatory ? ' (required)' : ''}
                <p>{criterion.evidence_description}</p>
                <p>
                  {criterion.decision === 'MET'
                    ? 'Evidence shown'
                    : criterion.decision === 'NOT_MET'
                      ? 'Evidence still needed'
                      : criterion.decision === 'NOT_EVALUABLE'
                        ? 'Evidence needs review'
                        : 'Awaiting assessor review'}
                </p>
              </li>
            ))}
          </ul>
          <p>Evidence: your saved response in this attempt.</p>
          <p>{result.next_action}</p>
          {result.history.length > 0 && (
            <details>
              <summary>Decision history</summary>
              <ol>
                {result.history.map((entry, index) => (
                  <li key={`${entry.at}-${index}`}>
                    {entry.action.toLowerCase()} · {new Date(entry.at).toLocaleString()}
                  </li>
                ))}
              </ol>
            </details>
          )}
          {result.requests.map((item) => (
            <section key={item.id} aria-label="Review request">
              <h3>{item.state === 'PENDING' ? 'Review requested' : 'Review resolved'}</h3>
              <p>{item.reason}</p>
              <p>Requested {new Date(item.requested_at).toLocaleString()}</p>
              {item.learner_notice && (
                <p>
                  <strong>Assessor response:</strong> {item.learner_notice}
                </p>
              )}
            </section>
          ))}
          {result.can_request_review &&
            !result.requests.some((item) => item.state === 'PENDING') && (
              <form
                onSubmit={(event) => {
                  event.preventDefault()
                  void submitReview()
                }}
              >
                <label htmlFor={fieldId}>What would you like your assessor to review?</label>
                <Textarea
                  id={fieldId}
                  value={reason}
                  maxLength={2000}
                  rows={4}
                  required
                  disabled={busy}
                  onChange={(event) => {
                    setReason(event.target.value)
                    setRequestKey(crypto.randomUUID())
                  }}
                />
                <Button type="submit" disabled={busy || !reason.trim()}>
                  {busy ? 'Saving request…' : 'Request assessor review'}
                </Button>
              </form>
            )}
        </>
      )}
    </Card>
  )
}
