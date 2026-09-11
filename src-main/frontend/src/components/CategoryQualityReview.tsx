import { useEffect, useState } from 'react'
import { request } from '../app/api'
import { Field, Textarea } from './ui'
import { qualityDimensions } from './categoryQualityReviewTypes'
import type { Finding, QualitySubmission } from './categoryQualityReviewTypes'
type Context = {
  required: boolean, request_digest: string,
  request: { evidence: { reference: string, content: unknown }[], versions: Record<string, string> }
}

export function CategoryQualityReview({ taskId, revisionId, reviewVersion, disabled, onChange }: {
  taskId: string, revisionId: string, reviewVersion: number, disabled: boolean,
  onChange: (value: QualitySubmission | null, approvalReady: boolean) => void,
}) {
  const [context, setContext] = useState<Context | null>(null)
  const [findings, setFindings] = useState<Finding[]>([])
  const [error, setError] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    void request<Context>(`/tasks/${encodeURIComponent(taskId)}/review/quality`, { signal: controller.signal }).then(value => {
      if (controller.signal.aborted) return
      setContext(value)
      setFindings(qualityDimensions.map(([dimension]) => ({ dimension, outcome: 'UNVERIFIED', basis: 'human', reason: '', evidence_references: [] })))
      if (!value.required) onChange(null, true)
    }).catch(() => {
      if (!controller.signal.aborted) setError('The saved quality review context is unavailable. Reload the task review before approving.')
    })
    return () => controller.abort()
  }, [taskId, revisionId, reviewVersion, onChange])
  const update = (index: number, patch: Partial<Finding>) => {
    const next = findings.map((finding, at) => at === index ? { ...finding, ...patch } : finding)
    setFindings(next)
    const complete = next.every(finding => finding.reason.trim() && (finding.outcome !== 'SATISFIED' || finding.evidence_references.length))
    onChange(context && complete ? { request_digest: context.request_digest, findings: next } : null,
      complete && next.every(finding => finding.outcome === 'SATISFIED' || finding.outcome === 'NOT_APPLICABLE'))
  }
  if (error) return <p role="alert">{error}</p>
  if (!context) return <p role="status">Loading saved quality review context...</p>
  if (!context.required) return null
  return <fieldset disabled={disabled}>
    <legend>Generated content quality review</legend>
    <p>Inspect the saved task and approved sources for every dimension. Structural validity does not establish factual accuracy. Explain any dimension that does not apply. Unverified or unmet dimensions block approval.</p>
    <details><summary>Approved source and task context</summary>
      {context.request.evidence.map(evidence => <article key={evidence.reference}><h4>{evidence.reference}</h4><pre>{JSON.stringify(evidence.content, null, 2)}</pre></article>)}
    </details>
    {findings.map((finding, index) => <fieldset key={finding.dimension}>
      <legend>{qualityDimensions[index][1]}</legend>
      <Field label={`${qualityDimensions[index][1]} finding`}><select value={finding.outcome} onChange={event => update(index, { outcome: event.target.value as Finding['outcome'] })}>
        <option value="UNVERIFIED">Not yet verified</option><option value="SATISFIED">Satisfied</option><option value="VIOLATED">Needs correction</option><option value="NOT_APPLICABLE">Does not apply</option>
      </select></Field>
      <Field label={`${qualityDimensions[index][1]} reason`}><Textarea maxLength={2000} value={finding.reason} onChange={event => update(index, { reason: event.target.value })} /></Field>
      <Field label={`${qualityDimensions[index][1]} evidence`}><select multiple value={finding.evidence_references} onChange={event => update(index, { evidence_references: Array.from(event.target.selectedOptions, option => option.value) })}>
        {context.request.evidence.map(evidence => <option key={evidence.reference} value={evidence.reference}>{evidence.reference}</option>)}
      </select></Field>
    </fieldset>)}
  </fieldset>
}
