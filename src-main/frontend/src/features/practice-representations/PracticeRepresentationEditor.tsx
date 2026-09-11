import { useState } from 'react'
import type { PracticeRepresentation } from './api'
import { Button, Field, Input, Textarea } from '../../components/ui'

export function PracticeRepresentationEditor({ value, disabled, onChange }: { value: Record<string, unknown>; disabled: boolean; onChange: (value: Record<string, unknown>) => void }) {
  const items = Array.isArray(value.practice_representations) ? value.practice_representations as PracticeRepresentation[] : []
  const [circuitError, setCircuitError] = useState('')
  const update = (index: number, change: Partial<PracticeRepresentation>) => onChange({ ...value, practice_representations: items.map((item, offset) => offset === index ? { ...item, ...change } : item) })
  return <details><summary>Reviewed practice representations</summary>
    <p>Optional practice content only. Supply source passages and an equivalence rationale, then save and review the task revision. Accessibility support must preserve the construct and contain no instructional help. This editor does not approve equivalence or create transfer access conditions.</p>
    {items.map((item, index) => <fieldset key={item.representation_id} disabled={disabled}>
      <legend>Practice representation {index + 1}</legend>
      <Field label="Representation title"><Input value={item.title} maxLength={200} onChange={event => update(index, { title: event.target.value })} /></Field>
      <label>Representation format <select value={item.mode} onChange={event => update(index, { mode: event.target.value as PracticeRepresentation['mode'], circuit: null })}>{['text', 'visual', 'worked_example', 'circuit', 'stepwise'].map(mode => <option key={mode} value={mode}>{mode.replace('_', ' ')}</option>)}</select></label>
      <label>Explanation detail <select value={item.explanation_detail} onChange={event => update(index, { explanation_detail: event.target.value as 'brief' | 'detailed' })}><option value="brief">Brief</option><option value="detailed">Detailed</option></select></label>
      <label>Support declaration <select value={item.support_kind} onChange={event => update(index, { support_kind: event.target.value as PracticeRepresentation['support_kind'], instructional_support_level: event.target.value === 'accessibility' ? 0 : 2 })}><option value="instructional">Instructional</option><option value="accessibility">Accessibility only</option></select></label>
      {item.support_kind === 'instructional' && <label>Instructional support level <select value={item.instructional_support_level} onChange={event => update(index, { instructional_support_level: Number(event.target.value) })}><option value={1}>Goal reminder</option><option value={2}>Concept cue</option><option value={3}>Narrowing hint</option><option value={4}>Partial worked step</option></select></label>}
      <Field label="Equivalent text"><Textarea value={item.text} maxLength={4000} onChange={event => update(index, { text: event.target.value })} /></Field>
      <Field label="Labelled steps (one per line)"><Textarea value={item.steps.join('\n')} onChange={event => update(index, { steps: event.target.value.split('\n') })} /></Field>
      <Field label="Approved task source passage IDs (one per line)"><Textarea value={item.source_references.join('\n')} onChange={event => update(index, { source_references: event.target.value.split('\n') })} /></Field>
      <Field label="Construct equivalence and support rationale"><Textarea maxLength={2000} value={item.equivalence_basis} onChange={event => update(index, { equivalence_basis: event.target.value })} /></Field>
      {item.mode === 'circuit' && <Field label="Circuit definition"><Textarea defaultValue={JSON.stringify(item.circuit, null, 2)} onBlur={event => { try { const circuit: unknown = JSON.parse(event.target.value); if (!circuit || typeof circuit !== 'object' || Array.isArray(circuit)) throw new Error(); update(index, { circuit: circuit as Record<string, unknown> }); setCircuitError('') } catch { update(index, { circuit: null }); setCircuitError('Enter a valid circuit object before saving.') } }} /></Field>}
      <Button disabled={disabled} onClick={() => onChange({ ...value, practice_representations: items.filter((_, offset) => offset !== index) })}>Remove representation {index + 1}</Button>
    </fieldset>)}
    {circuitError && <p role="alert">{circuitError}</p>}
    <Button disabled={disabled || items.length >= 20} onClick={() => onChange({ ...value, practice_representations: [...items, { representation_id: crypto.randomUUID(), mode: 'text', title: '', text: '', steps: [], circuit: null, source_references: [], equivalence_basis: '', support_kind: 'instructional', instructional_support_level: 2, explanation_detail: 'brief' }] })}>Add practice representation</Button>
  </details>
}
