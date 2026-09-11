import { StructuredTask, type StructuredDefinition } from './StructuredTask'
import { Button, Field, Input, Textarea } from './ui'

type Item = { id: string; text: string; source_references: string[] }
export function StructuredTaskEditor({ type, value, answer, disabled, onChange, onAnswer }: {
  type: 'matching' | 'sequencing'; value: Record<string, unknown>; answer: string; disabled: boolean
  onChange: (value: Record<string, unknown>) => void; onAnswer: (answer: string) => void
}) {
  const definition = (value.structured_task ?? { task_type: type, schema_version: `learnlens.${type}.v1`, ...(type === 'matching' ? { prompts: [], options: [] } : { items: [] }) }) as StructuredDefinition
  const groups = type === 'matching' ? ['prompts', 'options'] as const : ['items'] as const
  const set = (group: string, items: Item[]) => onChange({ ...value, response_review: 'human', structured_task: { ...definition, [group]: items } })
  return <fieldset disabled={disabled}><legend>{type === 'matching' ? 'Matching definition' : 'Sequencing definition'}</legend>
    <p>Each item must cite a source passage declared on this task. Save and review changes before approval.</p>
    {groups.map(group => {
      const items: Item[] = (definition as unknown as Record<string, Item[]>)[group] ?? []
      return <fieldset key={group}><legend>{group}</legend>{items.map((item, index) => {
        const update = (change: Partial<Item>) => set(group, items.map((row, i) => i === index ? { ...row, ...change } : row))
        return <div key={index}>
          <Field label={`${group} ${index + 1} ID`}><Input value={item.id} onChange={event => update({ id: event.target.value })} /></Field>
          <Field label={`${group} ${index + 1} text`}><Textarea value={item.text} onChange={event => update({ text: event.target.value })} /></Field>
          <Field label={`${group} ${index + 1} source passages`} help="One declared passage ID per line."><Textarea value={item.source_references.join('\n')} onChange={event => update({ source_references: event.target.value.split('\n').filter(Boolean) })} /></Field>
          <Button onClick={() => set(group, items.filter((_, i) => i !== index))}>Remove {group} {index + 1}</Button>
        </div>
      })}<Button disabled={disabled || items.length >= 20} onClick={() => set(group, [...items, { id: `${group}-${items.length + 1}`, text: '', source_references: [] }])}>Add {group} item</Button></fieldset>
    })}
    <h4>Private answer key</h4><StructuredTask definition={definition} answer={answer} onChange={onAnswer} />
  </fieldset>
}
