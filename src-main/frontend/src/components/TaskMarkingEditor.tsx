import { Button, Field, Input, Select, Textarea } from './ui'

type Content = Record<string, unknown>
function contentObject(value: unknown): Content {
  return value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Content : {}
}
const list = (value: unknown): unknown[] => Array.isArray(value) ? value : []
const lines = (value: unknown) => list(value).map(String).join('\n')

export function CircuitSpecificationEditor({ label, value, disabled, onChange }: { label: string; value: unknown; disabled: boolean; onChange: (value: Content) => void }) {
  const circuit = contentObject(value)
  const operations = list(circuit.operations)
  const set = (key: string, next: unknown) => onChange({ ...circuit, [key]: next })
  return <fieldset disabled={disabled}>
    <legend>{label}</legend>
    <p>Supported gates are H, X, and CX. Qubit numbers start at zero. Approval checks the saved circuit.</p>
    <Field label={`${label} qubits`}><Input type="number" min={1} max={5} step={1} value={String(circuit.qubits ?? '')} onChange={(event) => set('qubits', Number(event.target.value))} /></Field>
    <Field label={`${label} shots`}><Input type="number" min={1} max={4096} step={1} value={String(circuit.shots ?? 1024)} onChange={(event) => set('shots', Number(event.target.value))} /></Field>
    <Field label={`${label} seed`}><Input type="number" min={0} step={1} value={String(circuit.seed ?? 42)} onChange={(event) => set('seed', Number(event.target.value))} /></Field>
    <ol>{operations.map((operation, index) => {
      const row = contentObject(operation)
      const replace = (key: string, next: unknown) => set('operations', operations.map((item, itemIndex) => itemIndex === index ? { ...row, [key]: next } : item))
      return <li key={index}>
        <Field label={`${label} gate ${index + 1}`}><Select value={typeof row.gate === 'string' ? row.gate : ''} disabled={disabled} onValueChange={(gate) => replace('gate', gate)} options={['h', 'x', 'cx'].map((gate) => ({ value: gate, label: gate.toUpperCase() }))} /></Field>
        <Field label={`${label} targets ${index + 1}`} help="For CX, enter control then target, separated by a comma."><Input value={list(row.targets).join(',')} onChange={(event) => replace('targets', event.target.value.split(',').map((target) => target.trim() === '' ? null : Number(target)))} /></Field>
        <Button variant="quiet" onClick={() => set('operations', operations.filter((_, itemIndex) => itemIndex !== index))}>Remove {label.toLowerCase()} gate {index + 1}</Button>
      </li>
    })}</ol>
    <Button disabled={disabled || operations.length >= 30} variant="secondary" onClick={() => set('operations', [...operations, { gate: 'h', targets: [0] }])}>Add {label.toLowerCase()} gate</Button>
  </fieldset>
}

export function TaskMarkingEditor({ taskType, value, disabled, onChange }: { taskType: string; value: Content; disabled: boolean; onChange: (value: Content) => void }) {
  const set = (key: string, next: unknown) => onChange({ ...value, [key]: next })
  const fields: Array<[string, string]> = [
    ['required_keywords', 'Required keywords'], ['required_terms', 'Required terms'],
    ['required_code_fragments', 'Required code fragments'], ['correct_answers', 'Correct choice IDs'],
    ['required_gates', 'Required gates'], ['allowed_gates', 'Allowed gates'],
  ]
  const primary: Record<string, string[]> = {
    short_answer: ['required_keywords'], code_explanation: ['required_terms'],
    code_completion: ['required_code_fragments'], multiple_answer: ['correct_answers'],
    quantum_circuit: ['required_gates', 'allowed_gates'], circuit: ['required_gates', 'allowed_gates'],
  }
  const choices = list(value.choices)
  const circuitTask = taskType === 'quantum_circuit' || taskType === 'circuit'
  return <fieldset disabled={disabled}>
    <legend>Marking guidance</legend>
    {fields.filter(([key]) => key in value || primary[taskType]?.includes(key)).map(([key, label]) => <Field key={key} label={label} help="Enter one item per line.">
      <Textarea value={lines(value[key])} onChange={(event) => set(key, event.target.value.split('\n'))} />
    </Field>)}
    {(['multiple_choice', 'multiple_answer'].includes(taskType) || 'choices' in value) && <>
      <h4>Answer choices</h4>
      {choices.map((choice, index) => {
        const row = contentObject(choice)
        const replace = (key: string, next: string) => set('choices', choices.map((item, itemIndex) => itemIndex === index ? { ...row, [key]: next } : item))
        return <div key={index}>
          <Field label={`Choice ${index + 1} ID`}><Input value={String(row.id ?? '')} onChange={(event) => replace('id', event.target.value)} /></Field>
          <Field label={`Choice ${index + 1} text`}><Textarea value={String(row.text ?? '')} onChange={(event) => replace('text', event.target.value)} /></Field>
          <Button variant="quiet" onClick={() => set('choices', choices.filter((_, itemIndex) => itemIndex !== index))}>Remove choice {index + 1}</Button>
        </div>
      })}
      <Button variant="secondary" onClick={() => set('choices', [...choices, { id: '', text: '' }])}>Add answer choice</Button>
    </>}
    {'starter_circuit' in value ? <CircuitSpecificationEditor label="Starter circuit" value={value.starter_circuit} disabled={disabled} onChange={(next) => set('starter_circuit', next)} /> : circuitTask && <>
      <p>No starter circuit is saved.</p>
      <Button variant="secondary" onClick={() => set('starter_circuit', { qubits: 1, operations: [] })}>Add starter circuit</Button>
    </>}
    {'expected_circuit' in value ? <>
      <CircuitSpecificationEditor label="Expected circuit" value={value.expected_circuit} disabled={disabled} onChange={(next) => set('expected_circuit', next)} />
      <Button variant="quiet" onClick={() => { const next = { ...value }; delete next.expected_circuit; onChange(next) }}>Remove expected circuit</Button>
    </> : circuitTask && <Button variant="secondary" onClick={() => set('expected_circuit', { qubits: 1, operations: [] })}>Add expected circuit</Button>}
  </fieldset>
}
