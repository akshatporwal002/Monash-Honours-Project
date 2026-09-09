import { useState } from 'react'
import type { ApiSchemas } from '../../api/generated'
import { request } from '../../app/api'
import {
  Button,
  Card,
  Field,
  Input,
  Select,
  Textarea,
} from '../../components/ui'

export function QueueConfiguration({
  setup,
  path,
  onSaved,
}: {
  setup: ApiSchemas['EscalationQueueRead']
  path: string
  onSaved: () => void
}) {
  const current = setup.configuration
  const [primary, setPrimary] = useState(
    current ? String(current.primary_user_id) : '',
  )
  const [backup, setBackup] = useState(
    current ? String(current.backup_user_id) : '',
  )
  const [acknowledgement, setAcknowledgement] = useState(
    current?.acknowledgement_target ?? '',
  )
  const [resolution, setResolution] = useState(current?.resolution_target ?? '')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const options = setup.eligible_members.map((member) => ({
    value: String(member.id),
    label: member.name,
  }))
  async function save() {
    setBusy(true)
    setError('')
    try {
      await request(`${path}/configuration`, {
        method: 'POST',
        body: JSON.stringify({
          expected_revision: current?.revision ?? 0,
          primary_user_id: Number(primary),
          backup_user_id: Number(backup),
          acknowledgement_target: acknowledgement,
          resolution_target: resolution,
          reason,
        }),
      })
      onSaved()
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : 'Queue settings could not be saved.',
      )
    } finally {
      setBusy(false)
    }
  }
  return (
    <Card heading="Queue ownership and targets">
      {error && <p role="alert">{error}</p>}
      {!current && (
        <p role="status">
          Reports are retained. Configure separate primary and backup owners
          before responding.
        </p>
      )}
      <details open={!current}>
        <summary>
          {current ? 'Update queue configuration' : 'Configure queue'}
        </summary>
        <form
          onSubmit={(event) => {
            event.preventDefault()
            void save()
          }}
        >
          <Field label="Primary owner" required>
            <Select
              options={options}
              value={primary || undefined}
              onValueChange={setPrimary}
              disabled={busy}
            />
          </Field>
          <Field label="Backup owner" required>
            <Select
              options={options}
              value={backup || undefined}
              onValueChange={setBackup}
              disabled={busy}
            />
          </Field>
          <p>
            Use the approved staffed hours and severity rules. Set the
            corresponding dates on each case; no response time is assumed.
          </p>
          <Field label="Acknowledgement target and staffed hours" required>
            <Input
              value={acknowledgement}
              maxLength={500}
              onChange={(event) => setAcknowledgement(event.target.value)}
              required
              disabled={busy}
            />
          </Field>
          <Field label="Resolution target and severity rules" required>
            <Input
              value={resolution}
              maxLength={500}
              onChange={(event) => setResolution(event.target.value)}
              required
              disabled={busy}
            />
          </Field>
          <Field label="Configuration reason" required>
            <Textarea
              value={reason}
              maxLength={2000}
              onChange={(event) => setReason(event.target.value)}
              required
              disabled={busy}
            />
          </Field>
          <Button
            type="submit"
            disabled={
              busy ||
              !primary ||
              !backup ||
              primary === backup ||
              !reason.trim()
            }
          >
            Save queue configuration
          </Button>
        </form>
      </details>
    </Card>
  )
}
