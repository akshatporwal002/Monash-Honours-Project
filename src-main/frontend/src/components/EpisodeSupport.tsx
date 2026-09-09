import { useEffect, useRef, useState } from 'react'
import { api } from '../app/api'
import type { ApiSchemas } from '../api/generated'
import type { EpisodeState } from '../app/types'
import { Button } from './ui'

export function EpisodeSupport({ taskId, workId, state, disabled, onRequest = false }: {
  taskId: string; workId: string | null; state: EpisodeState; disabled: boolean
  onRequest?: boolean
}) {
  const [history, setHistory] = useState<ApiSchemas['EpisodeHelpUseRead'][]>([])
  const [offset, setOffset] = useState<number | null>(null)
  const [hint, setHint] = useState<string | null>(null)
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const pending = useRef<Record<string, string>>({})
  const stageId = state.transfer?.stage_start_id ?? null
  useEffect(() => {
    const controller = new AbortController()
    api.student.helpHistory(taskId, controller.signal).then(page => {
      if (!controller.signal.aborted) { setHistory(page.items); setOffset(page.next_offset) }
    }).catch(() => { if (!controller.signal.aborted) setMessage('Support history could not be loaded. Your response is unchanged.') })
    return () => controller.abort()
  }, [taskId, stageId])

  const record = async (kind: 'conceptual_hint' | 'accessibility', index: number) => {
    if (!workId) return
    const key = `${workId}:${stageId}:${kind}:${index}`
    pending.current[key] ??= crypto.randomUUID()
    setLoading(true)
    try {
      const receipt = await api.student.recordHelp(taskId, { assessment_work_start_id: workId, stage_start_id: stageId, kind, item_index: index, request_key: pending.current[key] })
      delete pending.current[key]
      if (kind === 'conceptual_hint') setHint(receipt.content)
      if (!history.some(item => item.id === receipt.record.id)) setOffset(current => current === null ? null : current + 1)
      setHistory(current => [receipt.record, ...current.filter(item => item.id !== receipt.record.id)])
      setMessage(kind === 'conceptual_hint' ? 'Hint request saved. You can request approved hints as often as needed.' : 'Access support noted. It does not lower your result.')
    } catch { setMessage('Support request could not be saved. Try the same action again. Your response is unchanged.') }
    finally { setLoading(false) }
  }
  return <>
    {state.transfer ? <p>Fresh application is unaided. Accessibility support remains available.</p> : <>
      <p>Conceptual hints, use as often as needed</p>
      {onRequest ? <details><summary>Open approved hint controls</summary>{(state.supported_hints ?? []).map((label, index) => <Button key={index} disabled={disabled || loading || !workId} onClick={() => void record('conceptual_hint', index)}>Request {label.toLowerCase()}</Button>)}</details> : (state.supported_hints ?? []).map((label, index) => <Button key={index} disabled={disabled || loading || !workId} onClick={() => void record('conceptual_hint', index)}>Request {label.toLowerCase()}</Button>)}
      {hint && <p aria-label="Requested conceptual hint">{hint}</p>}
    </>}
    {(state.accessibility_support ?? []).map((support, index) => <div key={index}><p>{support}</p><Button disabled={disabled || loading || !workId} onClick={() => void record('accessibility', index)}>I used access support {index + 1}</Button></div>)}
    {message && <p role="status">{message}</p>}
    <details><summary>Support request history</summary>
      <p>This records explicit requests and actions. It does not measure how you used the support.</p>
      {history.map(item => <p key={item.id}>{item.kind === 'conceptual_hint' ? 'Conceptual hint request' : 'Accessibility support action'} {item.item_index + 1}, {item.stage_start_id ? 'fresh application' : 'supported response'}, {new Date(item.created_at).toLocaleString()}</p>)}
      {!history.length && <p>No recorded support actions yet.</p>}
      {offset !== null && <Button disabled={loading} onClick={() => {
        setLoading(true)
        api.student.helpHistory(taskId, undefined, offset).then(page => { setHistory(current => [...current, ...page.items.filter(item => !current.some(saved => saved.id === item.id))]); setOffset(page.next_offset) }).catch(() => setMessage('Earlier support requests could not be loaded. Try again.')).finally(() => setLoading(false))
      }}>Load earlier support requests</Button>}
    </details>
  </>
}
