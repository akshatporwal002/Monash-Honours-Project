import { useEffect, useState } from 'react'
import type { ApiSchemas } from '../../api/generated'
import { request } from '../../app/api'
import {
  Button,
  Card,
  Field,
  PageHeader,
  Select,
  Textarea,
} from '../../components/ui'
import { EscalationCase } from './EscalationCase'
import { QueueConfiguration } from './QueueConfiguration'

type Queue = ApiSchemas['EscalationQueueRead']

export function EscalationQueue() {
  const [queues, setQueues] = useState<Queue[]>([])
  const [choice, setChoice] = useState('')
  const [error, setError] = useState('')
  const [refresh, setRefresh] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    request<Queue[]>('/escalations/queues', { signal: controller.signal })
      .then((value) => {
        setQueues(value)
        setError('')
      })
      .catch((caught) => {
        if (!controller.signal.aborted) {
          setQueues([])
          setError(
            caught instanceof Error
              ? caught.message
              : 'Queues could not be loaded.',
          )
        }
      })
    return () => controller.abort()
  }, [refresh])
  const selected = queues.find(
    (item) => `${item.course_id}/${item.kind}` === choice,
  )
  return (
    <div>
      <PageHeader
        title="Human review and output reports"
        description="Manage reported concerns and inspect retained AI output. Formal result changes remain in assessment review."
      />
      {error && <p role="alert">{error}</p>}
      <Button
        variant="secondary"
        onClick={() => setRefresh((value) => value + 1)}
      >
        Refresh queue access
      </Button>
      {!queues.length && !error && (
        <p>No queues are available for your current permissions.</p>
      )}
      <Field label="Course and review queue">
        <Select
          value={selected ? choice : undefined}
          options={queues.map((queue) => ({
            value: `${queue.course_id}/${queue.kind}`,
            label: `${queue.course_title} · ${queue.kind.toLowerCase()}`,
          }))}
          onValueChange={setChoice}
        />
      </Field>
      {selected && (
        <QueueWorkspace key={`${choice}-${refresh}`} selected={selected} />
      )}
    </div>
  )
}

function QueueWorkspace({ selected }: { selected: Queue }) {
  const path = `/escalations/courses/${encodeURIComponent(selected.course_id)}/${selected.kind}`
  const [setup, setSetup] = useState<Queue | null>(null)
  const [items, setItems] = useState<ApiSchemas['EscalationStaffRead'][]>([])
  const [error, setError] = useState('')
  const [refresh, setRefresh] = useState(0)
  const [offset, setOffset] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    Promise.all([
      request<Queue>(`${path}/configuration`, { signal: controller.signal }),
      request<ApiSchemas['EscalationStaffRead'][]>(
        `${path}/cases?offset=${offset}`,
        { signal: controller.signal },
      ),
    ])
      .then(([configuration, cases]) => {
        setSetup(configuration)
        setItems(cases)
        setError('')
      })
      .catch((caught) => {
        if (!controller.signal.aborted) {
          setItems([])
          setSetup(null)
          setError(
            caught instanceof Error
              ? caught.message
              : 'The queue could not be loaded.',
          )
        }
      })
    return () => controller.abort()
  }, [path, offset, refresh])
  const reload = () => setRefresh((value) => value + 1)
  return (
    <>
      {error && <p role="alert">{error}</p>}
      <Button variant="secondary" onClick={reload}>
        Reload reports
      </Button>
      {setup && (
        <>
          <QueueConfiguration
            key={`configuration-${setup.configuration?.revision ?? 0}`}
            setup={setup}
            path={path}
            onSaved={reload}
          />
          {selected.kind === 'ASSESSOR' && (
            <FeedbackSampling courseId={selected.course_id} onSaved={reload} />
          )}
          {!items.length && <p>No reports on this page.</p>}
          {items.map((item) => (
            <EscalationCase
              key={`${item.id}-${item.revision}-${setup.configuration?.revision ?? 0}`}
              item={item}
              setup={setup}
              onSaved={reload}
            />
          ))}
        </>
      )}
      {offset > 0 && (
        <Button
          variant="secondary"
          onClick={() => setOffset(Math.max(0, offset - 50))}
        >
          Previous reports
        </Button>
      )}
      {items.length === 50 && (
        <Button variant="secondary" onClick={() => setOffset(offset + 50)}>
          Next reports
        </Button>
      )}
    </>
  )
}

function FeedbackSampling({
  courseId,
  onSaved,
}: {
  courseId: string
  onSaved: () => void
}) {
  const [samples, setSamples] = useState<string[]>([])
  const [offset, setOffset] = useState(0)
  const [sampleId, setSampleId] = useState('')
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const path = `/escalations/courses/${encodeURIComponent(courseId)}/samples`
  useEffect(() => {
    const controller = new AbortController()
    request<string[]>(`${path}?offset=${offset}`, { signal: controller.signal })
      .then(setSamples)
      .catch((caught) => {
        if (!controller.signal.aborted)
          setError(
            caught instanceof Error
              ? caught.message
              : 'Samples could not be loaded.',
          )
      })
    return () => controller.abort()
  }, [path, offset])
  async function sample() {
    setBusy(true)
    setError('')
    try {
      await request(path, {
        method: 'POST',
        body: JSON.stringify({ feedback_id: sampleId, reason }),
      })
      onSaved()
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : 'The sample could not be queued.',
      )
    } finally {
      setBusy(false)
    }
  }
  return (
    <Card heading="Human sampling of accepted feedback">
      {error && <p role="alert">{error}</p>}
      <form
        onSubmit={(event) => {
          event.preventDefault()
          void sample()
        }}
      >
        <Field label="Accepted feedback">
          <Select
            value={sampleId || undefined}
            options={samples.map((id, index) => ({
              value: id,
              label: `Accepted output ${offset + index + 1} · ${id.slice(0, 8)}`,
            }))}
            onValueChange={setSampleId}
            disabled={busy}
          />
        </Field>
        <Field label="Sampling reason" required>
          <Textarea
            value={reason}
            maxLength={2000}
            onChange={(event) => setReason(event.target.value)}
            disabled={busy}
            required
          />
        </Field>
        <Button type="submit" disabled={busy || !sampleId || !reason.trim()}>
          Queue for human sampling
        </Button>
      </form>
      {offset > 0 && (
        <Button
          variant="secondary"
          onClick={() => {
            setSampleId('')
            setOffset(Math.max(0, offset - 50))
          }}
        >
          Previous accepted outputs
        </Button>
      )}
      {samples.length === 50 && (
        <Button
          variant="secondary"
          onClick={() => {
            setSampleId('')
            setOffset(offset + 50)
          }}
        >
          More accepted outputs
        </Button>
      )}
    </Card>
  )
}
