import type { BloomKnowledge, BloomProcess } from '../../features/assessment/types'

/**
 * Single source for learner-facing Bloom wording (plan 006 Step 3).
 * Descriptor wording follows the D2 §5.1 table
 * (docs/02-pass-incomplete-bloom-assessment-spec.md:86-93).
 * Bloom names the evidence target — it is not a score and never a numeric ladder.
 */

export const bloomProcessLabels: Record<BloomProcess, string> = {
  REMEMBER: 'Remember',
  UNDERSTAND: 'Understand',
  APPLY: 'Apply',
  ANALYSE: 'Analyse',
  EVALUATE: 'Evaluate',
  CREATE: 'Create',
}

export const bloomProcessDescriptors: Record<BloomProcess, string> = {
  REMEMBER: 'Retrieve or recognise accurate facts, terms, or symbols.',
  UNDERSTAND: 'Explain, predict, compare, classify, or represent meaning.',
  APPLY: 'Select and use a known method in a suitable case.',
  ANALYSE: 'Break a problem into parts and explain relations or causes.',
  EVALUATE: 'Judge options against stated criteria and justify the judgement.',
  CREATE: 'Design, test, revise, and defend a solution under constraints.',
}

export const bloomKnowledgeLabels: Record<BloomKnowledge, string> = {
  FACTUAL: 'Factual knowledge',
  CONCEPTUAL: 'Conceptual knowledge',
  PROCEDURAL: 'Procedural knowledge',
  METACOGNITIVE: 'Metacognitive knowledge',
}

/** "Analyse — break a problem into parts and explain relations or causes." */
export function bloomProcessPlain(process: BloomProcess): string {
  const descriptor = bloomProcessDescriptors[process]
  return `${bloomProcessLabels[process]} — ${descriptor.charAt(0).toLowerCase()}${descriptor.slice(1, -1)}`
}
