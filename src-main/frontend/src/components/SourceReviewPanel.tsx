import { useEffect, useState } from 'react'

import { ApiError, api } from '../app/api'
import type { ApiSchemas } from '../api/generated'
import { Button, Field, Select, Tag, Textarea } from './ui'
import styles from './TaskReviewPanel.module.css'

export function SourceReviewPanel({ courseId, materialId, readOnly = false }: { courseId: string; materialId: string; readOnly?: boolean }) {
  const [revisions, setRevisions] = useState<ApiSchemas['SourceRevisionRead'][]>([])
  const [selectedId, setSelectedId] = useState('')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [reload, setReload] = useState(0)
  const selected = revisions.find((revision) => revision.id === selectedId)

  useEffect(() => {
    const controller = new AbortController()
    void api.sourceReview.history(courseId, materialId, controller.signal).then((rows) => {
      if (controller.signal.aborted) return
      setRevisions(rows)
      setSelectedId((current) => rows.some((row) => row.id === current) ? current : rows[0]?.id ?? '')
      setLoading(false)
    }).catch((caught: unknown) => {
      if (controller.signal.aborted) return
      setError(caught instanceof ApiError ? caught.message : 'Source history could not be loaded.')
      setLoading(false)
    })
    return () => controller.abort()
  }, [courseId, materialId, reload])

  const refresh = () => {
    setLoading(true)
    setError('')
    setReason('')
    setReload((value) => value + 1)
  }

  const record = async (state: 'APPROVED' | 'REVOKED') => {
    if (!selected || busy || loading || readOnly) return
    setBusy(true)
    setError('')
    setNotice('')
    try {
      await api.sourceReview.record(courseId, materialId, selected.id, {
        state, reason, expected_sequence: selected.approvals?.at(-1)?.sequence ?? 0,
      })
      refresh()
      setNotice(state === 'APPROVED' ? 'Source approval recorded. Review tasks that use this source before publishing.' : 'Source approval revoked. Tasks that relied on it need review.')
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Source review could not be recorded.')
    } finally {
      setBusy(false)
    }
  }

  return <section aria-label="Source review" className={styles.panel}>
    <h3>Review saved source passages</h3>
    <p>{readOnly ? 'Inspect the exact saved passages and their approval history.' : 'Read the saved content before recording approval. This action applies to the selected revision.'}</p>
    {error && <p role="alert">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    <Button variant="quiet" disabled={busy} onClick={refresh}>Reload source history</Button>
    {loading ? <p role="status">Loading source history...</p> : error && revisions.length === 0 ? null : revisions.length === 0 ? <p>No saved passages are available. Process this material before review.</p> : <>
      <Field label="Source revision"><Select value={selectedId} disabled={busy} onValueChange={(value) => { setSelectedId(value); setReason(''); setNotice('') }}
        options={revisions.map((revision) => ({ value: revision.id, label: `Revision ${revision.version}: ${revision.source_label}` }))} />
      </Field>
      {selected && <>
        <p><Tag>{selected.approval_state === 'APPROVED' ? 'Approved' : selected.approval_state === 'REVOKED' ? 'Revoked' : 'Unreviewed'}</Tag> Saved {new Date(selected.created_at).toLocaleString()}</p>
        <ol>{selected.passages?.map((passage) => <li key={passage.id} className={styles.entry}>
          <h4>{passage.heading || `Passage ${passage.chunk_index + 1}`}</h4>
          {passage.location_label && <p>{passage.location_label}</p>}
          <p>{passage.chunk_text}</p>
        </li>)}</ol>
        {!readOnly && <><Field label="Source review reason" required><Textarea value={reason} maxLength={2000} disabled={busy} onChange={(event) => setReason(event.target.value)} /></Field>
        <div className={styles.actions}>
          <Button disabled={busy || !reason.trim() || !selected.passages?.length} onClick={() => void record('APPROVED')}>Approve source revision</Button>
          <Button disabled={busy || !reason.trim() || selected.approval_state !== 'APPROVED'} onClick={() => void record('REVOKED')}>Revoke source approval</Button>
        </div></>}
        <details><summary>Source approval history</summary><ol>{selected.approvals?.map((approval) => <li key={approval.id}>
          {approval.state === 'APPROVED' ? 'Approved' : 'Revoked'}: {approval.reason} ({new Date(approval.created_at).toLocaleString()})
        </li>)}</ol></details>
      </>}
    </>}
  </section>
}
