import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import type { ApiSchemas } from '../../api/generated'
import { request } from '../../app/api'
import { Button, Card } from '../../components/ui'

export function OutcomeResultPanel({ responseId }: { responseId: string }) {
  const [result, setResult] = useState<ApiSchemas['OutcomeResultRead'] | null>(
    null,
  )
  const [error, setError] = useState('')
  const [refresh, setRefresh] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    request<ApiSchemas['OutcomeResultRead']>(
      `/students/me/responses/${encodeURIComponent(responseId)}/outcome-result`,
      { signal: controller.signal },
    )
      .then((value) => {
        if (
          !Array.isArray(value.authorisations) ||
          !Array.isArray(value.evidence_response_ids)
        )
          throw new Error(
            'The outcome result could not be loaded. Please refresh.',
          )
        if (!controller.signal.aborted) {
          setResult(value)
          setError('')
        }
      })
      .catch((caught) => {
        if (!controller.signal.aborted) {
          setResult(null)
          setError(
            caught instanceof Error
              ? caught.message
              : 'The outcome result could not be loaded.',
          )
        }
      })
    return () => controller.abort()
  }, [responseId, refresh])
  return (
    <Card
      heading="Current outcome and reassessment"
      aria-label="Current outcome and reassessment"
    >
      {error && <p role="alert">{error}</p>}
      <Button
        variant="secondary"
        onClick={() => {
          setResult(null)
          setRefresh((value) => value + 1)
        }}
      >
        Refresh outcome
      </Button>
      {result && (
        <>
          <p>
            <strong>{result.result ?? result.status}</strong>
          </p>
          <p>{result.explanation}</p>
          {result.evidence_response_ids.length > 0 && (
            <p>
              Based on {result.evidence_response_ids.length} confirmed response
              {result.evidence_response_ids.length === 1 ? '' : 's'}. Earlier
              decisions remain in each task’s attempt history.
            </p>
          )}
          {result.authorisations.map((grant) => (
            <section key={grant.id} aria-label="Reassessment notice">
              <h3>{grant.task_title}</h3>
              <p>{grant.learner_notice}</p>
              {grant.available || grant.replacement_response_id ? (
                <Link
                  to={`/student/tasks/${encodeURIComponent(grant.task_id)}`}
                >
                  {grant.available
                    ? 'Open fresh reassessment'
                    : 'View reassessment attempt'}
                </Link>
              ) : (
                <p>
                  Ask your assessor to review this authorisation before starting
                  new work.
                </p>
              )}
            </section>
          ))}
        </>
      )}
    </Card>
  )
}
