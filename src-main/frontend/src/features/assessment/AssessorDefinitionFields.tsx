import { useState } from 'react'
import { Button, Card, Checkbox, Field, Input, Textarea } from '../../components/ui'
import type { AssessmentDraft } from './api'
import { editableRule, isRecord, newCriterion, ruleReferences } from './definitionEditing'
import type { CriterionDraft } from './definitionEditing'
import { assessmentPurposeValues, bloomKnowledgeValues, bloomProcessValues } from './types'
import styles from './assessment.module.css'
import { AssessorPassRule } from './AssessorPassRule'

function StructuredField({ label, value, onChange, onValidity, arrayOnly = false, objectOnly = false }: {
  label: string, value: unknown, onChange: (value: never) => void,
  onValidity: (label: string, valid: boolean) => void, arrayOnly?: boolean, objectOnly?: boolean,
}) {
  const [text, setText] = useState(() => JSON.stringify(value, null, 2))
  const [invalid, setInvalid] = useState(false)
  return <Field label={label} error={invalid ? 'Enter valid JSON with the required structure.' : undefined} help="Structured policy data; retain any fields you are not changing.">
    <Textarea value={text} onChange={(event) => {
      setText(event.target.value)
      try {
        const parsed: unknown = JSON.parse(event.target.value)
        if ((!isRecord(parsed) && !Array.isArray(parsed)) || (arrayOnly && !Array.isArray(parsed))
          || (objectOnly && !isRecord(parsed))
          || (arrayOnly && (parsed as unknown[]).some((item) => typeof item !== 'string'))) throw new Error()
        onChange(parsed as never)
        setInvalid(false)
        onValidity(label, true)
      } catch { setInvalid(true); onValidity(label, false) }
    }} />
  </Field>
}

const policyFields = [
  ['supporting_evidence', 'Supporting evidence'], ['contradicting_evidence', 'Contradicting evidence'],
  ['insufficient_evidence', 'Insufficient evidence'], ['task_conditions', 'Task conditions'],
  ['next_action_contract', 'Next action and review policy'], ['permitted_tools', 'Permitted tools'],
  ['instructional_support', 'Instructional support'], ['access_conditions', 'Access conditions'],
  ['transfer_rule', 'Transfer rule'], ['evidence_sufficiency', 'Evidence sufficiency'],
] as const
const criterionTextFields = [
  ['learner_description', 'Learner description'], ['evidence_description', 'Evidence description'],
  ['met_rule', 'Met rule'], ['not_met_rule', 'Not met rule'], ['not_evaluable_rule', 'Not evaluable rule'],
] as const

export function AssessorDefinitionFields({ draft, onChange, onValidity, reservedCriterionKeys }: {
  draft: AssessmentDraft, onChange: (draft: AssessmentDraft) => void,
  onValidity: (label: string, valid: boolean) => void,
  reservedCriterionKeys: string[],
}) {
  const [allocatedKeys, setAllocatedKeys] = useState<string[]>([])
  const update = <Key extends keyof AssessmentDraft>(key: Key, value: AssessmentDraft[Key]) => onChange({ ...draft, [key]: value })
  const updateCriterion = (index: number, patch: Partial<CriterionDraft>) => update('criteria',
    draft.criteria.map((criterion, at) => at === index ? { ...criterion, ...patch } : criterion))
  let references: string[] | null = null
  try { references = ruleReferences(editableRule(draft.pass_rule_expression)) } catch { /* Invalid rules must be repaired before removing criteria. */ }
  return <>
    <Card heading="Assessment target">
      <Field label="Claim"><Textarea value={draft.claim} onChange={(event) => update('claim', event.target.value)} /></Field>
      <div className={styles.formGrid}>
        <Field label="Bloom process"><select value={draft.bloom_process} onChange={(event) => update('bloom_process', event.target.value as AssessmentDraft['bloom_process'])}>
          {bloomProcessValues.map((value) => <option key={value}>{value}</option>)}
        </select></Field>
        <Field label="Knowledge dimension"><select value={draft.knowledge_dimension} onChange={(event) => update('knowledge_dimension', event.target.value as AssessmentDraft['knowledge_dimension'])}>
          {bloomKnowledgeValues.map((value) => <option key={value}>{value}</option>)}
        </select></Field>
        <Field label="Assessment purpose"><select value={draft.purpose} onChange={(event) => update('purpose', event.target.value as AssessmentDraft['purpose'])}>
          {assessmentPurposeValues.map((value) => <option key={value}>{value}</option>)}
        </select></Field>
      </div>
      <Checkbox label="Eligible for a formal result" checked={draft.formal_result_eligible} onChange={(event) => update('formal_result_eligible', event.target.checked)} />
    </Card>
    <Card heading="Criteria and pass rule">
      <p>Stable criterion keys retain their identity across versions. Mandatory criteria must appear in the pass rule.</p>
      {draft.criteria.map((criterion, index) => <fieldset key={criterion.stable_key} className={styles.fieldset}>
        <legend>Criterion {index + 1}: {criterion.stable_key}</legend>
        {criterionTextFields.map(([key, label]) => <Field key={key} label={`${label} — ${criterion.stable_key}`}>
          <Textarea value={criterion[key]} onChange={(event) => updateCriterion(index, { [key]: event.target.value })} />
        </Field>)}
        <Checkbox label={`Mandatory — ${criterion.stable_key}`} checked={criterion.mandatory} onChange={(event) => updateCriterion(index, { mandatory: event.target.checked })} />
        <Field label={`Evaluator — ${criterion.stable_key}`}><select value={criterion.evaluator_type} onChange={(event) => updateCriterion(index, { evaluator_type: event.target.value as CriterionDraft['evaluator_type'] })}>
          {['human', 'rules', 'validated_ai', 'mixed'].map((type) => <option key={type}>{type}</option>)}
        </select></Field>
        <details><summary>Evidence sources, anchors and critical errors — {criterion.stable_key}</summary>
          <StructuredField label={`Evidence sources — ${criterion.stable_key}`} value={criterion.evidence_source_types} arrayOnly onValidity={onValidity} onChange={(value) => updateCriterion(index, { evidence_source_types: value })} />
          <StructuredField label={`Approved anchors — ${criterion.stable_key}`} value={criterion.approved_anchors} onValidity={onValidity} onChange={(value) => updateCriterion(index, { approved_anchors: value })} />
          <StructuredField label={`Critical error rules — ${criterion.stable_key}`} value={criterion.critical_error_rules} onValidity={onValidity} onChange={(value) => updateCriterion(index, { critical_error_rules: value })} />
        </details>
        <Button variant="secondary" disabled={references === null || references.includes(criterion.stable_key)} onClick={() => {
          for (const prefix of ['Evidence sources', 'Approved anchors', 'Critical error rules']) onValidity(`${prefix} — ${criterion.stable_key}`, true)
          update('criteria', draft.criteria.filter((_, at) => at !== index))
        }}>Remove criterion {criterion.stable_key}</Button>
        {references?.includes(criterion.stable_key) && <p>Remove {criterion.stable_key} from the pass rule before deleting it.</p>}
      </fieldset>)}
      <Button variant="secondary" onClick={() => {
        const criterion = newCriterion(draft.criteria, [...reservedCriterionKeys, ...allocatedKeys])
        setAllocatedKeys((keys) => [...keys, criterion.stable_key])
        update('criteria', [...draft.criteria, criterion])
      }}>Add criterion</Button>
      <p>All mandatory criteria must be met in addition to the conditions below. Changing a group to a single criterion replaces its conditions.</p>
      <AssessorPassRule rule={editableRule(draft.pass_rule_expression)} criteria={draft.criteria} onChange={(rule) => update('pass_rule_expression', rule)} />
    </Card>
    <Card heading="Policies and task forms">
      <p>Review access preservation, Bloom elicitation, tool limits and transfer conditions before approving a new version.</p>
      {policyFields.map(([key, label]) => <details key={key}><summary>{label}</summary>
        <StructuredField label={`${label} policy`} value={draft[key]} onValidity={onValidity} onChange={(value) => update(key, value)} />
      </details>)}
      <p>Saving uses the task's current teaching revision and refreshes its source digest. Published versions retain their frozen task forms.</p>
      {draft.task_forms.map((form, index) => <fieldset key={index} className={styles.fieldset}>
        <legend>Task form {index + 1}</legend>
        {(['learning_task_id', 'source_version', 'source_digest', 'task_family'] as const).map((key) => <Field key={key} label={`${key.replaceAll('_', ' ')} — form ${index + 1}`}>
          <Input value={form[key]} readOnly={key !== 'task_family'} onChange={(event) => update('task_forms', draft.task_forms.map((item, at) => at === index ? { ...item, [key]: event.target.value } : item))} />
        </Field>)}
        {(['context', 'constraints'] as const).map((key) => <StructuredField key={key} label={`${key} — form ${index + 1}`} value={form[key]} onValidity={onValidity} onChange={(value) => update('task_forms', draft.task_forms.map((item, at) => at === index ? { ...item, [key]: value } : item))} />)}
      </fieldset>)}
    </Card>
  </>
}
