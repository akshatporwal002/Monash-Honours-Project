import { describe, expect, it } from 'vitest'

import { bloomProcessLabels, bloomProcessPlain } from './bloom'
import { bloomKnowledgeValues, bloomProcessValues } from '../../features/assessment/types'
import { bloomKnowledgeLabels } from './bloom'

describe('bloom plain-language wording', () => {
  it('covers every Bloom process value', () => {
    for (const value of bloomProcessValues) {
      expect(bloomProcessLabels[value]).toBeTruthy()
      expect(bloomProcessPlain(value)).toContain('—')
    }
  })

  it('covers every knowledge dimension value', () => {
    for (const value of bloomKnowledgeValues) {
      expect(bloomKnowledgeLabels[value]).toBeTruthy()
    }
  })

  it('uses en-AU spelling: Analyse, never Analyze', () => {
    expect(bloomProcessLabels.ANALYSE).toBe('Analyse')
    expect(JSON.stringify(bloomProcessLabels)).not.toMatch(/analyz/i)
  })

  it('never frames Bloom as a score or level number', () => {
    for (const value of bloomProcessValues) {
      expect(bloomProcessPlain(value)).not.toMatch(/\b(score|level \d|points?)\b/i)
    }
  })
})
