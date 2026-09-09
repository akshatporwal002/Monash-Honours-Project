import { useEffect, useId, useState } from 'react'
import type { ApiSchemas } from '../../api/generated'
import { request } from '../../app/api'
import { Button, Card, Textarea } from '../../components/ui'

type Appeal = ApiSchemas['LearnerAppealRead']

type OpenDecision = (id: string) => Promise<{ review_revision: number }>

export function AssessorAppeals({
  courseId,
  onOpenDecision,
}: {
  courseId: string
  onOpenDecision: OpenDecision
}) {
  const [items, setItems] = useState<Appeal[]>([])
  const [error, setError] = useState('')
  const [refresh, setRefresh] = useState(0)
  const [offset, setOffset] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    request<Appeal[]>(
      `/assessment/courses/${encodeURIComponent(courseId)}/review-requests?offset=${offset}`,
      { signal: controller.signal },
    )
      .then((value) => {
        setItems(value)
        setError('')
      })
      .catch((caught) => {
        if (!controller.signal.aborted) {
          setItems([])
          setError(
            caught instanceof Error ? caught.message : 'Review requests could not be loaded.',
          )
        }
      })
    return () => controller.abort()
  }, [courseId, refresh, offset])
  return (
    <Card heading="Learner review requests" aria-label="Learner review requests">
      {error && <p role="alert">{error}</p>}
      <Button variant="secondary" onClick={() => setRefresh((value) => value + 1)}>
        Refresh requests
      </Button>
      {!items.length && !error && <p>No pending requests on this page.</p>}
      {items.map((item) => (
        <AppealForm
          key={item.id}
          item={item}
          onOpenDecision={onOpenDecision}
          onResolved={() => setRefresh((value) => value + 1)}
        />
      ))}
      {offset > 0 && (
        <Button variant="secondary" onClick={() => setOffset((value) => Math.max(0, value - 50))}>
          Previous requests
        </Button>
      )}
      {items.length === 50 && (
        <Button variant="secondary" onClick={() => setOffset((value) => value + 50)}>
          More requests
        </Button>
      )}
    </Card>
  )
}

function AppealForm({
  item,
  onOpenDecision,
  onResolved,
}: {
  item: Appeal
  onOpenDecision: OpenDecision
  onResolved: () => void
}) {
  const id = useId()
  const [reason, setReason] = useState('')
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [reviewedRevision, setReviewedRevision] = useState<number | null>(null)
  async function resolve() {
    setBusy(true)
    setError('')
    try {
      await request(`/assessment/review-requests/${encodeURIComponent(item.id)}/resolve`, {
        method: 'POST',
        body: JSON.stringify({
          reason,
          learner_notice: notice,
          expected_decision_revision: item.decision_revision,
        }),
      })
      onResolved()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The resolution could not be saved.')
    } finally {
      setBusy(false)
    }
  }
  return (
    <section aria-label="Pending learner request">
      <h3>
        {item.request_kind.toLowerCase()} · {new Date(item.requested_at).toLocaleString()}
      </h3>
      <p>{item.reason}</p>
      <Button
        variant="secondary"
        onClick={() => {
          void onOpenDecision(item.decision_id)
            .then((detail) => setReviewedRevision(detail.review_revision))
            .catch((caught) =>
              setError(caught instanceof Error ? caught.message : 'Decision could not be opened.'),
            )
        }}
      >
        Open decision and evidence
      </Button>
      <p>
        Record any result change in the decision workspace, then refresh requests before resolving.
        A resolution alone does not change the result.
      </p>
      <form
        onSubmit={(event) => {
          event.preventDefault()
          void resolve()
        }}
      >
        <label htmlFor={`${id}-reason`}>Internal resolution reason</label>
        <Textarea
          id={`${id}-reason`}
          value={reason}
          required
          maxLength={2000}
          rows={3}
          disabled={busy}
          onChange={(event) => setReason(event.target.value)}
        />
        <label htmlFor={`${id}-notice`}>Response to the learner</label>
        <Textarea
          id={`${id}-notice`}
          value={notice}
          required
          maxLength={2000}
          rows={3}
          disabled={busy}
          onChange={(event) => setNotice(event.target.value)}
        />
        <p>
          Explain the outcome and next step without private assessment content. The detailed
          response is visible to the learner only while a confirmed or updated result is released.
        </p>
        {error && <p role="alert">{error}</p>}
        <Button
          type="submit"
          disabled={
            busy || reviewedRevision !== item.decision_revision || !reason.trim() || !notice.trim()
          }
        >
          {busy ? 'Saving resolution…' : 'Resolve request'}
        </Button>
      </form>
    </section>
  )
}
