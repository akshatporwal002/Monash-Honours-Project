import { useEffect, useId, useState } from 'react'
import { ApiError, api } from '../../app/api'
import type { ApiSchemas } from '../../api/generated'
import { Button, Card, Field } from '../../components/ui'

type Preferences = ApiSchemas['LearnerPreferencesRead']
const key = () => globalThis.crypto?.randomUUID?.() ?? `preferences-${Date.now()}`
const defaults = {
  pace: 'DEFAULT',
  format: 'NO_PREFERENCE',
  explanation_detail: 'STANDARD',
  optional_breaks_enabled: false,
  repeat_practice_enabled: false,
  personalisation_enabled: false,
} as const

function normalise(loaded: Preferences): Preferences {
  return { ...defaults, ...loaded }
}

export function LearnerPreferencesSummary() {
  const panelId = useId()
  const [value, setValue] = useState<Preferences | null>(null)
  const [draft, setDraft] = useState<Preferences | null>(null)
  const [open, setOpen] = useState(false)
  const [status, setStatus] = useState('')
  const [saving, setSaving] = useState(false)
  useEffect(() => { void api.preferences.read().then((loaded) => { const normalised = normalise(loaded); setValue(normalised); setDraft(normalised) }).catch(() => setStatus('Preferences could not be loaded. Task work remains available.')) }, [])
  if (!value || !draft) return <Card eyebrow="Optional support" heading="Learning preferences"><p role={status ? "alert" : "status"}>{status || 'Loading independent preferences…'}</p></Card>
  const change = <K extends keyof Preferences>(field: K, next: Preferences[K]) => setDraft({ ...draft, [field]: next })
  const save = async () => { setSaving(true); setStatus(''); try { const saved = await api.preferences.save({ ...draft, expected_revision: value.revision, idempotency_key: key() }); setValue(saved); setDraft(saved); setOpen(false); setStatus('Learning preferences saved.') } catch (error) { setStatus(error instanceof ApiError && error.status === 409 ? 'A newer preference revision exists. Reload before saving.' : 'Preferences could not be saved. Your choices are still here.') } finally { setSaving(false) } }
  const savePersonalisation = async (personalisation_enabled: boolean) => {
    setSaving(true)
    setStatus('')
    try {
      const saved = await api.preferences.save({
        ...value,
        personalisation_enabled,
        expected_revision: value.revision,
        idempotency_key: key(),
      })
      setValue(saved)
      setDraft((current) => current && { ...current, personalisation_enabled: saved.personalisation_enabled, revision: saved.revision })
      setStatus('Personalisation preference saved.')
    } catch (error) {
      setDraft((current) => current && { ...current, personalisation_enabled: value.personalisation_enabled })
      setStatus(error instanceof ApiError && error.status === 409 ? 'A newer preference revision exists. Reload before changing personalisation.' : 'Personalisation preference could not be saved. Your previous setting remains in effect.')
    } finally {
      setSaving(false)
    }
  }
  const inactive = !value.personalisation_enabled
  return <Card eyebrow="Optional support" heading="Learning preferences">
    <p>{inactive ? `Personalisation is off. Saved, currently not applied: ${value.pace.toLowerCase()} pace, ${value.format.toLowerCase()} format, ${value.explanation_detail.toLowerCase()} detail.` : `${value.pace.toLowerCase()} pace, ${value.format.toLowerCase()} format, ${value.explanation_detail.toLowerCase()} detail.`}</p>
    <label><input type="checkbox" checked={draft.personalisation_enabled} disabled={saving} onChange={(event) => void savePersonalisation(event.target.checked)} /> Allow non-essential personalisation</label>
    <p>Optional breaks only record your choice; this card does not create reminders or enforce breaks.</p>
    <Button aria-expanded={open} aria-controls={panelId} onClick={() => setOpen(!open)}>{open ? 'Hide preference editor' : 'Edit preferences'}</Button>
    {open ? <div id={panelId}>
      <Field label="Presentation pace"><select value={draft.pace} onChange={e => change('pace', e.target.value as Preferences['pace'])}><option value="DEFAULT">Default</option><option value="SLOWER">Slower</option><option value="FASTER">Faster</option></select></Field>
      <Field label="Preferred format"><select value={draft.format} onChange={e => change('format', e.target.value as Preferences['format'])}><option value="NO_PREFERENCE">No preference</option><option value="TEXT">Text</option><option value="VISUAL">Visual</option><option value="WORKED_EXAMPLE">Worked example</option><option value="CIRCUIT">Circuit</option><option value="STEPWISE">Stepwise</option></select></Field>
      <Field label="Explanation detail"><select value={draft.explanation_detail} onChange={e => change('explanation_detail', e.target.value as Preferences['explanation_detail'])}><option value="BRIEF">Brief</option><option value="STANDARD">Standard</option><option value="DETAILED">Detailed</option></select></Field>
      <label><input type="checkbox" checked={draft.optional_breaks_enabled} onChange={e => change('optional_breaks_enabled', e.target.checked)} /> Save optional-break preference</label><br />
      <label><input type="checkbox" checked={draft.repeat_practice_enabled} onChange={e => change('repeat_practice_enabled', e.target.checked)} /> Save repeat-practice preference</label><br />
      <Button loading={saving} onClick={() => void save()}>Save preferences</Button>
    </div> : null}
    <p role="status">{status}</p>
  </Card>
}
