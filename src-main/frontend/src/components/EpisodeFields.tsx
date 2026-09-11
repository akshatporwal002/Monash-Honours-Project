import styles from "./EpisodeFields.module.css"
import type { ReactNode } from 'react'
import { EpisodeCircuitText } from "./EpisodeSnapshot"
import type { EpisodePayload, EpisodeProcess, EpisodeState, TaskSubmission } from '../app/types'
import { Button, Card, Field, Textarea } from './ui'


export function EpisodeFields({ value, state, attempts, disabled, onChange, onCheckpoint, onTransfer, onTransferCheckpoint, onTransferSimulation, support, standaloneTransfer = false }: {
  standaloneTransfer?: boolean
  value: EpisodePayload
  state: EpisodeState | null
  attempts: TaskSubmission[]
  disabled: boolean
  onChange: (value: EpisodePayload) => void
  onCheckpoint: () => void
  onTransfer: () => void
  onTransferCheckpoint: () => void
  onTransferSimulation: () => void
  support?: ReactNode
}) {
  const update = (field: keyof EpisodeProcess, content: unknown) => onChange({ ...value, supported: { ...value.supported, [field]: content } })
  const transferChange = (transfer: EpisodePayload['transfer']) => {
    const changedInput = JSON.stringify(transfer?.content) !== JSON.stringify(value.transfer?.content)
    onChange({ ...value, transfer: transfer && changedInput ? { ...transfer, process: { ...transfer.process, prediction_checkpoint_id: null, simulation_references: [] } } : transfer })
  }
  const addTransferGate = (gate: 'h' | 'x') => {
    if (!value.transfer) return
    const circuit = value.transfer.content.circuit ?? state?.transfer?.starter_circuit ?? { qubits: 1, operations: [] }
    const operations = Array.isArray(circuit.operations) ? circuit.operations : []
    transferChange({ ...value.transfer, content: { ...value.transfer.content, circuit: { ...circuit, operations: [...operations, { gate, targets: [0] }] } }, process: { ...value.transfer.process, simulation_references: [] } })
  }
  return <Card heading="Learning episode">
    <nav className={styles.navigation} aria-label="Episode sections"><a href="#episode-prediction">Prediction</a>{' | '}<a href="#episode-explanation">Explanation</a>{' | '}<a href="#episode-reflection">Reflection</a>{' | '}<a href="#episode-transfer">Fresh application</a></nav>
    <fieldset className={styles.stage} disabled={disabled}>
      <legend>Supported response</legend>
      {standaloneTransfer && <Field label="New-context application"><Textarea value={value.supported.application?.answer ?? ''} onChange={event => update('application', { answer: event.target.value })} /></Field>}
      <div id="episode-prediction">
        <Field label="Your prediction before results" help="Your original prediction is saved before results become available.">
          <Textarea value={value.supported.prediction?.answer ?? ''} readOnly={Boolean(value.supported.prediction_checkpoint_id)} onChange={event => update('prediction', { ...value.supported.prediction, answer: event.target.value })} />
        </Field>
        {state && <Button variant="secondary" onClick={onCheckpoint} disabled={!value.supported.prediction?.answer?.trim()}>Record prediction for this input</Button>}
        {value.supported.prediction_checkpoint_id && <><p role="status">Original prediction recorded. Each changed circuit needs its own checkpoint.</p><Button variant="quiet" onClick={() => onChange({ ...value, supported: { ...value.supported, prediction: { answer: '' }, prediction_checkpoint_id: null, simulation_references: [] } })}>Write a new prediction</Button></>}
      </div>
      <Field label="Your reasoning"><Textarea value={value.supported.reasoning ?? ''} onChange={event => update('reasoning', event.target.value)} /></Field>
      <div id="episode-explanation"><Field label="Explain the result"><Textarea value={value.supported.explanation ?? ''} onChange={event => update('explanation', event.target.value)} /></Field></div>
      <div id="episode-reflection"><Field label="Your reflection" help="Reflection and approved support do not lower your result."><Textarea value={value.supported.reflection ?? ''} onChange={event => update('reflection', event.target.value)} /></Field></div>
      {attempts.some(attempt => attempt.id) && <>
        <label htmlFor="episode-revision">Revise an earlier response</label>
        <select id="episode-revision" value={value.supported.revision?.previous_response_version_id ?? ''} onChange={event => update('revision', event.target.value ? { previous_response_version_id: event.target.value, reason: value.supported.revision?.reason ?? '' } : null)}>
          <option value="">No revision link</option>
          {attempts.filter(attempt => attempt.id).map(attempt => <option key={attempt.id} value={attempt.id}>Response {attempt.attempt_number}</option>)}
        </select>
        {value.supported.revision && <Field label="Reason for your revision"><Textarea value={value.supported.revision.reason} onChange={event => update('revision', { ...value.supported.revision, reason: event.target.value })} /></Field>}
      </>}
    </fieldset>
    {state && <>
      <section className={styles.support} aria-label="Approved support">
        <h3>Approved support</h3>
        {support ?? (state.accessibility_support ?? []).map((description, index) => <p key={index}>{description}</p>)}
      </section>
      <section className={styles.transfer} id="episode-transfer" aria-label="Fresh application">
        <h3>Fresh application</h3>
        {state.transfer ? <>
          <p>{state.transfer.prompt}</p><p>{state.transfer.instructions}</p>
          <Field label="Fresh application response"><Textarea disabled={disabled} value={value.transfer?.content.answer ?? ''} onChange={event => transferChange({ stage_start_id: state.transfer!.stage_start_id, part_id: state.transfer!.part_id, content: { ...value.transfer?.content, answer: event.target.value }, process: value.transfer?.process ?? {} })} /></Field>
          <Field label="Fresh application code"><Textarea disabled={disabled} spellCheck={false} value={value.transfer?.content.code ?? state.transfer.starter_code ?? ''} onChange={event => transferChange({ stage_start_id: state.transfer!.stage_start_id, part_id: state.transfer!.part_id, content: { answer: '', ...value.transfer?.content, code: event.target.value }, process: value.transfer?.process ?? {} })} /></Field>
          {state.transfer.starter_circuit && <>
            <fieldset className={styles.stage} disabled={disabled}><legend>Fresh application circuit</legend>
              <Button onClick={() => addTransferGate('h')}>Add fresh H gate</Button>{' '}
              <Button onClick={() => addTransferGate('x')}>Add fresh X gate</Button>{' '}
              <Button onClick={() => value.transfer && transferChange({ ...value.transfer, content: { ...value.transfer.content, circuit: { ...value.transfer.content.circuit, qubits: state.transfer!.starter_circuit!.qubits, operations: [] } }, process: { ...value.transfer.process, simulation_references: [] } })}>Clear fresh circuit</Button>
              <div aria-label="Fresh application circuit text"><EpisodeCircuitText circuit={value.transfer?.content.circuit ?? state.transfer.starter_circuit} /></div>
              <Field label="Fresh application prediction"><Textarea value={value.transfer?.process.prediction?.answer ?? ''} readOnly={Boolean(value.transfer?.process.prediction_checkpoint_id)} onChange={event => value.transfer && transferChange({ ...value.transfer, process: { ...value.transfer.process, prediction: { answer: event.target.value } } })} /></Field>
              {value.transfer?.process.prediction_checkpoint_id && <Button onClick={() => value.transfer && transferChange({ ...value.transfer, process: { ...value.transfer.process, prediction: { answer: '' }, prediction_checkpoint_id: null, simulation_references: [] } })}>Write a new fresh prediction</Button>}
              <Button onClick={onTransferCheckpoint}>Record fresh prediction</Button>{' '}
              <Button onClick={onTransferSimulation} disabled={!value.transfer?.process.prediction_checkpoint_id}>Run fresh circuit</Button>
            </fieldset>
          </>}
          {(['reasoning', 'explanation', 'reflection'] as const).map(field => <Field key={field} label={`Fresh application ${field}`}><Textarea disabled={disabled} value={value.transfer?.process[field] ?? ''} onChange={event => onChange({ ...value, transfer: { stage_start_id: state.transfer!.stage_start_id, part_id: state.transfer!.part_id, content: value.transfer?.content ?? { answer: '' }, process: { ...value.transfer?.process, [field]: event.target.value } } })} /></Field>)}
        </> : <><p>The fresh prompt opens after you record your prediction and explanation.</p><Button disabled={disabled} onClick={onTransfer}>Start unaided fresh application</Button></>}
      </section>
    </>}
  </Card>
}
