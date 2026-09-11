import type { EpisodeContent, EpisodePayload, EpisodeProcess } from '../app/types'

function describeOperation(item: unknown) {
  const operation = item as { gate?: string; targets?: number[] }
  const gate = operation.gate?.toUpperCase()
  return gate === 'CX'
    ? `${gate}, control qubit ${operation.targets?.[0]}, target qubit ${operation.targets?.[1]}`
    : `${gate} on qubit ${operation.targets?.join(', ')}`
}

export function EpisodeCircuitText({ circuit }: { circuit: Record<string, unknown> }) {
  const operations = Array.isArray(circuit.operations) ? circuit.operations : []
  return <pre style={{ whiteSpace: 'pre-wrap' }} aria-label="Circuit text equivalent">{`${String(circuit.qubits)} qubits\n${operations.length ? operations.map((item, index) => `${index + 1}. ${describeOperation(item)}`).join('\n') : 'No gates added.'}`}</pre>
}

function Content({ content }: { content: EpisodeContent }) {
  const circuit = content.circuit
  const operations = circuit && Array.isArray(circuit.operations) ? circuit.operations : []
  return <>
    {content.answer && <pre style={{ whiteSpace: 'pre-wrap' }}>{content.answer}</pre>}
    {content.code && <pre aria-label="Saved response code">{content.code}</pre>}
    {circuit && <div aria-label="Saved episode circuit">
      <p>{String(circuit.qubits)} qubits</p>
      <ol>{operations.map((item, index) => <li key={index}>{describeOperation(item)}</li>)}</ol>
    </div>}
  </>
}

function Process({ process }: { process: EpisodeProcess }) {
  return <>
    {process.application && <><h4>New-context application</h4><Content content={process.application} /></>}
    {process.prediction && <><h4>Original prediction</h4><Content content={process.prediction} /></>}
    {(['reasoning', 'explanation', 'reflection'] as const).map(field => process[field] ? <div key={field}><h4>{field.charAt(0).toUpperCase() + field.slice(1)}</h4><pre style={{ whiteSpace: 'pre-wrap' }}>{process[field]}</pre></div> : null)}
    {process.revision && <><h4>Revision reason</h4><pre style={{ whiteSpace: 'pre-wrap' }}>{process.revision.reason}</pre><p>This response links to an earlier saved version.</p></>}
    {Boolean(process.simulation_references?.length) && <p>{process.simulation_references!.length} saved simulation reference(s).</p>}
  </>
}

export function EpisodeSnapshot({ episode }: { episode: EpisodePayload }) {
  return <section aria-label="Saved learning episode">
    <h3>Supported response</h3><Process process={episode.supported} />
    {episode.transfer && <><h3>Fresh application response</h3><Content content={episode.transfer.content} /><Process process={episode.transfer.process} /></>}
  </section>
}
