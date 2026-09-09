import { useEffect, useState } from 'react'
import type { ApiSchemas } from '../../api/generated'
import { request } from '../../app/api'
import { Button, Card } from '../../components/ui'

export function GamificationPreferences() {
  const [saved, setSaved] = useState<
    ApiSchemas['GamificationPreferenceRead'] | null
  >(null)
  const [enabled, setEnabled] = useState(true)
  const [key, setKey] = useState(() => crypto.randomUUID())
  const [refresh, setRefresh] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    request<ApiSchemas['GamificationPreferenceRead']>(
      '/students/me/gamification',
      { signal: controller.signal },
    )
      .then((value) => {
        setSaved(value)
        setEnabled(value.enabled)
        setError('')
      })
      .catch((caught) => {
        if (!controller.signal.aborted)
          setError(
            caught instanceof Error
              ? caught.message
              : 'Gamification preferences could not be loaded.',
          )
      })
    return () => controller.abort()
  }, [refresh])
  async function save() {
    if (!saved) return
    setBusy(true)
    setError('')
    setStatus('')
    try {
      const value = await request<ApiSchemas['GamificationPreferenceRead']>(
        '/students/me/gamification',
        {
          method: 'PUT',
          body: JSON.stringify({
            enabled,
            expected_revision: saved.revision,
            idempotency_key: key,
          }),
        },
      )
      setSaved(value)
      setEnabled(value.enabled)
      setKey(crypto.randomUUID())
      setStatus(
        value.enabled
          ? 'Optional points and achievements are enabled.'
          : 'Optional points and achievements are off.',
      )
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : 'The preference could not be saved. Your choice is retained.',
      )
    } finally {
      setBusy(false)
    }
  }
  return (
    <Card
      heading="Optional points and achievements"
      aria-label="Optional points and achievements"
    >
      <p>
        Recognise participation, reflection, revision and feedback use. Points
        and achievements never change assessment standards or course access.
      </p>
      {error && <p role="alert">{error}</p>}
      {status && <p role="status">{status}</p>}
      {saved && (
        <label>
          <input
            type="checkbox"
            checked={enabled}
            disabled={busy}
            onChange={(event) => {
              setEnabled(event.target.checked)
              setKey(crypto.randomUUID())
              setStatus('')
            }}
          />{' '}
          Enable optional points and achievements
        </label>
      )}
      <p>
        Turning this off hides rewards and stops new awards. Earlier records are
        retained. You can change this preference at any time.
      </p>
      <Button disabled={!saved || busy} onClick={() => void save()}>
        Save gamification preference
      </Button>
      <Button
        variant="secondary"
        disabled={busy}
        onClick={() => {
          setStatus('')
          setRefresh((value) => value + 1)
        }}
      >
        Reload gamification preference
      </Button>
    </Card>
  )
}
