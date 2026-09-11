import { useEffect, useRef, useState } from 'react'
import { request } from '../../app/api'
import { Button, CodeBlock } from '../../components/ui'

type Suggestion = { id: string; recorded_by: number; output: { output_reference: string; provider: string; model: string; generated_at: string; criteria: { criterion_version_id: string; decision: string; reason: string; evidence_ids: string[] }[] } }
type Read = { status: string; reason: string; records: Suggestion[]; release_expires_at?: string }
type QualityContext = { request_digest: string; reviewer: { kind: string; reference: string; version: string }; request: { output: unknown; evidence: { reference: string; content: unknown }[] } }
type Finding = { outcome: string; reason: string; evidence_references: string[] }
const dimensions = {
  factual_accuracy: 'Factual accuracy', grounding_and_source_use: 'Grounding and source use', relevance: 'Relevance',
  outcome_and_bloom_alignment: 'Outcome and Bloom alignment', evidence_rule_alignment: 'Evidence-rule alignment',
  support_and_answer_leakage: 'Suitable support and answer leakage', clarity_and_next_steps: 'Clear language and useful next steps',
  accessibility_and_inclusive_wording: 'Accessibility and inclusive wording', bias_and_unsupported_learner_claims: 'Bias and unsupported learner claims',
  reflection_and_independent_work: 'Reflection and independent work',
}

export function AssessorSuggestionPanel({ attemptId, independent }: { attemptId: string; independent: boolean }) {
  const [open, setOpen] = useState(false)
  if (independent) return <p>AI suggestions are not displayed during independent moderation.</p>
  return <section aria-label="Advisory criterion suggestions">
    <Button variant="secondary" onClick={() => setOpen(value => !value)}>{open ? 'Close' : 'Open'} AI suggestion records</Button>
    {open && <SuggestionRecords key={attemptId} attemptId={attemptId} />}
  </section>
}

function SuggestionRecords({ attemptId }: { attemptId: string }) {
  const [reload, setReload] = useState(0)
  const [data, setData] = useState<Read | null>(null)
  const [file, setFile] = useState<Record<string, unknown> | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [quality, setQuality] = useState<QualityContext | null>(null)
  const [findings, setFindings] = useState<Record<string, Finding>>({})
  const [message, setMessage] = useState('')
  const active = useRef(true)
  const generation = useRef(0)
  const base = `/assessment/attempts/${encodeURIComponent(attemptId)}/ai-suggestions`
  useEffect(() => {
    active.current = true
    let alive = true
    const controller = new AbortController()
    void request<Read>(base, { signal: controller.signal }).then(value => { if (alive) { setData(value); setError('') } }).catch(() => { if (alive) { setData(null); setError('Suggestion records are unavailable. Check access and current release.') } })
    return () => { alive = false; active.current = false; generation.current += 1; controller.abort() }
  }, [base, reload])
  useEffect(() => {
    if (!data?.release_expires_at) return
    const expires = new Date(data.release_expires_at).getTime()
    const timer = window.setInterval(() => {
      if (Date.now() >= expires) { setData(null); setFile(null); setError('The suggestion release expired. Reload to check its current status.') }
    }, 1000)
    return () => window.clearInterval(timer)
  }, [data?.release_expires_at])
  async function selectFile(selected: File | undefined) {
    const current = ++generation.current
    setFile(null); setQuality(null); setFindings({}); setError(''); setMessage('')
    if (!selected) return
    try {
      const value: unknown = JSON.parse(await selected.text())
      if (typeof value !== 'object' || value === null || Array.isArray(value)) throw new Error()
      if (active.current && current === generation.current) setFile(value as Record<string, unknown>)
    } catch { if (active.current && current === generation.current) setError('Choose a readable recorded-output file.') }
  }
  async function prepareReview() {
    if (!file) return
    const current = ++generation.current
    setBusy(true); setError(''); setQuality(null)
    try {
      const next = await request<QualityContext>(`${base}/quality-context`, { method: 'POST', body: JSON.stringify({ ...file, quality_review: null }) })
      if (active.current && current === generation.current) { setQuality(next); setFindings({}) }
    } catch (caught) {
      if (active.current && current === generation.current) { setData(null); setError(caught instanceof Error ? caught.message : 'The quality review context is unavailable.') }
    } finally { if (active.current && current === generation.current) setBusy(false) }
  }
  async function importFile() {
    if (!file || !quality) return
    const current = ++generation.current
    setBusy(true); setError('')
    try {
      const receipt = await request<{ quality_decision: string }>(base, { method: 'POST', body: JSON.stringify({ ...file, quality_review: {
        request_digest: quality.request_digest, reviewer: quality.reviewer,
        findings: Object.keys(dimensions).map(dimension => ({ dimension, basis: 'human', ...findings[dimension] })),
      } }) })
      const next = await request<Read>(base)
      if (active.current && current === generation.current) { setData(next); setFile(null); setQuality(null); setMessage(`Quality review: ${receipt.quality_decision}. Record retained; only approved suggestions are displayed. Human assessment decisions remain separate.`) }
    } catch (caught) {
      if (active.current && current === generation.current) { setData(null); setQuality(null); setError(caught instanceof Error ? caught.message : 'Output import failed.') }
    } finally { if (active.current && current === generation.current) setBusy(false) }
  }
  return <div>
    <p>Suggestions are retained model outputs, not assessor decisions. Inspect the original evidence and enter your own decisions below.</p>
    <Button variant="secondary" disabled={busy} onClick={() => { setData(null); setFile(null); setQuality(null); setReload(value => value + 1) }}>Reload suggestion records</Button>
    {error && <p role="alert">{error}</p>}
    {message && <p role="status">{message}</p>}
    {data && <p role="status">{data.status}: {data.reason}</p>}
    {data?.status === 'RELEASED' && <>
      <label>Recorded AI output<input type="file" accept="application/json,.json" disabled={busy} onChange={event => void selectFile(event.target.files?.[0])} /></label>
      <Button disabled={busy || !file} onClick={() => void prepareReview()}>Prepare output quality review</Button>
      {quality && <form onSubmit={event => { event.preventDefault(); void importFile() }}>
        <h4>Candidate output quality review</h4>
        <p>This candidate has not passed quality review. Inspect every dimension and the exact evidence before recording your findings. Rejected or unverified candidates remain hidden from the suggestion list.</p>
        <details><summary>Inspect candidate and frozen review evidence</summary><CodeBlock code={JSON.stringify(quality.request, null, 2)} label="Candidate review evidence" /></details>
        {Object.entries(dimensions).map(([dimension, label]) => {
          const finding = findings[dimension] ?? { outcome: '', reason: '', evidence_references: [] }
          const update = (change: Partial<Finding>) => setFindings(current => ({ ...current, [dimension]: { ...finding, ...change } }))
          return <fieldset key={dimension} disabled={busy}><legend>{label}</legend>
            <label>{label} finding<select required value={finding.outcome} onChange={event => update({ outcome: event.target.value })}><option value="">Choose a finding</option>{['SATISFIED', 'VIOLATED', 'UNVERIFIED', 'NOT_APPLICABLE'].map(value => <option key={value} value={value}>{value.replaceAll('_', ' ')}</option>)}</select></label>
            <label>{label} reason<textarea required maxLength={2000} value={finding.reason} onChange={event => update({ reason: event.target.value })} /></label>
            <label>{label} supporting evidence<select multiple value={finding.evidence_references} required={finding.outcome === 'SATISFIED'} onChange={event => update({ evidence_references: Array.from(event.target.selectedOptions, option => option.value) })}>{quality.request.evidence.map(item => <option key={item.reference} value={item.reference}>{item.reference}</option>)}</select></label>
          </fieldset>
        })}
        <Button type="submit" disabled={busy}>Record quality review and import</Button>
      </form>}
    </>}
    {data?.records.map(record => <article key={record.id}>
      <h4>{record.output.output_reference}</h4><p>{record.output.provider} / {record.output.model}, generated {record.output.generated_at}. Recorded by assessor {record.recorded_by}.</p>
      <ul>{record.output.criteria.map(criterion => <li key={criterion.criterion_version_id}><strong>Suggested {criterion.decision}</strong>: {criterion.reason}<p>Criterion {criterion.criterion_version_id}. Evidence: {criterion.evidence_ids.join(', ')}</p></li>)}</ul>
    </article>)}
  </div>
}
