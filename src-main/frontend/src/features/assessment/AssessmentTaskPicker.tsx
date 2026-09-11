import { useState } from 'react'

import { ApiError, api } from '../../app/api'
import type { ApiSchemas } from '../../api/generated'
import { SourceReviewPanel } from '../../components/SourceReviewPanel'
import { Button, Field, Select } from '../../components/ui'
import type { SetupUpdate } from './AssessorSetupPanels'
import { GeneratedAssessmentDraft } from './GeneratedAssessmentDraft'

export function AssessmentTaskPicker({ courseId, lockedIdentity, onUpdate }: { courseId: string; lockedIdentity: boolean; onUpdate: SetupUpdate }) {
  const [loaded, setLoaded] = useState<{ courseId: string; rows: (ApiSchemas['AssessmentAuthoringTaskRead'] & { generated_assessment_candidate?: boolean })[]; offset: number } | null>(null)
  const [selectedId, setSelectedId] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [materialId, setMaterialId] = useState('')
  const rows = loaded?.courseId === courseId ? loaded.rows : []
  const selected = rows.find((row) => row.task_id === selectedId)
  const load = async (offset = 0) => {
    setBusy(true)
    setError('')
    setLoaded(null)
    setSelectedId('')
    setMaterialId('')
    try {
      setLoaded({ courseId, rows: await api.assessment.authoringTasks(courseId, offset), offset })
      setSelectedId('')
      setMaterialId('')
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Saved tasks could not be loaded.')
    } finally { setBusy(false) }
  }
  const choose = () => {
    if (!selected?.revision_id || !selected.content_digest || lockedIdentity || !selected.reviewed) return
    onUpdate('taskId', selected.task_id)
    onUpdate('outcomeId', selected.outcome_id)
    onUpdate('outcome', selected.outcome_statement)
    onUpdate('sourceVersion', `task-revision:${selected.revision_id}`)
    onUpdate('sourceDigest', selected.content_digest)
    onUpdate('source', selected.source_materials.map((material) => material.label).join(', '))
    onUpdate('taskFamily', selected.task_type)
  }
  return <section aria-label="Saved assessment tasks">
    <Button variant="secondary" disabled={!courseId || busy} onClick={() => void load()}>Browse saved course tasks</Button>
    {error && <p role="alert">{error}</p>}
    {loaded?.courseId === courseId && <>
      <Field label="Saved course task"><Select value={selectedId} disabled={busy} onValueChange={(value) => { setSelectedId(value); setMaterialId('') }} options={rows.map((task) => ({ value: task.task_id, label: task.title }))} placeholder="Choose a task" /></Field>
      {rows.length === 0 && <p>No tasks on this page.</p>}
      <Button variant="quiet" disabled={busy || loaded.offset === 0} onClick={() => void load(Math.max(0, loaded.offset - 20))}>Previous tasks</Button>
      <Button variant="quiet" disabled={busy || rows.length < 20} onClick={() => void load(loaded.offset + 20)}>Next tasks</Button>
      {selected && <>
        <p>{selected.outcome_statement}</p>
        <p>{selected.reviewed ? 'Current teaching review approved.' : 'Teaching review is incomplete.'}</p>
        <ul>{selected.issues.map((issue) => <li key={issue}>{issue}</li>)}</ul>
        <Button disabled={busy || lockedIdentity || !selected.reviewed || !selected.source_materials.length} onClick={choose}>Use this reviewed task</Button>
        {selected.generated_assessment_candidate && selected.reviewed && selected.revision_id && !lockedIdentity && <GeneratedAssessmentDraft key={`${courseId}-${selected.task_id}-${selected.revision_id}`} courseId={courseId} taskId={selected.task_id} revisionId={selected.revision_id} />}
        {lockedIdentity && <p>The saved definition keeps its course and outcome. Start a new definition to change them.</p>}
        {selected.source_materials.map((material) => <Button key={material.material_id} variant="quiet" onClick={() => setMaterialId(material.material_id)}>Read source: {material.label}</Button>)}
        {materialId && <SourceReviewPanel key={`${courseId}-${materialId}`} courseId={courseId} materialId={materialId} readOnly />}
      </>}
    </>}
  </section>
}
