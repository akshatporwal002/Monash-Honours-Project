import { CircuitSpecificationEditor } from './TaskMarkingEditor'
import { Button, Checkbox, Field, Textarea } from './ui'

type Content = Record<string, unknown>
const object = (value: unknown): Content => value !== null && typeof value === 'object'
  && !Array.isArray(value) ? value as Content : {}
const text = (value: unknown): string => typeof value === 'string' ? value : ''
const lines = (value: unknown): string => Array.isArray(value) ? value.map(String).join('\n') : ''

export function EpisodePlanEditor({ value, disabled, onChange }: {
  value: Content; disabled: boolean; onChange: (value: Content) => void
}) {
  const plan = object(value.episode_plan)
  const enabled = value.episode_plan != null
  const transfer = object(plan.transfer)
  const solution = object(transfer.solution)
  const setPlan = (key: string, next: unknown) => onChange({ ...value, episode_plan: { ...plan, [key]: next } })
  const setTransfer = (key: string, next: unknown) => setPlan('transfer', { ...transfer, [key]: next })
  return <fieldset disabled={disabled}>
    <legend>Supported work and fresh transfer</legend>
    <Checkbox label="Include a separate unaided transfer stage" checked={enabled} onChange={(event) => {
      const next = { ...value }
      if (event.target.checked) next.episode_plan = {
        schema_version: 'learnlens.episode-plan.v1', supported_part_id: 'supported',
        prediction_required: true, required_responses: ['prediction', 'explanation'],
        supported_hints: [], accessibility_support: [],
        transfer: { part_id: 'transfer', prompt: '', instructions: 'Apply what you learned to this fresh task without instructional hints.' },
      }
      else delete next.episode_plan
      onChange(next)
    }} />
    {enabled && <>
      <p>Review the supported work, conceptual hints, and fresh task together. Changes require a new saved revision and approval.</p>
      <p>Fresh task content stays hidden until the learner enters transfer. Solutions remain private to authorised reviewers.</p>
      <Field label="Approved conceptual hints" help="One hint per line. Learners may use approved hints without a count limit during supported work.">
        <Textarea value={lines(plan.supported_hints)} onChange={(event) => setPlan('supported_hints', event.target.value.split('\n').filter((line) => line.trim()))} />
      </Field>
      <Field label="Accessibility support for both stages" help="One support per line. Keep access support separate from instructional hints.">
        <Textarea value={lines(plan.accessibility_support)} onChange={(event) => setPlan('accessibility_support', event.target.value.split('\n').filter((line) => line.trim()))} />
      </Field>
      <Field label="Fresh transfer prompt" required><Textarea value={text(transfer.prompt)} onChange={(event) => setTransfer('prompt', event.target.value)} /></Field>
      <Field label="Fresh transfer instructions"><Textarea value={text(transfer.instructions)} onChange={(event) => setTransfer('instructions', event.target.value)} /></Field>
      <Field label="Fresh transfer starter code" help="Optional. Code formatting is preserved."><Textarea value={text(transfer.starter_code)} onChange={(event) => setTransfer('starter_code', event.target.value || null)} /></Field>
      {transfer.starter_circuit != null ? <>
        <CircuitSpecificationEditor label="Transfer starter circuit" value={transfer.starter_circuit} disabled={disabled} onChange={(next) => setTransfer('starter_circuit', next)} />
        <Button variant="quiet" onClick={() => setTransfer('starter_circuit', null)}>Remove transfer starter circuit</Button>
      </> : <Button variant="secondary" onClick={() => setTransfer('starter_circuit', { qubits: 1, operations: [] })}>Add transfer starter circuit</Button>}
      <Field label="Private transfer solution" help="Optional marking guidance. This is never released through the learner stage endpoint.">
        <Textarea value={text(solution.answer)} onChange={(event) => setTransfer('solution', { ...solution, answer: event.target.value })} />
      </Field>
    </>}
  </fieldset>
}
