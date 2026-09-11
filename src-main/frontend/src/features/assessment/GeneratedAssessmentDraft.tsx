import { useState } from 'react'
import { ApiError, api } from '../../app/api'
import type { ApiSchemas } from '../../api/generated'
import { Button } from '../../components/ui'

export function GeneratedAssessmentDraft({ courseId, taskId, revisionId }: { courseId: string; taskId: string; revisionId: string }) {
  const [draft, setDraft] = useState<ApiSchemas['AssessmentDefinitionDraftCreate'] | null>(null)
  const [saved, setSaved] = useState<ApiSchemas['AssessmentDefinitionRead'] | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const act = async (save: boolean) => {
    setBusy(true); setError('')
    try {
      if (save) setSaved(await api.assessment.saveGeneratedDraft(courseId, taskId, revisionId))
      else setDraft(await api.assessment.generatedDraft(courseId, taskId, revisionId))
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'The generated design could not be loaded or saved. Reload the reviewed task and try again.')
      setDraft(null)
    } finally { setBusy(false) }
  }
  return <section aria-label="Generated assessment design">
    <Button variant="secondary" disabled={busy || Boolean(saved)} onClick={() => void act(false)}>Preview generated assessment design</Button>
    {error && <p role="alert">{error}</p>}
    {draft && <>
      <h3>Proposed assessment design</h3>
      <p>{draft.claim}</p>
      <p>{draft.purpose} · {draft.bloom_process} · {draft.knowledge_dimension}</p>
      <p>All {draft.criteria.length} criteria are required. An assessor reviews the proposed anchors, source alignment, access conditions and Bloom target before any formal use.</p>
      <ol>{draft.criteria.map(criterion => <li key={criterion.stable_key}>
        <strong>{criterion.learner_description}</strong>
        <p>Meets criterion: {criterion.met_rule}</p><p>Does not meet criterion: {criterion.not_met_rule}</p>
        <details><summary>Proposed anchors and evidence requirements</summary>
          <p>{criterion.evidence_description}</p><p>Cannot evaluate: {criterion.not_evaluable_rule}</p>
          <ul>{Object.entries(criterion.approved_anchors).flatMap(([name, entries]) => Array.isArray(entries)
            ? entries.filter((value): value is string => typeof value === 'string').map((value, index) => <li key={`${name}-${index}`}>{name === 'met' ? 'Meets criterion' : 'Does not meet criterion'}: {value}</li>) : [])}</ul>
        </details>
      </li>)}</ol>
      <p>Saving creates an unapproved version in assessment history. Formal eligibility and access/Bloom verification remain unset. An existing definition for this outcome must be revised through its current authoring workflow.</p>
      <Button disabled={busy || Boolean(saved)} onClick={() => void act(true)}>Save generated assessment draft</Button>
    </>}
    {saved && <p role="status">Assessment draft version {saved.version} saved. It has not been approved.</p>}
  </section>
}
