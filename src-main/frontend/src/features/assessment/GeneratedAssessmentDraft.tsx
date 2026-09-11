import { useEffect, useRef, useState } from 'react'
import { ApiError, api } from '../../app/api'
import type { ApiSchemas } from '../../api/generated'
import { Button } from '../../components/ui'

export function GeneratedAssessmentDraft({ courseId, taskId, revisionId, onSaved }: { courseId: string; taskId: string; revisionId: string; onSaved?: (definition: ApiSchemas['AssessmentDefinitionRead']) => void }) {
  const [draft, setDraft] = useState<ApiSchemas['AssessmentDefinitionDraftCreate'] | null>(null)
  const [saved, setSaved] = useState<ApiSchemas['AssessmentDefinitionRead'] | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const requestEpoch = useRef(0)
  useEffect(() => () => { requestEpoch.current += 1 }, [courseId, taskId, revisionId])
  const act = async (save: boolean) => {
    const epoch = ++requestEpoch.current
    setBusy(true); setError('')
    try {
      if (save) {
        const definition = await api.assessment.saveGeneratedDraft(courseId, taskId, revisionId)
        if (requestEpoch.current !== epoch) return
        setSaved(definition)
        onSaved?.(definition)
      }
      else {
        const proposal = await api.assessment.generatedDraft(courseId, taskId, revisionId)
        if (requestEpoch.current !== epoch) return
        setDraft(proposal)
      }
    } catch (caught) {
      if (requestEpoch.current !== epoch) return
      setError(caught instanceof ApiError ? caught.message : 'The generated design could not be loaded or saved. Reload the reviewed task and try again.')
      setDraft(null)
    } finally { if (requestEpoch.current === epoch) setBusy(false) }
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
