import { useEffect, useRef, useState } from 'react'
import { ApiError, api } from '../app/api'
import type { ApiSchemas } from '../api/generated'
import { Button, Card } from './ui'
import styles from './LearnerPreferences.module.css'
import { baselinePreferences } from '../app/preferences'
import type { PreferenceValues } from '../app/preferences'

export function LearnerPreferences({ onSaved }: { onSaved?: (value: ApiSchemas['PreferenceRead']) => void }) {
  const [saved, setSaved] = useState<ApiSchemas['PreferenceRead'] | null>(null)
  const [draft, setDraft] = useState<PreferenceValues>(baselinePreferences)
  const [message, setMessage] = useState('Loading saved preferences...')
  const [busy, setBusy] = useState(false)
  const [conflict, setConflict] = useState(false)
  const [reload, setReload] = useState(0)
  const [history, setHistory] = useState<ApiSchemas['PreferenceRevision'][]>([])
  const [historyOffset, setHistoryOffset] = useState<number | null>(null)
  const [historyLoaded, setHistoryLoaded] = useState(false)
  const [historyMessage, setHistoryMessage] = useState('')
  const pending = useRef<{ signature: string; key: string } | null>(null)
  const onSavedRef = useRef(onSaved)
  useEffect(() => { onSavedRef.current = onSaved }, [onSaved])
  useEffect(() => {
    const controller = new AbortController()
    let loaded = false
    let resumeLoad = false
    const depart = () => {
      resumeLoad = !loaded
      controller.abort()
    }
    const restore = (event: PageTransitionEvent) => {
      // A cached document keeps its React tree. Resume only an interrupted load
      // so returning to a loaded editor cannot overwrite an unsaved draft.
      if (event.persisted && resumeLoad) {
        resumeLoad = false
        setReload(value => value + 1)
      }
    }
    window.addEventListener('pagehide', depart)
    window.addEventListener('pageshow', restore)
    Promise.resolve().then(() => {
      if (!controller.signal.aborted) return api.student.preferences(controller.signal)
    }).then(value => {
      if (controller.signal.aborted) return
      if (typeof value?.version !== 'number' || !value.values) throw new Error('Invalid preference response')
      loaded = true
      setSaved(value); setDraft(value.values); setMessage(`Saved preferences loaded. Version ${value.version}.`)
      onSavedRef.current?.(value)
    }).catch(() => { if (!controller.signal.aborted) setMessage('Preferences could not be loaded. Try loading again.') })
    return () => {
      window.removeEventListener('pagehide', depart)
      window.removeEventListener('pageshow', restore)
      controller.abort()
    }
  }, [reload])

  const update = <K extends keyof PreferenceValues>(key: K, value: PreferenceValues[K]) => {
    setDraft(current => ({ ...current, [key]: value })); setMessage('Unsaved preference changes.')
  }
  const save = async (reset = false) => {
    if (!saved || conflict) return
    const signature = JSON.stringify({ reset, version: saved.version, values: draft })
    if (pending.current?.signature !== signature) pending.current = { signature, key: crypto.randomUUID() }
    setBusy(true)
    try {
      const command = { expected_version: saved.version, request_key: pending.current.key }
      const value = reset ? await api.student.resetPreferences(command) : await api.student.savePreferences({ ...command, values: draft })
      setSaved(value); setDraft(value.values); pending.current = null
      setMessage(reset ? 'Preferences reset and saved. Earlier choices remain in history.' : `Preferences saved. Version ${value.version}.`)
      setHistory([]); setHistoryLoaded(false); setHistoryOffset(null); onSavedRef.current?.(value)
    } catch (error) {
      const stale = error instanceof ApiError && error.status === 409
      setConflict(stale)
      setMessage(stale ? 'Another session changed your preferences. Your draft is kept. Refresh the saved version before saving it.' : 'Preferences could not be saved. Your draft is kept. Try saving again.')
    } finally { setBusy(false) }
  }
  const refreshConflict = async () => {
    setBusy(true)
    try {
      const value = await api.student.preferences()
      setSaved(value); setConflict(false); pending.current = null; onSavedRef.current?.(value)
      setMessage('Latest saved version loaded. Your draft is kept. Compare the saved choices below before saving your draft.')
    } catch { setMessage('The saved version could not be refreshed. Your draft is kept. Try again.') }
    finally { setBusy(false) }
  }
  const loadHistory = async (offset = 0) => {
    setBusy(true)
    try {
      const page = await api.student.preferenceHistory(undefined, offset)
      setHistory(current => offset ? [...current, ...page.items.filter(item => !current.some(prior => prior.version === item.version))] : page.items)
      setHistoryOffset(page.next_offset); setHistoryLoaded(true); setHistoryMessage('Preference history loaded.')
    } catch { setHistoryMessage('History could not be loaded. Try again; your draft is kept.') }
    finally { setBusy(false) }
  }
  return <Card heading="Learning preferences">
    <p>These are choices you can change, not estimates of your ability. They apply across your courses.</p>
    <p>Only optional presentation changes. Approved task forms, required feedback, reflection, and access support remain available.</p>
    <p role="status" aria-live="polite">{message}</p>
    {!saved ? <Button onClick={() => setReload(value => value + 1)}>Try loading preferences again</Button> : <>
      <form onSubmit={event => { event.preventDefault(); void save() }}>
        <fieldset disabled={busy} className={styles.fields}>
          <legend>Your requested choices</legend>
          <label><input type="checkbox" checked={draft.personalisation_enabled} onChange={event => update('personalisation_enabled', event.target.checked)} /> Enable non-essential personalisation</label>
          <label>Pace<select value={draft.pace} onChange={event => update('pace', event.target.value as PreferenceValues['pace'])}><option value="self_paced">Self paced overview</option><option value="stepwise">Stepwise workspace guide</option></select></label>
          <label>Support format<select value={draft.format} onChange={event => update('format', event.target.value as PreferenceValues['format'])}><option value="text">Text</option><option value="stepwise">Stepwise list</option></select></label>
          <label>Explanation detail<select value={draft.explanation_detail} onChange={event => update('explanation_detail', event.target.value as PreferenceValues['explanation_detail'])}><option value="brief">Brief guidance</option><option value="detailed">Detailed guidance</option></select></label>
          <label>Support amount<select value={draft.support_amount} onChange={event => update('support_amount', event.target.value as PreferenceValues['support_amount'])}><option value="standard">Show approved hint controls</option><option value="on_request">Open hint controls when requested</option></select></label>
          <label>Feedback form<select value={draft.feedback_form} onChange={event => update('feedback_form', event.target.value as PreferenceValues['feedback_form'])}><option value="inline">Inline explanation</option><option value="expandable">Expandable explanation</option></select></label>
          <label><input type="checkbox" checked={draft.breaks} onChange={event => update('breaks', event.target.checked)} /> Show save and break control</label>
          <label><input type="checkbox" checked={draft.repeat_practice} onChange={event => update('repeat_practice', event.target.checked)} /> Offer repeat practice where permitted</label>
          <Button type="submit" disabled={conflict}>Save preferences</Button>
          <Button type="button" disabled={conflict} onClick={() => void save(true)}>Reset and save defaults</Button>
          {conflict && <Button type="button" onClick={() => void refreshConflict()}>Refresh saved version, keep my draft</Button>}
        </fieldset>
      </form>
      <details><summary>Saved choices, version {saved.version}</summary><PreferenceSummary values={saved.values} /></details>
      <details><summary>Preference change history</summary>
        <p>Explicit choices only. Reset keeps earlier revisions. No educator approval is needed.</p>
        <Button disabled={busy} onClick={() => void loadHistory()}>Load preference history</Button>
        <p role="status">{historyMessage}</p>
        {historyLoaded && !history.length && <p>No saved changes yet.</p>}
        {history.map(item => <section key={item.version}><h3>Version {item.version}, {item.action}, {new Date(item.created_at).toLocaleString()}</h3><PreferenceSummary values={item.values} /></section>)}
        {historyOffset !== null && <Button disabled={busy} onClick={() => void loadHistory(historyOffset)}>Load earlier preference changes</Button>}
      </details>
    </>}
  </Card>
}

function PreferenceSummary({ values }: { values: PreferenceValues }) {
  return <dl>{Object.entries(values).map(([key, value]) => <div key={key}><dt>{key.replaceAll('_', ' ')}</dt><dd>{typeof value === 'boolean' ? value ? 'On' : 'Off' : value?.replaceAll('_', ' ')}</dd></div>)}</dl>
}
