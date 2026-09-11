import { useEffect, useRef, useState } from 'react'
import { ApiError } from '../../app/api'
import { SupportRepresentation } from '../../components/SupportRepresentation'
import { Button } from '../../components/ui'
import { practiceRepresentations, type Catalog, type Receipt } from './api'

export function PracticeRepresentationPanel({ taskId, preferenceVersion, disabled = false }: { taskId: string; preferenceVersion: number; disabled?: boolean }) {
  const [catalog, setCatalog] = useState<Catalog | null>(null)
  const [receipt, setReceipt] = useState<Receipt | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [reload, setReload] = useState(0)
  const automaticKeys = useRef(new Map<string, string>())
  const requestSequence = useRef(0)
  const message = (caught: unknown) => caught instanceof ApiError ? caught.message : 'Reviewed representations could not be loaded. Try again.'

  useEffect(() => {
    const controller = new AbortController()
    const sequence = ++requestSequence.current
    const invalidateRequests = () => { requestSequence.current++ }
    void practiceRepresentations.catalog(taskId, controller.signal).then(async current => {
      if (controller.signal.aborted || sequence !== requestSequence.current) return
      setCatalog(current); setReceipt(null); setError(''); setBusy(false)
      if (!current.on_request && current.selected_id && !disabled) {
        const key = `${taskId}:${current.revision_id}:${current.review_event_id}:${current.preference_version}:${current.selected_id}:${current.selection}`
        if (!automaticKeys.current.has(key)) automaticKeys.current.set(key, crypto.randomUUID())
        const shown = await practiceRepresentations.deliver(taskId, {
          revision_id: current.revision_id, preference_version: current.preference_version,
          representation_id: current.selected_id, selection: current.selection,
          request_key: automaticKeys.current.get(key)!,
        }, controller.signal)
        if (!controller.signal.aborted && sequence === requestSequence.current) setReceipt(shown)
      }
    }).catch(caught => {
      if (!controller.signal.aborted && sequence === requestSequence.current) { setReceipt(null); setCatalog(null); setError(message(caught)) }
    })
    return () => { controller.abort(); invalidateRequests() }
  }, [taskId, preferenceVersion, reload, disabled])

  const show = async (representationId: string, selection: 'preference' | 'override') => {
    if (!catalog || disabled || busy) return
    const sequence = ++requestSequence.current
    setBusy(true); setError(''); setReceipt(null)
    try {
      const result = await practiceRepresentations.deliver(taskId, {
        revision_id: catalog.revision_id, preference_version: catalog.preference_version,
        representation_id: representationId, request_key: crypto.randomUUID(), selection,
      })
      if (sequence === requestSequence.current) setReceipt(result)
    } catch (caught) { if (sequence === requestSequence.current) setError(message(caught)) }
    finally { if (sequence === requestSequence.current) setBusy(false) }
  }

  if (!error && catalog?.choices.length === 0) return null
  return <section aria-label="Reviewed practice representations">
    <h3>Another way to explore this task</h3>
    {error && <p role="alert">{error} <Button onClick={() => setReload(value => value + 1)}>Reload representations</Button></p>}
    {catalog && <>
      <p>{catalog.explanation}</p>
      {catalog.on_request && <p>Support is on request. Choose a reviewed version when you want it.</p>}
      <p>These versions keep the task and required response unchanged. Opening one does not show whether it helped you learn.</p>
      <ul>{catalog.choices.map(choice => <li key={choice.representation_id}>
        <Button disabled={disabled || busy} onClick={() => void show(choice.representation_id, 'override')}>
          Open {choice.title} ({choice.mode.replace('_', ' ')}, {choice.explanation_detail})
        </Button> — {choice.support_kind === 'accessibility' ? 'Approved access support; no instructional help' : `Instructional support, level ${choice.instructional_support_level}`}
      </li>)}</ul>
      {catalog.recommended_id && <Button disabled={disabled || busy} onClick={() => void show(catalog.recommended_id!, 'preference')}>Use my presentation preferences</Button>}
    </>}
    {busy && <p role="status">Opening reviewed content…</p>}
    {!disabled && receipt && receipt.revision_id === catalog?.revision_id && receipt.review_event_id === catalog.review_event_id && receipt.preference_version === catalog.preference_version && <>
      <SupportRepresentation value={receipt.representation} />
      <p>{receipt.representation.support_kind === 'accessibility' ? 'Access support delivered.' : 'Instructional support delivered.'} Your choice is recorded with the reviewed task version.</p>
    </>}
  </section>
}
