export interface CircuitRuleDraft {
  kind: 'circuit_v1'
  stage: 'supported' | 'transfer'
  qubits: number
  operations: Array<{ gate: 'h' | 'x' | 'cx'; targets: number[] }>
}

/** Parse the educator's declared structural claim without accepting executable code. */
export function buildCircuitRuleDraft(
  qubitText: string,
  gateText: string,
  stage: CircuitRuleDraft['stage'],
): CircuitRuleDraft | null {
  const qubits = Number(qubitText)
  if (!Number.isInteger(qubits) || qubits < 1 || qubits > 5) return null
  const lines = gateText.split('\n').map((line) => line.trim()).filter(Boolean)
  if (lines.length > 30) return null
  const operations: CircuitRuleDraft['operations'] = []
  for (const line of lines) {
    const match = /^(h|x|cx)\s+(\d)(?:\s+(\d))?$/i.exec(line)
    if (!match) return null
    const gate = match[1].toLowerCase()
    if (gate !== 'h' && gate !== 'x' && gate !== 'cx') return null
    const targets = match[3] === undefined ? [Number(match[2])] : [Number(match[2]), Number(match[3])]
    if (targets.length !== (gate === 'cx' ? 2 : 1)
      || new Set(targets).size !== targets.length || targets.some((target) => target >= qubits)) return null
    operations.push({ gate, targets })
  }
  return { kind: 'circuit_v1', stage, qubits, operations }
}
