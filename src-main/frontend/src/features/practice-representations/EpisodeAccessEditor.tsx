import { CircuitSpecificationEditor } from '../../components/TaskMarkingEditor'
import { Button, Field, Input, Textarea } from '../../components/ui'

type Content = Record<string, unknown>
const object = (value: unknown): Content => value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Content : {}
const text = (value: unknown) => typeof value === 'string' ? value : ''
const lines = (value: unknown) => Array.isArray(value) ? value.join('\n') : ''

export function EpisodeAccessEditor({ value, disabled, onChange }: { value: Content; disabled: boolean; onChange: (next: Content) => void }) {
  const plan = object(value.episode_plan)
  if (!value.episode_plan) return null
  return <details><summary>Equivalent access forms by stage</summary>
    <p>Access forms must preserve the input and required response without hints or solutions. Each stage is reviewed and frozen with its task form; transfer content stays private until stage entry.</p>
    {(['supported', 'transfer'] as const).map(stage => {
      const stagePlan = stage === 'supported' ? plan : object(plan.transfer)
      const items = Array.isArray(stagePlan.access_representations) ? stagePlan.access_representations : []
      const save = (next: unknown[]) => onChange({ ...value, episode_plan: stage === 'supported' ? { ...plan, access_representations: next } : { ...plan, transfer: { ...stagePlan, access_representations: next } } })
      return <fieldset key={stage} disabled={disabled}><legend>{stage === 'supported' ? 'Supported work access' : 'Transfer access'}</legend>
        {items.map((row, index) => {
          const item = object(row)
          const update = (key: string, next: unknown) => save(items.map((original, i) => i === index ? { ...item, [key]: next, instructional_support_level: 0 } : original))
          return <fieldset key={index}><legend>{stage} access {index + 1}</legend>
            <Field label={`${stage} access ${index + 1} title`}><Input value={text(item.title)} maxLength={200} onChange={event => update('title', event.target.value)} /></Field>
            <label>{stage} access format <select value={text(item.mode)} onChange={event => { const mode = event.target.value; save(items.map((original, i) => i === index ? { ...item, mode, circuit: null, instructional_support_level: 0 } : original)) }}>{['text', 'visual', 'stepwise', 'circuit'].map(mode => <option key={mode}>{mode}</option>)}</select></label>
            <Field label={`${stage} access ${index + 1} equivalent text`}><Textarea value={text(item.text)} maxLength={4000} onChange={event => update('text', event.target.value)} /></Field>
            <Field label={`${stage} access ${index + 1} labelled parts`}><Textarea value={lines(item.steps)} onChange={event => update('steps', event.target.value.split('\n').filter(Boolean))} /></Field>
            <Field label={`${stage} access ${index + 1} source passages`}><Textarea value={lines(item.source_references)} onChange={event => update('source_references', event.target.value.split('\n').filter(Boolean))} /></Field>
            <Field label={`${stage} access ${index + 1} equivalence rationale`}><Textarea value={text(item.equivalence_basis)} maxLength={2000} onChange={event => update('equivalence_basis', event.target.value)} /></Field>
            {item.mode === 'circuit' && <CircuitSpecificationEditor label={`${stage} access ${index + 1} circuit`} value={item.circuit} disabled={disabled} onChange={next => update('circuit', next)} />}
            <Button onClick={() => save(items.filter((_, i) => i !== index))}>Remove {stage} access {index + 1}</Button>
          </fieldset>
        })}
        <Button disabled={disabled || items.length >= 20} onClick={() => save([...items, { mode: 'text', title: '', text: '', steps: [], circuit: null, source_references: [], equivalence_basis: '', instructional_support_level: 0, explanation_detail: 'detailed' }])}>Add {stage} access form</Button>
      </fieldset>
    })}
  </details>
}
