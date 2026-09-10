import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../app/api'
import type { LearnerModelTimelineResponse } from '../app/api'

export function LearnerModelTimeline() {
  const [search] = useSearchParams()
  const initialCourse = search.get('course') ?? ''
  const initialOutcome = search.get('outcome') ?? ''
  const [courseId, setCourseId] = useState(initialCourse)
  const [outcomeId, setOutcomeId] = useState(initialOutcome)
  const [timeline, setTimeline] = useState<LearnerModelTimelineResponse | null>(null)
  const [message, setMessage] = useState('')
  const [evidenceId, setEvidenceId] = useState('')
  const [targetKind, setTargetKind] = useState<'EVIDENCE' | 'ESTIMATE'>('EVIDENCE')
  const [note, setNote] = useState('')
  useEffect(() => {
    if (!initialCourse || !initialOutcome) return
    let active = true
    api.learnerModel.mine(initialCourse, initialOutcome)
      .then(page => { if (active) setTimeline(page) })
      .catch(() => { if (active) setMessage('This learning history is unavailable.') })
    return () => { active = false }
  }, [initialCourse, initialOutcome])
  const load = async (cursor?: string) => {
    try {
      const page = await api.learnerModel.mine(courseId, outcomeId, cursor)
      setTimeline(current => cursor && current ? { ...page, entries: [...current.entries, ...page.entries] } : page)
      setMessage('')
    }
    catch { setMessage('This learning history is unavailable. Check the course and outcome, then try again.') }
  }
  const annotate = async () => {
    try {
      await api.learnerModel.annotate({ course_id: courseId, outcome_id: outcomeId, target: targetKind === 'EVIDENCE' ? { target_kind: targetKind, evidence_id: evidenceId } : { target_kind: targetKind, estimate_id: evidenceId }, note, idempotency_key: crypto.randomUUID(), occurred_at: new Date().toISOString() })
      setNote(''); await load(); setMessage('Your context was added.')
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Your context could not be saved. Your draft is still here.') }
  }
  return <main><h1>My learning evidence and estimates</h1><p>Estimates are uncertain, evidence-linked learning inferences—not grades or formal results.</p><label>Course ID<input value={courseId} onChange={event => setCourseId(event.target.value)} /></label><label>Outcome ID<input value={outcomeId} onChange={event => setOutcomeId(event.target.value)} /></label><button onClick={() => void load()}>Load history</button><p role="status">{message}</p>{timeline && <><h2>Ordered history</h2><ol>{timeline.entries.map(item => <li key={`${item.entry_type}:${item.reference_id}`}>{item.entry_type.toLowerCase()} recorded {new Date(item.occurred_at).toLocaleString()}</li>)}</ol>{timeline.next_cursor && <button onClick={() => void load(timeline.next_cursor ?? undefined)}>Load more history</button>}<h2>Evidence</h2><ul>{timeline.evidence.map(item => <li key={item.id}>{item.type} — {new Date(item.occurred_at).toLocaleString()}</li>)}</ul><h2>Add context</h2><label>Challenge target<select value={targetKind} onChange={event => setTargetKind(event.target.value as typeof targetKind)}><option value="EVIDENCE">Evidence</option><option value="ESTIMATE">Estimate</option></select></label><label>{targetKind === 'EVIDENCE' ? 'Evidence ID' : 'Estimate ID'}<input value={evidenceId} onChange={event => setEvidenceId(event.target.value)} /></label><label>Context ({note.length}/2000)<textarea maxLength={2000} value={note} onChange={event => setNote(event.target.value)} /></label><button disabled={!evidenceId || !note.trim()} onClick={() => void annotate()}>Add context</button><h2>Correction history</h2><ul>{timeline.corrections.map(item => <li key={item.annotation.annotation_id}>Your note: {item.annotation.note}<ul>{item.reviews.map(review => <li key={review.review_id}>Educator outcome: {review.action}. {review.reason}</li>)}</ul></li>)}</ul><h2>Snapshots</h2><ul>{timeline.snapshots.map(snapshot => <li key={snapshot.snapshot_id}>Snapshot {snapshot.record_version}: {snapshot.validation_classification}<ul>{snapshot.estimates.map(estimate => <li key={estimate.estimate_id}>{estimate.dimension}: {estimate.inference_status}; uncertainty {estimate.uncertainty}</li>)}</ul></li>)}</ul></>}</main>
}
