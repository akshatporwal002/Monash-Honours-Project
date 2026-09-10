import { render, screen, within } from '@testing-library/react'
import { EpisodeCircuitText, EpisodeSnapshot } from '../components/EpisodeSnapshot'
import type { EpisodePayload } from '../app/types'

test.each([
  { targets: [0, 1], description: 'CX, control qubit 0, target qubit 1' },
  { targets: [1, 0], description: 'CX, control qubit 1, target qubit 0' },
])('live and saved circuit text name CX roles for $targets in stored gate order', ({ targets, description }) => {
  const circuit = { qubits: 2, operations: [
    { gate: 'h', targets: [1] },
    { gate: 'cx', targets },
    { gate: 'x', targets: [0] },
  ] }
  const original = JSON.stringify(circuit)
  const episode: EpisodePayload = {
    schema_version: 'learnlens.episode.v1',
    supported: { prediction: { circuit } },
    transfer: { stage_start_id: 'start', part_id: 'fresh', content: { circuit }, process: {} },
  }
  render(<><EpisodeCircuitText circuit={circuit} /><EpisodeSnapshot episode={episode} /></>)

  expect(screen.getByLabelText('Circuit text equivalent').textContent).toBe(
    `2 qubits\n1. H on qubit 1\n2. ${description}\n3. X on qubit 0`,
  )
  const savedCircuits = screen.getAllByLabelText('Saved episode circuit')
  expect(savedCircuits).toHaveLength(2)
  for (const saved of savedCircuits) {
    expect(within(saved).getByText('2 qubits')).toBeVisible()
    expect(within(saved).getAllByRole('listitem').map(item => item.textContent)).toEqual([
      'H on qubit 1', description, 'X on qubit 0',
    ])
  }
  expect(JSON.stringify(circuit)).toBe(original)
})

test('live empty circuit text retains its no-gates description', () => {
  render(<EpisodeCircuitText circuit={{ qubits: 1, operations: [] }} />)
  expect(screen.getByLabelText('Circuit text equivalent').textContent).toBe('1 qubits\nNo gates added.')
})
