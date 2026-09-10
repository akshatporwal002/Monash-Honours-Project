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
    {Boolean(response.recorded_teaching?.length) && <section aria-label="Recorded instructional help">
      <h3>Recorded instructional help</h3>
      {response.recorded_teaching?.map(item => <div key={item.evidence_id}>
        <p>Instructional support level {item.instructional_support_level}{item.during_transfer ? ', after the fresh stage began' : ''}. Recorded {new Date(item.occurred_at).toLocaleString()}.</p>
        <p style={{ whiteSpace: 'pre-wrap' }}>{item.explanation}</p>
        <p>Evidence: {item.evidence_id}</p>
      </div>)}
    </section>}
    <h3>Supported response</h3>
    <ResponseContent content={response.content} />
    {response.episode && <ResponseProcess stage={response.episode.supported} />}
    {response.episode && <>
      <h3>Fresh transfer response</h3>
      {response.episode.transfer ? <>
        <p>Part: {response.episode.transfer.part_id}. Stage entry: {response.episode.transfer.stage_start_id}.</p>
        <ResponseContent content={response.episode.transfer.content} />
        <ResponseProcess stage={response.episode.transfer.process} />
      </> : <p>No separate transfer response was recorded.</p>}
    </>}
  </section>
}

export function AssessorReviewResponse({ response, history = [], historicalEvidence = [], frozenContext, simulations = [], issues = [], fallbackText }: {
  response?: FrozenResponse | null
  history?: FrozenResponse[]
  historicalEvidence?: ApiSchemas['HistoricalResponseEvidenceRead'][]
  frozenContext?: ApiSchemas['FrozenAssessmentContextRead'] | null
  simulations?: Record<string, unknown>[]
  issues?: string[]
  fallbackText?: string
}) {
  return <>
    {issues.map((issue) => <p key={issue} className={styles.alert} role="alert">{issue}</p>)}
    {frozenContext && <section aria-label="Frozen assessment question and standard" className={styles.section}>
      <h3>Frozen question and standard</h3>
      <h4>{frozenContext.task_title}</h4>
      <p style={{ whiteSpace: 'pre-wrap' }}>{frozenContext.supported_prompt}</p>
      <p style={{ whiteSpace: 'pre-wrap' }}>{frozenContext.supported_instructions}</p>
      {frozenContext.starter_code != null && <CodeBlock code={frozenContext.starter_code} label="Frozen supported starter code" />}
      {frozenContext.starter_circuit != null && <CodeBlock code={JSON.stringify(frozenContext.starter_circuit, null, 2)} label="Frozen supported starter circuit" />}
      {frozenContext.transfer_prompt != null && <>
        <h4>Fresh transfer question</h4>
        <p style={{ whiteSpace: 'pre-wrap' }}>{frozenContext.transfer_prompt}</p>
        <p style={{ whiteSpace: 'pre-wrap' }}>{frozenContext.transfer_instructions}</p>
        {frozenContext.transfer_starter_code != null && <CodeBlock code={frozenContext.transfer_starter_code} label="Frozen transfer starter code" />}
        {frozenContext.transfer_starter_circuit != null && <CodeBlock code={JSON.stringify(frozenContext.transfer_starter_circuit, null, 2)} label="Frozen transfer starter circuit" />}
      </>}
      <h4>Approved learning outcome</h4>
      <p>{frozenContext.outcome_title}</p><p>{frozenContext.outcome_statement}</p>
      <p>Bloom process: {frozenContext.bloom_process}. Knowledge dimension: {frozenContext.knowledge_dimension}.</p>
      <details><summary>Exact frozen pass rule</summary><CodeBlock code={JSON.stringify(frozenContext.pass_rule_expression, null, 2)} label="Frozen pass rule expression" /></details>
      <p>Reviewed task revision: {frozenContext.task_revision_id}</p>
    </section>}
    {response ? <FrozenContent response={response} /> : <p>{fallbackText || 'Frozen response is unavailable. Keep this work under review.'}</p>}
    {!historicalEvidence.length && history.length > 0 && <section aria-label="Earlier immutable responses">
      <h3>Earlier responses</h3>
      {history.map((earlier) => <details key={earlier.reference.evidence_id}>
        <summary>Inspect earlier response {earlier.reference.evidence_id}</summary>
        <FrozenContent response={earlier} />
      </details>)}
    </section>}
    {historicalEvidence.length > 0 && <section aria-label="Earlier immutable responses">
      <h3>Earlier responses</h3>
      {historicalEvidence.map((earlier) => <details key={earlier.response_version_id}>
        <summary>Inspect earlier response {earlier.response_version_id}</summary>
        <AssessorReviewResponse response={earlier.response} simulations={earlier.simulations} issues={earlier.issues} />
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
