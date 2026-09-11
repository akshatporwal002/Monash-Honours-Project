import type { AssessmentDefinition, AssessmentDraft } from './api'

export type AuthoringDefinition = Omit<AssessmentDefinition, 'criteria'> & {
  outcome_id: string
  criteria: (AssessmentDefinition['criteria'][number] & Pick<
    AssessmentDraft['criteria'][number], 'approved_anchors' | 'critical_error_rules'
  >)[]
}
export type CriterionDraft = AssessmentDraft['criteria'][number]
export type Rule = { criterion: string } | { operator: 'ALL_OF' | 'ANY_OF' | 'NOT', clauses: Rule[] }
export class DefinitionEditingError extends Error {}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

export function editableRule(value: unknown, ids: Map<string, string> = new Map(), depth = 1): Rule {
  if (!isRecord(value) || depth > 16) throw new DefinitionEditingError('The pass rule cannot be edited safely.')
  if (Object.keys(value).length === 1 && typeof value.criterion === 'string') {
    return { criterion: value.criterion }
  }
  if (Object.keys(value).length === 1 && typeof value.criterion_version_id === 'string') {
    const key = ids.get(value.criterion_version_id)
    if (!key) throw new DefinitionEditingError('The pass rule references a criterion missing from this version.')
    return { criterion: key }
  }
  if (Object.keys(value).length !== 2 || !['ALL_OF', 'ANY_OF', 'NOT'].includes(String(value.operator))
    || !Array.isArray(value.clauses) || !value.clauses.length
    || (value.operator === 'NOT' && value.clauses.length !== 1)) {
    throw new DefinitionEditingError('The pass rule needs valid Boolean operators and criterion references.')
  }
  return {
    operator: value.operator as 'ALL_OF' | 'ANY_OF' | 'NOT',
    clauses: value.clauses.map((clause) => editableRule(clause, ids, depth + 1)),
  }
}

export function ruleReferences(rule: Rule): string[] {
  return 'criterion' in rule ? [rule.criterion] : rule.clauses.flatMap(ruleReferences)
}

// Select writable fields explicitly; copy opaque supported metadata without interpreting it.
export function definitionToDraft(value: AuthoringDefinition): AssessmentDraft {
  if (!value.outcome_id || typeof value.formal_result_eligible !== 'boolean'
    || value.criteria.some((criterion) => criterion.approved_anchors === undefined
      || criterion.critical_error_rules === undefined)) {
    throw new DefinitionEditingError('This response lacks authoring metadata. Reload after the assessment service is updated.')
  }
  return structuredClone({
    claim: value.claim, purpose: value.purpose, bloom_process: value.bloom_process,
    knowledge_dimension: value.knowledge_dimension, supporting_evidence: value.supporting_evidence,
    contradicting_evidence: value.contradicting_evidence, insufficient_evidence: value.insufficient_evidence,
    task_conditions: value.task_conditions, next_action_contract: value.next_action_contract,
    permitted_tools: value.permitted_tools, instructional_support: value.instructional_support,
    access_conditions: value.access_conditions, transfer_rule: value.transfer_rule,
    evidence_sufficiency: value.evidence_sufficiency, formal_result_eligible: value.formal_result_eligible,
    criteria: value.criteria.map(({ stable_key, learner_description, evidence_description, mandatory,
      evidence_source_types, met_rule, not_met_rule, not_evaluable_rule, evaluator_type,
      approved_anchors, critical_error_rules }) => ({ stable_key, learner_description,
      evidence_description, mandatory, evidence_source_types, met_rule, not_met_rule,
      not_evaluable_rule, evaluator_type, approved_anchors, critical_error_rules })),
    pass_rule_expression: editableRule(value.pass_rule_expression,
      new Map(value.criteria.map((criterion) => [criterion.id, criterion.stable_key]))),
    task_forms: value.task_forms.map(({ learning_task_id, source_version, source_digest,
      task_family, context, constraints }) => ({ learning_task_id, source_version,
      source_digest, task_family, context, constraints })),
  })
}

export function validateDefinitionDraft(draft: AssessmentDraft): string[] {
  const faults: string[] = []
  if (!draft.claim.trim()) faults.push('Enter a claim.')
  if (!draft.criteria.length) faults.push('Add at least one criterion.')
  const keys = draft.criteria.map((criterion) => criterion.stable_key)
  if (new Set(keys).size !== keys.length) faults.push('Criterion keys must be unique.')
  for (const criterion of draft.criteria) {
    if ([criterion.stable_key, criterion.learner_description, criterion.evidence_description,
      criterion.met_rule, criterion.not_met_rule, criterion.not_evaluable_rule].some((text) => !text.trim())) {
      faults.push(`Complete the descriptions and evidence rules for ${criterion.stable_key}.`)
    }
    if (!criterion.evidence_source_types.length || criterion.evidence_source_types.some((type) => !type.trim())) {
      faults.push(`Choose evidence sources for ${criterion.stable_key}.`)
    }
  }
  try {
    const rule = editableRule(draft.pass_rule_expression)
    const references = ruleReferences(rule)
    const count = (node: Rule): number => 'criterion' in node ? 1 : 1 + node.clauses.reduce((sum, item) => sum + count(item), 0)
    if (count(rule) > 64) faults.push('The pass rule may contain at most 64 nodes.')
    if (references.some((key) => !keys.includes(key))) faults.push('The pass rule references a removed criterion.')
    if (draft.criteria.some((criterion) => criterion.mandatory && !references.includes(criterion.stable_key))) {
      faults.push('Include every mandatory criterion in the pass rule.')
    }
  } catch (error) { faults.push(error instanceof Error ? error.message : 'Check the pass rule.') }
  if (!draft.task_forms.length) faults.push('Add at least one task form.')
  for (const form of draft.task_forms) {
    if ([form.learning_task_id, form.source_version, form.source_digest, form.task_family].some((text) => !text.trim())) {
      faults.push('Complete the task form identity and source fields.')
    }
  }
  return faults
}

export function newCriterion(existing: CriterionDraft[], reservedKeys: string[] = []): CriterionDraft {
  let number = existing.length + 1
  const keys = new Set([...existing.map((criterion) => criterion.stable_key), ...reservedKeys])
  while (keys.has(`criterion_${number}`)) number += 1
  return { stable_key: `criterion_${number}`, learner_description: '', evidence_description: '',
    mandatory: false, evidence_source_types: ['learner_response'], met_rule: '', not_met_rule: '',
    not_evaluable_rule: '', evaluator_type: 'human', approved_anchors: {}, critical_error_rules: {} }
}
