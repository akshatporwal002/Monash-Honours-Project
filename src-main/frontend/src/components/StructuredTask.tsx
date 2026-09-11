import { useId } from 'react'
import { Button } from './ui'

import { parsed, pairsOf, orderOf, type StructuredDefinition } from '../app/structuredTasks'
export type { StructuredDefinition } from '../app/structuredTasks'

export function StructuredTask({ definition, answer, onChange }: { definition: StructuredDefinition; answer: string; onChange: (answer: string) => void }) {
  const id = useId()
  if (definition.task_type === 'matching') {
    const pairs = pairsOf(answer)
    return <fieldset><legend>Match each prompt to one option</legend><p>Use each option once. All choices can be made with the keyboard.</p>
      {definition.prompts.map((item, index) => <div key={item.id}>
        <label htmlFor={`${id}-${index}`}>{item.text}</label>
        <select id={`${id}-${index}`} value={pairs[item.id] ?? ''} onChange={event => {
          const next = { ...pairs }; if (event.target.value) next[item.id] = event.target.value; else delete next[item.id]
          onChange(JSON.stringify({ schema_version: 'learnlens.matching-response.v1', pairs: next, labels: Object.fromEntries([...definition.prompts.map(item => [`prompt:${item.id}`, item.text]), ...definition.options.map(item => [`option:${item.id}`, item.text])]) }))
        }}><option value="">Choose a match</option>{definition.options.map(option => <option key={option.id} value={option.id} disabled={Object.entries(pairs).some(([key, value]) => key !== item.id && value === option.id)}>{option.text}</option>)}</select>
      </div>)}
    </fieldset>
  }
  const saved = orderOf(answer)
  const order = [...saved.filter(key => definition.items.some(item => item.id === key)), ...definition.items.map(item => item.id).filter(key => !saved.includes(key))]
  const write = (next: string[]) => onChange(JSON.stringify({ schema_version: 'learnlens.sequencing-response.v1', order: next, labels: Object.fromEntries(definition.items.map(item => [`item:${item.id}`, item.text])) }))
  const move = (index: number, direction: number) => {
    const next = [...order]; [next[index], next[index + direction]] = [next[index + direction], next[index]]; write(next)
  }
  return <fieldset><legend>Put the items in order</legend><p>Move items using the buttons, then confirm your order.</p><ol aria-label="Current sequence">{order.map((key, index) => <li key={key}>
    <span>{definition.items.find(item => item.id === key)?.text}</span>
    <Button aria-label={`Move ${key} earlier`} disabled={index === 0} onClick={() => move(index, -1)}>Move earlier</Button>
    <Button aria-label={`Move ${key} later`} disabled={index === order.length - 1} onClick={() => move(index, 1)}>Move later</Button>
  </li>)}</ol><Button onClick={() => write(order)}>Confirm this order</Button><p role="status">{saved.length ? `Saved in this draft: ${saved.join(', ')}` : 'Order not confirmed yet.'}</p></fieldset>
}

export function StructuredSnapshot({ answer }: { answer: string }) {
  const value = parsed(answer)
  const labels = value.labels && typeof value.labels === 'object' ? value.labels as Record<string, string> : {}
  if (value.schema_version === 'learnlens.matching-response.v1') return <table><caption>Saved matching evidence</caption><thead><tr><th>Prompt</th><th>Matched option</th></tr></thead><tbody>{Object.entries(pairsOf(answer)).map(([prompt, option]) => <tr key={prompt}><th>{labels[`prompt:${prompt}`] ?? prompt}</th><td>{labels[`option:${option}`] ?? option}</td></tr>)}</tbody></table>
  if (value.schema_version === 'learnlens.sequencing-response.v1') return <div><p>Saved sequence</p><ol>{orderOf(answer).map(item => <li key={item}>{labels[`item:${item}`] ?? item}</li>)}</ol></div>
  return <pre style={{ whiteSpace: 'pre-wrap' }}>{answer}</pre>
}
