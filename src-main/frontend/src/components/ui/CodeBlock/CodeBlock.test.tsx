import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { CodeBlock } from './CodeBlock'

describe('CodeBlock', () => {
  it('preserves indentation and line breaks exactly (FR13)', () => {
    const code = 'from qiskit import QuantumCircuit\n\ndef build():\n    qc = QuantumCircuit(2)\n    return qc'
    render(<CodeBlock code={code} label="Qiskit starter code" />)
    const pre = screen.getByLabelText('Qiskit starter code')
    expect(pre.textContent).toBe(code)
  })
})
