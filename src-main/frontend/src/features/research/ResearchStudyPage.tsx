import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import type { AuthUser } from '../../app/types'
import { ApiError } from '../../app/api'
import { Button, Card, Field } from '../../components/ui'
import { studyApi, studyFields, operationalFields, key, type Form, type Packet, type Plan, type Reconciliation } from './api'

export function StudyEntryPage({ user }: { user: AuthUser }) {
  const navigate = useNavigate()
  const [study, setStudy] = useState('')
  const [course, setCourse] = useState('')
  return <section><h1>Study workspace</h1><p>Enter the study and course references supplied by your study team. Research access requires a separate grant.</p>
    <form onSubmit={e => { e.preventDefault(); navigate(`/${user.role === 'student' ? 'study' : 'research'}/${encodeURIComponent(study)}/${encodeURIComponent(course)}`) }}>
      <Field label="Study reference"><input required value={study} onChange={e => setStudy(e.target.value)} /></Field>
      <Field label="Course reference"><input required value={course} onChange={e => setCourse(e.target.value)} /></Field><Button type="submit">Open study</Button>
    </form></section>
}

function ReferenceFields({ labels, values, setValues }: { labels: Record<string, string>; values: Record<string, string>; setValues: (values: Record<string, string>) => void }) {
  return <>{Object.entries(labels).map(([name, label]) => <Field key={name} label={label}><input required value={values[name] ?? ''} onChange={e => setValues({ ...values, [name]: e.target.value })} /></Field>)}</>
}

function ResearchStudyPageContent({ user }: { user: AuthUser }) {
  const { studyId = '', courseId = '' } = useParams()
  const [plan, setPlan] = useState<Plan | null>(null)
  const [status, setStatus] = useState('')
  const [busy, setBusy] = useState(false)
  const [accessDenied, setAccessDenied] = useState(false)
  const [reconciliation, setReconciliation] = useState<Reconciliation | null>(null)
  const [records, setRecords] = useState<Record<string, string | null>[]>([])
  const [formJson, setFormJson] = useState('')
  const [formKey, setFormKey] = useState('')
  const [formVersion, setFormVersion] = useState(0)
  const [form, setForm] = useState<Form | null>(null)
  const [reviewReference, setReviewReference] = useState('')
  const [planJson, setPlanJson] = useState('')
  const [allocation, setAllocation] = useState<Record<string, string>>({})
  const [recordInput, setRecordInput] = useState<Record<string, string>>({ kind: 'missingness' })
  const [packetInput, setPacketInput] = useState<Record<string, string>>({})
  const [redacted, setRedacted] = useState('')
  const [packetId, setPacketId] = useState('')
  const [packet, setPacket] = useState<Packet | null>(null)
  const [rating, setRating] = useState('')
  const [ratingMissing, setRatingMissing] = useState(false)
  const [outcome, setOutcome] = useState<Record<string, string>>({})
  const [exportFields, setExportFields] = useState<string[]>([])
  const [exportStages, setExportStages] = useState<string[]>([])
  const [format, setFormat] = useState('json')
  const [governanceJson, setGovernanceJson] = useState('')
  const [governanceHistory, setGovernanceHistory] = useState<unknown[] | null>(null)
  const [formReference, setFormReference] = useState('')
  const [disposalRecords, setDisposalRecords] = useState('')
  const [disposalManifest, setDisposalManifest] = useState<Record<string, unknown> | null>(null)
  const [disposalAuthorization, setDisposalAuthorization] = useState('')
  const [disposalAcknowledged, setDisposalAcknowledged] = useState(false)
  const [disposalRequestKey, setDisposalRequestKey] = useState(key)
  const [operational, setOperational] = useState<Record<string, string>>({})
  const [operationalSelected, setOperationalSelected] = useState<string[]>([])
  const [redactions, setRedactions] = useState('[]')
  const [snapshotRevision, setSnapshotRevision] = useState(0)
  const [preview, setPreview] = useState<Awaited<ReturnType<typeof studyApi.operationalPreview>> | null>(null)
  const operationalSelection = () => ({ allocation_id: operational.allocation_id, instrument_record_id: operational.instrument_record_id, fields: operationalSelected, redactions: JSON.parse(redactions) })
  const allowed = user.scoped_assignments.some(a => a.role === 'research' && a.course_id === courseId)
  useEffect(() => {
    if (!allowed || accessDenied) return
    const controller = new AbortController()
    void studyApi.plan(studyId, courseId, controller.signal).then(value => { if (!controller.signal.aborted) setPlan(value) }).catch(() => { if (!controller.signal.aborted) setStatus('The study plan is unavailable under your current grant.') })
    return () => controller.abort()
  }, [allowed, accessDenied, studyId, courseId])
  async function run(action: () => Promise<unknown>, message: string) {
    setBusy(true); setStatus('')
    try { const result = await action(); setStatus(`${message}${result && typeof result === 'object' && 'id' in result ? ` Receipt: ${String(result.id)}` : ''}`) }
    catch (error) {
      if (error instanceof ApiError && [403, 404].includes(error.status)) {
        setAccessDenied(true); setPacket(null); setPreview(null); setRecords([]); setReconciliation(null)
        setPlan(null); setForm(null); setFormJson(''); setPlanJson(''); setRedacted(''); setRedactions('[]')
        setAllocation({}); setRecordInput({}); setPacketInput({}); setOutcome({}); setOperational({}); setGovernanceJson('')
        setStatus(''); setGovernanceHistory(null); setDisposalManifest(null); setDisposalRecords(''); setDisposalAcknowledged(false)
      } else setStatus('This action could not be completed. Check the current scope, approval references and permissions; your entries are retained.')
    }
    finally { setBusy(false) }
  }
  const write = (decision: object) => studyApi.decision(studyId, courseId, { request_key: key(), decision })
  if (accessDenied) return <p role="alert">Study access is unavailable. Private study content has been cleared. Reopen the workspace after your grant is checked.</p>
  if (!allowed && user.role !== 'admin') return <p role="alert">A research assignment for this course is required.</p>
  return <section aria-label="Research study workspace"><h1>Research study workspace</h1>
    <p>{plan?.production_active ? 'This study has an active recorded release.' : 'Production research remains closed.'} Version freezes alone do not establish institutional approval. Study ratings are separate from formal learner results.</p>
    <p role="status">{status}</p>
    {user.role === 'admin' && <Card heading="Governance records"><p>Import a reviewed governance command with its current revision and external authority references. Research activation requires the deployment opt-in and an active release bound to current approvals and content.</p>
      <Field label="Governance command"><textarea value={governanceJson} onChange={e => setGovernanceJson(e.target.value)} /></Field>
      <Button disabled={busy || !governanceJson} onClick={() => void run(() => studyApi.governance(studyId, JSON.parse(governanceJson)), 'Governance decision recorded.')}>Record governance decision</Button>
      <Button disabled={busy} onClick={() => void run(async () => { setGovernanceHistory(await studyApi.governanceHistory(studyId)) }, 'Governance history loaded.')}>Review governance history</Button>
      {governanceHistory && <pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(governanceHistory, null, 2)}</pre>}
    </Card>}
    {user.role === 'admin' && <Card heading="Controlled restricted-text disposal">
      <p>Preview exact instrument response receipts, separated by commas. This does not delete anything. Execution requires a separately recorded disposal authorization with the matching manifest, named executor, supplied retention date and expiry, and no active hold. Assessment, source, consent and audit history stay protected.</p>
      <Field label="Disposal instrument response receipts"><textarea value={disposalRecords} onChange={e => { setDisposalRecords(e.target.value); setDisposalManifest(null); setDisposalAcknowledged(false) }} /></Field>
      <Button disabled={busy || !disposalRecords.trim()} onClick={() => void run(async () => { setDisposalManifest(await studyApi.disposalPreview(studyId, disposalRecords.split(',').map(value => value.trim()).filter(Boolean))) }, 'Disposal inventory previewed; nothing deleted.')}>Preview disposal inventory</Button>
      {disposalManifest && <pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(disposalManifest, null, 2)}</pre>}
      <Field label="Disposal authorization receipt"><input value={disposalAuthorization} onChange={e => { setDisposalAuthorization(e.target.value); setDisposalAcknowledged(false); setDisposalRequestKey(key()) }} /></Field>
      <label><input type="checkbox" checked={disposalAcknowledged} onChange={e => setDisposalAcknowledged(e.target.checked)} /> I am the named executor and this authorization covers the exact reviewed inventory.</label>
      <Button disabled={busy || !disposalAuthorization || !disposalAcknowledged} onClick={() => void run(async () => { const result = await studyApi.disposalExecute(studyId, disposalAuthorization, disposalRequestKey); setDisposalAcknowledged(false); setDisposalManifest(null); return result }, 'Authorized restricted-text disposal completed.')}>Execute authorized restricted-text disposal</Button>
    </Card>}
    {allowed && <>
      <Card heading="Versioned instrument preparation"><p>Import the reviewed instrument definition. Supply all item wording, response limits, stages and support references; this workspace supplies no questionnaire content.</p>
        <Field label="Existing form reference"><input value={formReference} onChange={e => setFormReference(e.target.value)} /></Field>
        <Button disabled={busy || !formReference} onClick={() => void run(async () => { const loaded = await studyApi.readForm(studyId, courseId, formReference); setForm(loaded); setFormKey(loaded.instrument_key ?? ''); setFormVersion(loaded.version); setFormJson(JSON.stringify(loaded.definition, null, 2)) }, 'Exact instrument version loaded.')}>Load instrument version</Button>
        <Field label="Instrument key"><input value={formKey} onChange={e => setFormKey(e.target.value)} /></Field>
        <Field label="Current version (zero for a new instrument)"><input type="number" min={0} value={formVersion} onChange={e => setFormVersion(Number(e.target.value))} /></Field>
        <Field label="Instrument definition (JSON)"><textarea rows={8} value={formJson} onChange={e => setFormJson(e.target.value)} /></Field>
        <Button disabled={busy || !formKey || !formJson} onClick={() => void run(async () => { const saved = await studyApi.form(studyId, courseId, formKey, { request_key: key(), expected_version: formVersion, definition: JSON.parse(formJson) }); setForm(saved); setFormVersion(saved.version); return saved }, 'Instrument version saved.')}>Save instrument version</Button>
        {form && <><p>Form reference: {form.id}. Version: {form.version}. Digest: {form.content_digest}</p>
          <Field label="Synthetic review reference"><input value={reviewReference} onChange={e => setReviewReference(e.target.value)} /></Field>
          <Button disabled={busy || !reviewReference || form.frozen || form.frozen_for_synthetic_validation} onClick={() => void run(async () => { const saved = await studyApi.freeze(studyId, courseId, form.id, { request_key: key(), content_digest: form.content_digest, synthetic_review_reference: reviewReference }); setForm(saved); return saved }, 'Exact version frozen; institutional instrument approval remains separate.')}>Freeze exact version</Button></>}
      </Card>
      <Card heading="Study plan"><p>Plan {plan?.id ?? 'not recorded'}; revision {plan?.revision ?? 0}. Import conditions, stage/form references, rubric wording and controlled values, allocation/redaction rules, and authority/evidence references from the reviewed plan.</p>
        <Button disabled={busy || !plan} onClick={() => setPlanJson(JSON.stringify(plan?.plan, null, 2))}>Load current plan into editor</Button>
        <Field label="Study plan definition (JSON)"><textarea rows={8} value={planJson} onChange={e => setPlanJson(e.target.value)} /></Field>
        <Button disabled={busy || !planJson} onClick={() => void run(async () => { const result = await write({ ...JSON.parse(planJson), kind: 'plan', expected_revision: plan?.revision ?? 0 }); setPlan(await studyApi.plan(studyId, courseId)); return result }, 'Study plan recorded.')}>Record plan version</Button>
      </Card>
      <Card heading="Participant allocation"><p>Record the allocation made under the referenced rule. The application does not choose a study condition.</p>
        <ReferenceFields labels={{ subject_user_id: 'Participant account reference', sequence_key: 'Learning sequence reference', allocation_evidence_reference: 'Allocation evidence reference' }} values={allocation} setValues={setAllocation} />
        <Field label="Condition"><select value={allocation.condition ?? ''} onChange={e => setAllocation({ ...allocation, condition: e.target.value })}><option value="">Choose approved condition…</option>{plan?.plan.conditions.map(c => <option key={c}>{c}</option>)}</select></Field>
        <Button disabled={busy || !plan || !allocation.condition} onClick={() => void run(() => write({ ...allocation, kind: 'allocation', plan_id: plan?.id, subject_user_id: Number(allocation.subject_user_id) }), 'Allocation recorded.')}>Record allocation</Button>
      </Card>
      <Card heading="Participant-stage reconciliation">
        <p>Compare each currently eligible allocation with the stages in the current plan. An unrecorded stage needs an actual response or an explicit missingness record. Multiple responses or a response alongside a gap need human reconciliation; no outcome is inferred.</p>
        <Button disabled={busy} onClick={() => void run(async () => { setReconciliation(await studyApi.reconciliation(studyId, courseId)) }, 'Participant stages reconciled.')}>Reconcile participant stages</Button>
        {reconciliation && <>
          <p>{reconciliation.rows.length} expected stages under plan {reconciliation.plan_id ?? 'not recorded'}.</p>
          <table><caption>Current eligible participant stages</caption><thead><tr><th>Participant / sequence</th><th>Stage / form</th><th>Observation status</th><th>Review records</th></tr></thead>
            <tbody>{reconciliation.rows.map(row => <tr key={`${row.allocation_id}:${row.stage}`}>
              <td>{row.participant_id}<br />{row.sequence_id}<br />Allocation: {row.allocation_id}</td>
              <td>{row.stage}<br />{row.form_id}</td><td>{row.status}
                <ul>{row.observations.map(observation => <li key={observation.record_id}>{observation.kind}: {observation.record_id}; {observation.missing_reason ?? observation.reason_code ?? 'recorded'}; {observation.missing_item_count} skipped or unavailable items</li>)}</ul>
              </td><td>Packets: {row.packet_ids.join(', ') || 'none'}<br />Ratings: {row.rating_ids.join(', ') || 'none'}<br />Outcomes: {row.outcome_ids.join(', ') || 'none'}</td>
            </tr>)}</tbody></table>
          {Object.entries(reconciliation.excluded_counts).map(([reason, count]) => <p key={reason}>Excluded: {reason} ({count})</p>)}
        </>}
      </Card>
      <Card heading="Missingness, attrition and deviations"><p>Record an event against an allocated stage using the instrument's supplied reason codes. This preserves an explicit gap without inventing an outcome.</p>
        <ReferenceFields labels={{ allocation_id: 'Status allocation receipt', subject_user_id: 'Status participant account reference', reason_code: 'Instrument event reason code' }} values={recordInput} setValues={setRecordInput} />
        <Field label="Status stage"><select value={recordInput.stage ?? ''} onChange={e => setRecordInput({ ...recordInput, stage: e.target.value })}><option value="">Choose stage…</option>{plan?.plan.stages.map(s => <option key={s.stage}>{s.stage}</option>)}</select></Field>
        <Field label="Event type"><select value={recordInput.kind} onChange={e => setRecordInput({ ...recordInput, kind: e.target.value })}><option value="missingness">Missing observation</option><option value="attrition">Attrition</option><option value="deviation">Protocol deviation</option></select></Field>
        {recordInput.kind === 'missingness' && <Field label="Missing observation reason"><select value={recordInput.missing_reason ?? ''} onChange={e => setRecordInput({ ...recordInput, missing_reason: e.target.value })}><option value="">Choose reason…</option>{['not_collected', 'not_applicable', 'participant_skipped', 'technical_failure', 'not_evaluable', 'outside_window', 'not_approved'].map(reason => <option key={reason}>{reason}</option>)}</select></Field>}
        <Button disabled={busy || !recordInput.allocation_id || !recordInput.stage || !recordInput.reason_code || (recordInput.kind === 'missingness' && !recordInput.missing_reason)} onClick={() => void run(() => studyApi.researcherResponse(studyId, courseId, { allocation_id: recordInput.allocation_id, record: { request_key: key(), subject_user_id: Number(recordInput.subject_user_id), form_version_id: plan?.plan.stages.find(s => s.stage === recordInput.stage)?.form_id, sequence_key: recordInput.allocation_id, stage: recordInput.stage, kind: recordInput.kind, answers: [], reason_code: recordInput.reason_code, missing_reason: recordInput.kind === 'missingness' ? recordInput.missing_reason : null } }), 'Study status recorded.')}>Record study status</Button>
      </Card>
      <Card heading="Prepare study reviewer packet"><p>Supply evidence redacted under the recorded rule. The packet omits account, participant, sequence and condition fields. Verify the evidence text itself is appropriately blinded before recording it.</p>
        <ReferenceFields labels={{ allocation_id: 'Allocation receipt', instrument_record_id: 'Instrument response receipt', reviewer_user_id: 'Independent reviewer account reference', rubric_code: 'Study rubric code', redaction_evidence_reference: 'Redaction review evidence reference' }} values={packetInput} setValues={setPacketInput} />
        <Field label="Reviewed and redacted evidence"><textarea value={redacted} onChange={e => setRedacted(e.target.value)} /></Field>
        <Button disabled={busy || !redacted} onClick={() => void run(() => write({ ...packetInput, kind: 'packet', reviewer_user_id: Number(packetInput.reviewer_user_id), redacted_evidence: redacted }), 'Reviewer packet recorded.')}>Record reviewer packet</Button>
      </Card>
      <Card heading="Review assigned study packet">
        <Field label="Packet reference"><input value={packetId} onChange={e => { setPacketId(e.target.value); setPacket(null); setRating('') }} /></Field>
        <Button disabled={busy || !packetId} onClick={() => void run(async () => { const value = await studyApi.packet(studyId, courseId, packetId); setPacket(value) }, 'Assigned packet opened.')}>Open assigned packet</Button>
        {packet && <><p>{packet.stage}: {packet.rubric.wording}</p><blockquote style={{ whiteSpace: 'pre-wrap' }}>{packet.redacted_evidence}</blockquote>
          <label><input type="checkbox" checked={ratingMissing} onChange={e => setRatingMissing(e.target.checked)} /> Evidence cannot be evaluated</label>
          {!ratingMissing && <Field label="Study rating"><select value={rating} onChange={e => setRating(e.target.value)}><option value="">Choose…</option>{packet.rubric.values.map(v => <option key={v}>{v}</option>)}</select></Field>}
          <Button disabled={busy || (!ratingMissing && !rating)} onClick={() => void run(() => write({ kind: 'rating', packet_id: packet.id, ...(ratingMissing ? { missing_reason: 'not_evaluable' } : { value_code: rating }) }), 'Study rating recorded.')}>Record study rating</Button></>}
      </Card>
      <Card heading="Stage outcome"><p>Record the reviewed interpretation of an existing study rating using its rubric code. Missing evidence needs an explicit reason.</p>
        <ReferenceFields labels={{ packet_id: 'Outcome packet reference', rating_id: 'Rating receipt', interpretation_reference: 'Interpretation rule/evidence reference', value_code: 'Outcome value code (leave empty for not evaluable)' }} values={outcome} setValues={setOutcome} />
        <Button disabled={busy || !outcome.packet_id || !outcome.rating_id || !outcome.interpretation_reference} onClick={() => void run(() => write({ ...outcome, kind: 'outcome', value_code: outcome.value_code || null, missing_reason: outcome.value_code ? null : 'not_evaluable' }), 'Study outcome recorded.')}>Record stage outcome</Button>
      </Card>
      <Card heading="Study records"><Button disabled={busy} onClick={() => void run(async () => setRecords(await studyApi.records(studyId, courseId)), 'Current eligible study records loaded.')}>Load eligible records</Button>
        <table><thead><tr><th>Receipt</th><th>Kind</th><th>Stage</th><th>Value</th><th>Missingness</th></tr></thead><tbody>{records.map(row => <tr key={row['study.record_id']}><td>{row['study.record_id']}</td><td>{row['study.record_kind']}</td><td>{row['study.stage'] ?? '—'}</td><td>{row['study.value_code'] ?? '—'}</td><td>{row['study.missing_reason'] ?? '—'}</td></tr>)}</tbody></table>
      </Card>
      <Card heading="Operational evidence snapshot"><p>Select the exact approved operational fields for a study response. Preview identifies absent records and redaction requirements. A snapshot saves source bindings and review instructions; it does not copy the full operational dataset.</p>
        <ReferenceFields labels={{ allocation_id: 'Operational allocation receipt', instrument_record_id: 'Linked instrument response receipt' }} values={operational} setValues={setOperational} />
        <fieldset><legend>Operational fields to collect</legend>{operationalFields.map(field => <label key={field} style={{ display: 'block' }}><input type="checkbox" aria-label={`Collect ${field}`} checked={operationalSelected.includes(field)} onChange={e => { setPreview(null); setOperationalSelected(current => e.target.checked ? [...current, field] : current.filter(f => f !== field)) }} /> {field}</label>)}</fieldset>
        <Field label="Reviewed redaction spans (JSON)"><textarea rows={4} value={redactions} onChange={e => { setPreview(null); setRedactions(e.target.value) }} /></Field>
        <p>Text/code fields require the preview source digest, the plan's redaction rule reference, a review evidence reference and reviewed character spans. Empty spans still require an actual review. Known identifiers and secret patterns are removed automatically.</p>
        <Button disabled={busy || !operationalSelected.length} onClick={() => void run(async () => { setPreview(await studyApi.operationalPreview(studyId, courseId, operationalSelection())) }, 'Operational field preview loaded.')}>Preview operational fields</Button>
        {preview && <div>{Object.entries(preview.fields).map(([field, value]) => <details key={field}><summary>{field}: {value.missing_reason ?? 'Available'}</summary><p>Source digest: {value.source_digest}. Adapter: {value.adapter_version}</p><pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(value.value, null, 2)}</pre></details>)}</div>}
        <Field label="Current snapshot revision (zero for first capture)"><input type="number" min={0} value={snapshotRevision} onChange={e => setSnapshotRevision(Number(e.target.value))} /></Field>
        <Button disabled={busy || !preview || Object.values(preview.fields).some(v => v.missing_reason === 'redaction_required')} onClick={() => void run(async () => { const result = await studyApi.operationalCapture(studyId, courseId, { ...operationalSelection(), expected_revision: snapshotRevision, request_key: key() }); setSnapshotRevision(n => n + 1); return result }, 'Operational snapshot recorded.')}>Capture selected operational fields</Button>
      </Card>
      <Card heading="Full study export"><p>Choose the exact approved fields and stages. This export includes study allocation, instrument observations, ratings, outcomes and selected operational snapshots. Restricted evidence text stays outside routine exports.</p>
        <fieldset><legend>Export fields</legend>{studyFields.map(field => <label key={field} style={{ display: 'block' }}><input type="checkbox" checked={exportFields.includes(field)} onChange={e => setExportFields(current => e.target.checked ? [...current, field] : current.filter(f => f !== field))} /> {field}</label>)}</fieldset>
        <fieldset><legend>Export stages</legend>{plan?.plan.stages.map(s => <label key={s.stage} style={{ display: 'block' }}><input type="checkbox" checked={exportStages.includes(s.stage)} onChange={e => setExportStages(current => e.target.checked ? [...current, s.stage] : current.filter(v => v !== s.stage))} /> {s.stage}</label>)}</fieldset>
        <Field label="Export format"><select value={format} onChange={e => setFormat(e.target.value)}><option value="json">JSON</option><option value="csv">CSV</option></select></Field>
        <Button disabled={busy || !exportFields.length || !exportStages.length} onClick={() => void run(() => studyApi.export(studyId, courseId, exportFields, exportStages, format), 'Study export downloaded.')}>Download study export</Button>
      </Card>
    </>}
  </section>
}

export function ResearchStudyPage({ user }: { user: AuthUser }) {
  const { studyId, courseId } = useParams()
  return <ResearchStudyPageContent key={`${studyId}:${courseId}:${JSON.stringify(user.scoped_assignments)}`} user={user} />
}
