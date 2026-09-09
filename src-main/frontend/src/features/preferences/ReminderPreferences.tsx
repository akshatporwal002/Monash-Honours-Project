import { useEffect, useRef, useState } from 'react'
import type { ApiSchemas } from '../../api/generated'
import { ApiError, api } from '../../app/api'
import { Button, Card, Field, Input } from '../../components/ui'
import styles from '../reminders/reminders.module.css'

function localInput(value: string | null | undefined): string {
  if (!value) return ''
  const date = new Date(value)
  const pad = (part: number) => String(part).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function ReminderPreferences() {
  const [saved, setSaved] = useState<
    ApiSchemas['ReminderPreferenceRead'] | null
  >(null)
  const [enabled, setEnabled] = useState(true)
  const [pause, setPause] = useState('')
  const [busy, setBusy] = useState(false)
  const [stale, setStale] = useState(false)
  const [status, setStatus] = useState('Loading reminder settings…')
  const [reload, setReload] = useState(0)
  const pending = useRef<{ body: string; key: string } | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    void api.reminders
      .preferences(controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return
        if (
          !Number.isInteger(value.revision) ||
          typeof value.enabled !== 'boolean'
        )
          throw new Error('Invalid reminder settings')
        setSaved(value)
        setEnabled(value.enabled)
        setPause(localInput(value.paused_until))
        setStale(false)
        setStatus('')
        pending.current = null
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setStatus(
            'Reminder settings could not be loaded. Reload to try again.',
          )
      })
    return () => controller.abort()
  }, [reload])

  const save = async () => {
    if (!saved) return
    setBusy(true)
    try {
      const payload = {
        expected_revision: saved.revision ?? 0,
        enabled,
        paused_until: pause ? new Date(pause).toISOString() : null,
      }
      const body = JSON.stringify(payload)
      if (pending.current?.body !== body)
        pending.current = { body, key: crypto.randomUUID() }
      const value = await api.reminders.savePreferences({
        ...payload,
        idempotency_key: pending.current.key,
      })
      setSaved(value)
      pending.current = null
      setStatus('Reminder settings saved.')
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) setStale(true)
      setStatus(
        error instanceof ApiError
          ? error.message
          : 'Reminder settings could not be saved. Your choices are still here.',
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card heading="Task reminders" aria-label="Task reminders" eyebrow="Notifications">
      <p>
        Choose whether to receive task reminders, or pause them during a break.
        You can still open every available task.
      </p>
      <fieldset className={styles.fields} disabled={busy || !saved || stale}>
        <legend>Reminder preferences</legend>
        <label>
          <input
            type="checkbox"
            checked={enabled}
            onChange={(event) => setEnabled(event.target.checked)}
          />{' '}
          Receive task reminders
        </label>
        <Field
          label="Pause reminders until"
          help={`Your local time (${Intl.DateTimeFormat().resolvedOptions().timeZone}). Leave blank for no pause.`}
        >
          <Input
            type="datetime-local"
            value={pause}
            onChange={(event) => setPause(event.target.value)}
          />
        </Field>
        <Button onClick={() => void save()}>Save reminder settings</Button>
      </fieldset>
      <p role="status">{status}</p>
      <Button
        variant="quiet"
        disabled={busy}
        onClick={() => {
          setSaved(null)
          setStatus('Loading reminder settings…')
          setReload((value) => value + 1)
        }}
      >
        Reload saved reminder settings
      </Button>
    </Card>
  )
}
