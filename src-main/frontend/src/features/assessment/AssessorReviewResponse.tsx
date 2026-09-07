import type { ApiSchemas } from '../../api/generated'
import { CodeBlock } from '../../components/ui'
import styles from './assessment.module.css'

type FrozenResponse = ApiSchemas['FrozenResponseRead']
type Content = ApiSchemas['ResponseContent']
type Stage = ApiSchemas['EpisodeStageResponseV1']

function ResponseContent({ content }: { content: Content }) {
  return <>
    {content.answer && <p style={{ whiteSpace: 'pre-wrap' }}>{content.answer}</p>}
    {content.code != null && <CodeBlock code={content.code} label="Submitted code" />}
    {content.circuit != null && <CodeBlock code={JSON.stringify(content.circuit, null, 2)} label="Submitted circuit data" />}
    {!content.answer && content.code == null && content.circuit == null && <p>No response content was recorded.</p>}
  </>
}

function ResponseProcess({ stage }: { stage: Stage }) {
  return <>
    <h4>Original prediction</h4>
    {stage.prediction ? <ResponseContent content={stage.prediction} /> : <p>No prediction recorded.</p>}
    {stage.prediction_checkpoint_id && <p>Prediction checkpoint: {stage.prediction_checkpoint_id}</p>}
    <h4>Reasoning</h4><p style={{ whiteSpace: 'pre-wrap' }}>{stage.reasoning || 'No reasoning recorded.'}</p>
    <h4>Explanation</h4><p style={{ whiteSpace: 'pre-wrap' }}>{stage.explanation || 'No explanation recorded.'}</p>
    <h4>Revision</h4>
    {stage.revision ? <p>{stage.revision.reason} Earlier response: {stage.revision.previous_response_version_id}</p> : <p>No revision recorded.</p>}
    <h4>Reflection</h4><p style={{ whiteSpace: 'pre-wrap' }}>{stage.reflection || 'No reflection recorded.'}</p>
  </>
}

function FrozenContent({ response }: { response: FrozenResponse }) {
  return <section className={styles.section}>
    <p>Immutable response: {response.reference.evidence_id}</p>
    <details><summary>Declared response conditions</summary><CodeBlock code={JSON.stringify(response.declared_conditions, null, 2)} label="Exact declared response conditions" /></details>
    <h3>Supported response</h3>
    <ResponseContent content={response.content} />
    {response.episode && <ResponseProcess stage={response.episode.supported} />}
    {response.episode && <>
      <h3>Unaided transfer response</h3>
      {response.episode.transfer ? <>
        <p>Part: {response.episode.transfer.part_id}. Stage entry: {response.episode.transfer.stage_start_id}.</p>
        <ResponseContent content={response.episode.transfer.content} />
        <ResponseProcess stage={response.episode.transfer.process} />
      </> : <p>No separate transfer response was recorded.</p>}
    </>}
  </section>
}

export function AssessorReviewResponse({ response, history = [], simulations = [], issues = [], fallbackText }: {
  response?: FrozenResponse | null
  history?: FrozenResponse[]
  simulations?: Record<string, unknown>[]
  issues?: string[]
  fallbackText?: string
}) {
  return <>
    {issues.map((issue) => <p key={issue} className={styles.alert} role="alert">{issue}</p>)}
    {response ? <FrozenContent response={response} /> : <p>{fallbackText || 'Frozen response is unavailable. Keep this work under review.'}</p>}
    {history.length > 0 && <section aria-label="Earlier immutable responses">
      <h3>Earlier responses</h3>
      {history.map((earlier) => <details key={earlier.reference.evidence_id}>
        <summary>Inspect earlier response {earlier.reference.evidence_id}</summary>
        <FrozenContent response={earlier} />
      </details>)}
    </section>}
    {simulations.length > 0 && <section aria-label="Recorded simulation evidence">
      <h3>Recorded simulations</h3>
      {simulations.map((run, index) => <details key={String(run.run_id ?? index)} open>
        <summary>Simulation {String(run.run_id)}: {String(run.status)}</summary>
        <p>Shots: {String(run.shots)}. Seed: {String(run.seed)}.</p>
        <CodeBlock code={JSON.stringify(run, null, 2)} label="Exact simulation inputs, versions, and outcome" />
      </details>)}
    </section>}
  </>
}
