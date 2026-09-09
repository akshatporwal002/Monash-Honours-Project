import { useState } from 'react'
import type { ApiSchemas } from '../../api/generated'
import { ApiError, request } from '../../app/api'
import {
  Button,
  Card,
  Field,
  Input,
  Select,
  Textarea,
} from '../../components/ui'

type Case = ApiSchemas['EscalationStaffRead']
const states = ['OPEN', 'ACKNOWLEDGED', 'ACTIONED', 'RESOLVED', 'CLOSED']
function localDate(value?: string | null) {
  if (!value) return ''
  const date = new Date(value)
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset())
  return date.toISOString().slice(0, 16)
}

export function EscalationCase({
  item,
  setup,
  onSaved,
}: {
  item: Case
  setup: ApiSchemas['EscalationQueueRead']
  onSaved: () => void
}) {
  const [status, setStatus] = useState(
    states[Math.min(states.indexOf(item.status) + 1, 4)],
  )
  const [severity, setSeverity] = useState<string>(item.severity)
  const [owner, setOwner] = useState(
    String(item.owner_user_id ?? setup.configuration?.primary_user_id ?? ''),
  )
  const [acknowledgement, setAcknowledgement] = useState(
    localDate(item.acknowledgement_due_at),
  )
  const [resolution, setResolution] = useState(
    localDate(item.resolution_due_at),
  )
  const [reason, setReason] = useState('')
  const [notice, setNotice] = useState('')
  const [key, setKey] = useState(() => crypto.randomUUID())
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [evidence, setEvidence] = useState<string | null>(null)
  const [accessLost, setAccessLost] = useState(false)
  const members = setup.eligible_members.filter((member) =>
    [
      setup.configuration?.primary_user_id,
      setup.configuration?.backup_user_id,
    ].includes(member.id),
  )
  const options = members.map((member) => ({
    value: String(member.id),
    label: member.name,
  }))
  async function loadEvidence() {
    try {
      setEvidence(
        JSON.stringify(
          await request(`/escalations/${encodeURIComponent(item.id)}/evidence`),
          null,
          2,
        ),
      )
      setError('')
    } catch (caught) {
      setEvidence(null)
      if (
        caught instanceof ApiError &&
        [401, 403, 404].includes(caught.status)
      ) {
        setAccessLost(true)
        onSaved()
      }
      setError(
        caught instanceof Error ? caught.message : 'Evidence is unavailable.',
      )
    }
  }
  async function save() {
    setBusy(true)
    setError('')
    try {
      await request(`/escalations/${encodeURIComponent(item.id)}/actions`, {
        method: 'POST',
        body: JSON.stringify({
          expected_revision: item.revision,
          idempotency_key: key,
          status,
          severity,
          owner_user_id: Number(owner),
          acknowledgement_due_at: new Date(acknowledgement).toISOString(),
          resolution_due_at: new Date(resolution).toISOString(),
          reason,
          learner_notice: notice,
        }),
      })
      onSaved()
    } catch (caught) {
      if (
        caught instanceof ApiError &&
        [401, 403, 404].includes(caught.status)
      ) {
        setEvidence(null)
        setAccessLost(true)
        onSaved()
      }
      setError(
        caught instanceof Error
          ? caught.message
          : 'The response could not be saved. Your text is retained.',
      )
    } finally {
      setBusy(false)
    }
  }
  if (accessLost)
    return (
      <p role="alert">
        Report access changed. Reload the queue to check your current
        permissions.
      </p>
    )
  return (
    <Card
      heading={`${item.trigger.replaceAll('_', ' ').toLowerCase()} · ${item.status.toLowerCase()}`}
    >
      <p>{item.reason}</p>
      <p>
        {item.severity.toLowerCase()} priority ·{' '}
        {new Date(item.created_at).toLocaleString()}
      </p>
      <p>
        Owner:{' '}
        {setup.eligible_members.find(
          (member) => member.id === item.owner_user_id,
        )?.name ?? 'Awaiting configuration'}
        . Backup:{' '}
        {setup.eligible_members.find(
          (member) => member.id === item.backup_user_id,
        )?.name ?? 'Awaiting configuration'}
        .
      </p>
      {error && <p role="alert">{error}</p>}
      <Button variant="secondary" onClick={() => void loadEvidence()}>
        Inspect retained output
      </Button>
      {evidence && (
        <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
          {evidence}
        </pre>
      )}
      <ol>
        {item.history.map((event, index) => (
          <li key={index}>
            {String(event.status)} · {String(event.reason)}
          </li>
        ))}
      </ol>
      {item.status !== 'CLOSED' && setup.configuration && (
        <form
          aria-label="Respond to report"
          onChange={() => setKey(crypto.randomUUID())}
          onSubmit={(event) => {
            event.preventDefault()
            void save()
          }}
        >
          <Field label="Next report status">
            <Select
              value={status}
              onValueChange={(value) => {
                setStatus(value)
                setKey(crypto.randomUUID())
              }}
              options={states
                .slice(
                  states.indexOf(item.status),
                  states.indexOf(item.status) + 2,
                )
                .map((value) => ({ value, label: value.toLowerCase() }))}
              disabled={busy}
            />
          </Field>
          <Field label="Severity">
            <Select
              value={severity}
              onValueChange={(value) => {
                setSeverity(value)
                setKey(crypto.randomUUID())
              }}
              options={['NORMAL', 'HIGH', 'CRITICAL'].map((value) => ({
                value,
                label: value.toLowerCase(),
              }))}
              disabled={busy}
            />
          </Field>
          <Field label="Case owner">
            <Select
              value={owner || undefined}
              options={options}
              onValueChange={(value) => {
                setOwner(value)
                setKey(crypto.randomUUID())
              }}
              disabled={busy}
            />
          </Field>
          <p>
            {setup.configuration.acknowledgement_target}.{' '}
            {setup.configuration.resolution_target}.
          </p>
          <Field label="Acknowledgement target (local time)" required>
            <Input
              type="datetime-local"
              value={acknowledgement}
              onChange={(event) => setAcknowledgement(event.target.value)}
              required
              disabled={busy}
            />
          </Field>
          <Field label="Resolution target (local time)" required>
            <Input
              type="datetime-local"
              value={resolution}
              onChange={(event) => setResolution(event.target.value)}
              required
              disabled={busy}
            />
          </Field>
          <Field label="Private action or resolution reason" required>
            <Textarea
              value={reason}
              maxLength={2000}
              onChange={(event) => setReason(event.target.value)}
              required
              disabled={busy}
            />
          </Field>
          <Field label="Notice to learner" required>
            <Textarea
              value={notice}
              maxLength={2000}
              onChange={(event) => setNotice(event.target.value)}
              required
              disabled={busy}
            />
          </Field>
          <Button
            type="submit"
            disabled={
              busy ||
              !owner ||
              !reason.trim() ||
              !notice.trim() ||
              !acknowledgement ||
              !resolution
            }
          >
            Record human response
          </Button>
        </form>
      )}
    </Card>
  )
}
