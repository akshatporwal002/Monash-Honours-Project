import { Button, Field } from '../../components/ui'
import type { CriterionDraft, Rule } from './definitionEditing'
import styles from './assessment.module.css'

export function AssessorPassRule({ rule, criteria, onChange, path = 'Pass rule', depth = 1 }: {
  rule: Rule, criteria: CriterionDraft[], onChange: (rule: Rule) => void, path?: string, depth?: number,
}) {
  const firstKey = criteria[0]?.stable_key ?? ''
  return <fieldset className={styles.fieldset}>
    <legend>{path}</legend>
    <Field label={`${path} condition`}><select value={'criterion' in rule ? 'criterion' : rule.operator} onChange={(event) => {
      if (event.target.value === 'criterion') onChange({ criterion: firstKey })
      else {
        const operator = event.target.value as 'ALL_OF' | 'ANY_OF' | 'NOT'
        const clauses = 'criterion' in rule ? [rule] : rule.clauses
        onChange({ operator, clauses: operator === 'NOT' ? [clauses[0]] : clauses })
      }
    }}>
      <option value="criterion">Criterion is met</option>
      <option value="ALL_OF" disabled={depth >= 16}>All conditions</option>
      <option value="ANY_OF" disabled={depth >= 16}>Any condition</option>
      <option value="NOT" disabled={depth >= 16 || ('clauses' in rule && rule.clauses.length > 1)}>Condition is not met</option>
    </select></Field>
    {'criterion' in rule ? <Field label={`${path} criterion`}><select value={rule.criterion} onChange={(event) => onChange({ criterion: event.target.value })}>
      {!criteria.some((criterion) => criterion.stable_key === rule.criterion) && <option value={rule.criterion}>Missing: {rule.criterion}</option>}
      {criteria.map((criterion) => <option key={criterion.stable_key} value={criterion.stable_key}>{criterion.stable_key}: {criterion.learner_description || 'New criterion'}</option>)}
    </select></Field> : <>
      {rule.clauses.map((clause, index) => <div key={index}>
        <AssessorPassRule rule={clause} criteria={criteria} path={`${path} ${index + 1}`} depth={depth + 1}
          onChange={(value) => onChange({ ...rule, clauses: rule.clauses.map((item, at) => at === index ? value : item) })} />
        <Button variant="secondary" disabled={rule.clauses.length === 1} onClick={() => onChange({ ...rule, clauses: rule.clauses.filter((_, at) => at !== index) })}>Remove {path.toLowerCase()} condition {index + 1}</Button>
      </div>)}
      <Button variant="secondary" disabled={rule.operator === 'NOT' || !firstKey || depth >= 16} onClick={() => onChange({ ...rule, clauses: [...rule.clauses, { criterion: firstKey }] })}>Add condition to {path.toLowerCase()}</Button>
    </>}
  </fieldset>
}
