import type { ApiSchemas } from '../api/generated'
import { Button, Card } from './ui'

export function PreferenceWorkspace({ effective, disabled, onBreak, onRepeat }: {
  effective: ApiSchemas['EffectivePreferences']; disabled: boolean
  onBreak: () => void; onRepeat: () => void
}) {
  const values = effective.values
  const guidance = values.explanation_detail === 'detailed'
    ? ['Read the approved task and its response conditions.', 'Record your own response. Use only the tools and support allowed for this stage.', 'Review your response and the available feedback. Keep required reflection in your own words.']
    : ['Read the task.', 'Record your response.', 'Review your work.']
  return <Card heading="Workspace preferences">
    {effective.limitations.map(message => <p key={message}>{message}</p>)}
    {!effective.transfer && <>
      {values.pace === 'stepwise' && <nav aria-label="Stepwise workspace guide"><a href="#task-title">1. Read task</a>{' | '}<a href="#task-response">2. Write response</a>{' | '}<a href="#task-records">3. Review saved work</a></nav>}
      <section aria-label="Optional workspace guidance">{values.format === 'stepwise' ? <ol>{guidance.map(line => <li key={line}>{line}</li>)}</ol> : <p>{guidance.join(' ')}</p>}</section>
    </>}
    {values.breaks && <><p>A break saves your draft. It does not pause deadlines or change task conditions.</p><Button disabled={disabled} onClick={onBreak}>Save draft and take a break</Button></>}
    {values.repeat_practice && effective.repeat_allowed && !effective.transfer && <><p>Repeat practice starts a new local draft for this permitted practice task. Earlier responses stay saved.</p><Button disabled={disabled} onClick={onRepeat}>Start another practice draft</Button></>}
  </Card>
}
