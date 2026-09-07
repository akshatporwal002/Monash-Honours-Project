import { describe, expect, it } from 'vitest'

import { buildAssessmentDraft, initialSetupValues, missingSetupFields } from './assessmentDraft'
import { buildCircuitRuleDraft } from './circuitRuleDraft'

describe('approved circuit authoring', () => {
  it('preserves an ordered structural claim and routes mixed work to human review', () => {
    const values = {
      ...initialSetupValues, courseId: 'course', evaluatorType: 'circuit_mixed' as const,
      circuitQubits: '2', circuitOperations: 'H 0\nCX 0 1', circuitStage: 'transfer' as const,
    }
    expect(buildAssessmentDraft(values).criteria[0]).toMatchObject({
      evaluator_type: 'mixed', evidence_source_types: ['learner_response'],
      approved_anchors: { kind: 'circuit_v1', stage: 'transfer', qubits: 2, operations: [
        { gate: 'h', targets: [0] }, { gate: 'cx', targets: [0, 1] },
      ] },
    })
    expect(missingSetupFields({ ...values, bloomProcess: 'REMEMBER' })).toContain('Apply target for circuit structure rules')
  })

  it.each(['H 2', 'CX 0 0', 'RX 0', 'H 0 1', 'CX 0', 'H 0; alert(1)'])(
    'rejects an unsupported or malformed structural claim: %s', (gates) => {
      expect(buildCircuitRuleDraft('2', gates, 'supported')).toBeNull()
    },
  )

  it('rejects oversized circuits and keeps a declared empty circuit valid', () => {
    expect(buildCircuitRuleDraft('6', 'H 0', 'supported')).toBeNull()
    expect(buildCircuitRuleDraft('1.5', 'H 0', 'supported')).toBeNull()
    expect(buildCircuitRuleDraft('1', Array(31).fill('H 0').join('\n'), 'supported')).toBeNull()
    expect(buildCircuitRuleDraft('1', '', 'supported')).toEqual({ kind: 'circuit_v1', stage: 'supported', qubits: 1, operations: [] })
  })
})
