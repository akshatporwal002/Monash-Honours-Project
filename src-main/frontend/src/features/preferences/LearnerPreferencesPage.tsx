import { useEffect, useState } from 'react'
import { ApiError, api } from '../../app/api'
import type { ApiSchemas } from '../../api/generated'
import { Button, Card, Field } from '../../components/ui'
import { GamificationPreferences } from './GamificationPreferences'
import { ReminderPreferences } from './ReminderPreferences'

type Preferences = ApiSchemas['LearnerPreferencesRead']
const key = () => globalThis.crypto?.randomUUID?.() ?? `preferences-${Date.now()}`

export function LearnerPreferencesPage() {
  const [value, setValue] = useState<Preferences | null>(null)
  const [status, setStatus] = useState('')
  useEffect(() => { void api.preferences.read().then(setValue).catch(() => setStatus('Preferences could not be loaded.')) }, [])
  if (!value) return <p role="status">Loading learning preferences…</p>
  const save = async () => {
    try {
      const saved = await api.preferences.save({ ...value, expected_revision: value.revision, idempotency_key: key() })
      setValue(saved); setStatus('Learning preferences saved.')
    } catch (error) { setStatus(error instanceof ApiError && error.status === 409 ? 'A newer revision exists. Reload before saving.' : 'Preferences could not be saved. Your choices are still here.') }
  }
  return <section aria-labelledby="preferences-heading">
    <Card eyebrow="Learner controls" heading="Learning preferences">
      <p id="preferences-heading">These optional, correctable choices do not describe ability or a learning style and never affect formal results.</p>
      <Field label="Presentation pace"><select value={value.pace} onChange={e => setValue({ ...value, pace: e.target.value as Preferences['pace'] })}><option value="DEFAULT">Default</option><option value="SLOWER">Slower</option><option value="FASTER">Faster</option></select></Field>
      <Field label="Preferred format"><select value={value.format} onChange={e => setValue({ ...value, format: e.target.value as Preferences['format'] })}><option value="NO_PREFERENCE">No preference</option><option value="TEXT">Text</option><option value="VISUAL">Visual</option><option value="WORKED_EXAMPLE">Worked example</option><option value="CIRCUIT">Circuit</option><option value="STEPWISE">Stepwise</option></select></Field>
      <Field label="Explanation detail"><select value={value.explanation_detail} onChange={e => setValue({ ...value, explanation_detail: e.target.value as Preferences['explanation_detail'] })}><option value="BRIEF">Brief</option><option value="STANDARD">Standard</option><option value="DETAILED">Detailed</option></select></Field>
      <label><input type="checkbox" checked={value.optional_breaks_enabled} onChange={e => setValue({ ...value, optional_breaks_enabled: e.target.checked })} /> Offer optional break invitations</label><br />
      <label><input type="checkbox" checked={value.repeat_practice_enabled} onChange={e => setValue({ ...value, repeat_practice_enabled: e.target.checked })} /> Offer repeat-practice invitations</label><br />
      <label><input type="checkbox" checked={value.personalisation_enabled} onChange={e => setValue({ ...value, personalisation_enabled: e.target.checked })} /> Allow non-essential personalisation</label>
      <p>Turning this off keeps saved choices but prevents automatic use. Approved manual hints and accessibility support remain separate.</p>
      <Button onClick={() => void save()}>Save preferences</Button><p role="status">{status}</p>
    </Card>
    <GamificationPreferences />
    <ReminderPreferences />
  </section>
}
