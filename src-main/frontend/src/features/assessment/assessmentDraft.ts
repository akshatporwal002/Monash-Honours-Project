import type { AssessmentDraft } from './api'

export interface SetupValues {
  courseId: string
  outcomeId: string
  outcome: string
  source: string
  sourceVersion: string
  sourceDigest: string
  bloomProcess: AssessmentDraft['bloom_process']
  knowledgeDimension: AssessmentDraft['knowledge_dimension']
  purpose: AssessmentDraft['purpose']
  claim: string
  evidence: string
  criterion: string
  taskId: string
  taskFamily: string
  tools: string
  support: string
  access: string
  transfer: string
  accessVerified: boolean
  bloomVerified: boolean
  approvalReason: string
}

export const initialSetupValues: Omit<SetupValues, 'courseId'> = {
  outcomeId: '', outcome: '', source: '', sourceVersion: '', sourceDigest: '',
  bloomProcess: 'APPLY', knowledgeDimension: 'PROCEDURAL', purpose: 'SUMMATIVE',
  claim: '', evidence: '', criterion: '', taskId: '', taskFamily: '', tools: '',
  support: '', access: '', transfer: '', accessVerified: false, bloomVerified: false,
  approvalReason: '',
}

function list(value: string): string[] {
  return value.split(',').map((item) => item.trim()).filter(Boolean)
}

export function missingSetupFields(values: SetupValues): string[] {
  const missing = [
    ['course', values.courseId], ['outcome ID', values.outcomeId], ['outcome wording', values.outcome],
    ['source', values.source], ['source version', values.sourceVersion], ['source digest', values.sourceDigest],
    ['claim', values.claim], ['required evidence', values.evidence], ['mandatory criterion', values.criterion],
    ['task ID', values.taskId], ['task family', values.taskFamily], ['permitted tools', values.tools],
    ['instructional support', values.support], ['access conditions', values.access], ['transfer rule', values.transfer],
  ].filter(([, value]) => !value.trim()).map(([name]) => name)
  if (!values.accessVerified) missing.push('access preservation verification')
  if (!values.bloomVerified) missing.push('Bloom elicitation verification')
  return missing
}

export function buildAssessmentDraft(values: SetupValues): AssessmentDraft {
  return {
    bloom_process: values.bloomProcess,
    knowledge_dimension: values.knowledgeDimension,
    purpose: values.purpose,
    claim: values.claim.trim(),
    supporting_evidence: { required: values.evidence.trim() },
    contradicting_evidence: { source: values.source.trim() },
    insufficient_evidence: { next_action: 'Return the attempt with the approved reassessment rule.' },
    task_conditions: { source: values.source.trim(), outcome: values.outcome.trim() },
    next_action_contract: { next_action: 'Explain the missing evidence and reassessment path.' },
    permitted_tools: { allowed: list(values.tools) },
    instructional_support: { allowed: list(values.support) },
    access_conditions: {
      modes: list(values.access).map((mode) => ({
        mode,
        preserves_construct: values.accessVerified,
      })),
    },
    transfer_rule: { rule: values.transfer.trim() },
    evidence_sufficiency: { required: values.evidence.trim() },
    formal_result_eligible: true,
    criteria: [{
      stable_key: 'required_evidence', learner_description: values.criterion.trim(),
      evidence_description: values.evidence.trim(), mandatory: true,
      evidence_source_types: ['learner_response'], met_rule: values.criterion.trim(),
      not_met_rule: 'The required evidence is absent or does not meet this criterion.',
      not_evaluable_rule: 'The evidence cannot be evaluated safely.', approved_anchors: {}, critical_error_rules: {},
    }],
    pass_rule_expression: {
      operator: 'ALL_OF',
      clauses: [{ criterion: 'required_evidence' }],
    },
    task_forms: [{
      learning_task_id: values.taskId.trim(), source_version: values.sourceVersion.trim(),
      source_digest: values.sourceDigest.trim(), task_family: values.taskFamily.trim(),
      context: { source: values.source.trim() },
      constraints: {
        access_modes: list(values.access),
        elicited_bloom_processes: values.bloomVerified ? [values.bloomProcess] : [],
      },
    }],
  }
}
