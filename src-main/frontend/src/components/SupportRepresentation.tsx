import { EpisodeCircuitText } from './EpisodeSnapshot'

export type Representation = {
  instructional_support_level: number
  mode: 'text' | 'visual' | 'worked_example' | 'circuit' | 'stepwise'
  title: string; text: string; steps: string[]; circuit: Record<string, unknown> | null
  source_references: string[]; equivalence_basis: string
}

function CircuitDiagram({ circuit }: { circuit: Record<string, unknown> }) {
  const qubits = typeof circuit.qubits === 'number' ? circuit.qubits : 1
  const operations = Array.isArray(circuit.operations) ? circuit.operations as Array<{ gate: string; targets: number[] }> : []
  const width = Math.max(240, 100 + operations.length * 60)
  return <div style={{ overflowX: 'auto' }}><svg aria-hidden="true" width={width} height={qubits * 50 + 20}>
    {Array.from({ length: qubits }, (_, index) => <g key={index}><text x={0} y={35 + index * 50} fill="currentColor">q{index}</text><line x1={35} y1={30 + index * 50} x2={width} y2={30 + index * 50} stroke="currentColor" /></g>)}
    {operations.map((operation, index) => {
      const x = 65 + index * 60
      return <g key={index}>{operation.gate === 'cx' && <line x1={x} x2={x} y1={30 + operation.targets[0] * 50} y2={30 + operation.targets[1] * 50} stroke="currentColor" />}{operation.targets.map((target, position) => <g key={target}>
        {operation.gate === 'cx' && position === 0 ? <circle cx={x} cy={30 + target * 50} r={5} fill="currentColor" /> : <><rect x={x - 15} y={15 + target * 50} width={30} height={30} fill="var(--surface, white)" stroke="currentColor" /><text x={x} y={35 + target * 50} textAnchor="middle" fill="currentColor">{operation.gate === 'cx' ? 'X' : operation.gate.toUpperCase()}</text></>}
      </g>)}</g>
    })}
  </svg></div>
}

export function SupportRepresentation({ value }: { value: Representation }) {
  return <section aria-label={`Approved ${value.mode.replace('_', ' ')} support`}>
    <h4>{value.title}</h4><p style={{ whiteSpace: 'pre-wrap' }}>{value.text}</p>
    {value.mode === 'visual' && <div aria-hidden="true" style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>{value.steps.map((step, index) => <div key={index} style={{ border: '2px solid currentColor', borderRadius: 8, padding: 12, maxWidth: 260 }}>{index + 1}. {step}{index < value.steps.length - 1 ? ' →' : ''}</div>)}</div>}
    {value.steps.length > 0 && <ol aria-label={value.mode === 'visual' ? 'Text equivalent of the diagram' : 'Explanation steps'}>{value.steps.map((step, index) => <li key={index}>{step}</li>)}</ol>}
    {value.circuit && <><CircuitDiagram circuit={value.circuit} /><EpisodeCircuitText circuit={value.circuit} /></>}
    <p>Sources: {value.source_references.join(', ')}</p>
    <details><summary>Why this format is approved</summary><p>{value.equivalence_basis}</p></details>
  </section>
}
