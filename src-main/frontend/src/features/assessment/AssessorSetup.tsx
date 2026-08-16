import { useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError } from '../../app/api'
import type { ScopedRoleAssignment } from '../../app/types'
import { PageHeading, Panel } from '../../components/ScreenPrimitives'
import { assessmentApi } from './api'
import type { AssessmentDefinition, AssessmentDraft } from './api'
import { assessmentPurposeValues, bloomKnowledgeValues, bloomProcessValues } from './types'
import './assessment.css'

interface SetupValues {
  courseId: string
  outcomeId: string
  outcome: string
  source: string
  sourceVersion: string
  sourceDigest: string
  bloomProcess: AssessmentDraft['bloom_process']
  knowledgeDimension: AssessmentDraft['knowledge_dimension']
  purpose: AssessmentDraft['purpose']
  claim: string
  evidence: string
  criterion: string
  taskId: string
  taskFamily: string
  tools: string
  support: string
  access: string
  transfer: string
  approvalReason: string
}

const initialValues: Omit<SetupValues, 'courseId'> = {
  outcomeId: '', outcome: '', source: '', sourceVersion: '', sourceDigest: '',
  bloomProcess: 'APPLY', knowledgeDimension: 'PROCEDURAL', purpose: 'SUMMATIVE',
  claim: '', evidence: '', criterion: '', taskId: '', taskFamily: '', tools: '',
  support: '', access: '', transfer: '', approvalReason: '',
}

function safeError(error: unknown): string {
  if (!(error instanceof ApiError)) return 'The assessment service could not be reached. Your draft remains in this form.'
  if (error.status === 403) return 'Your assessor permission no longer allows this action.'
  if (error.status === 404) return 'This assessment record is no longer available in the assigned course.'
  if (error.status === 409) return 'This assessment changed elsewhere. Your local values are still available below.'
  if (error.status === 422) return 'The assessment could not be approved. Check the required fields and current publication policy.'
  return 'The assessment service could not complete the request. Your draft remains in this form.'
}

function label(value: string): string {
  return value.toLowerCase().replaceAll('_', ' ')
}

function list(value: string): string[] {
  return value.split(',').map((item) => item.trim()).filter(Boolean)
}

export function AssessorSetup({
  assignments,
  onCheckAccess,
  onAccessRevoked,
}: {
  assignments: ScopedRoleAssignment[]
  onCheckAccess: () => Promise<boolean>
  onAccessRevoked: () => void
}) {
  const assessorAssignments = assignments.filter((assignment) => assignment.role === 'assessor')
  const [values, setValues] = useState<SetupValues>({ ...initialValues, courseId: assessorAssignments[0]?.course_id ?? '' })
  const [definition, setDefinition] = useState<AssessmentDefinition | null>(null)
  const [history, setHistory] = useState<AssessmentDefinition[]>([])
  const [faults, setFaults] = useState<string[]>([])
  const [status, setStatus] = useState('')
  const [serverError, setServerError] = useState('')
  const [stale, setStale] = useState(false)
  const [busy, setBusy] = useState<'save' | 'publish' | 'history' | 'access' | null>(null)

  const requiredFields = useMemo(() => [
    ['course', values.courseId], ['outcome ID', values.outcomeId], ['outcome wording', values.outcome],
    ['source', values.source], ['source version', values.sourceVersion], ['source digest', values.sourceDigest],
    ['claim', values.claim], ['required evidence', values.evidence], ['mandatory criterion', values.criterion],
    ['task ID', values.taskId], ['task family', values.taskFamily], ['permitted tools', values.tools],
    ['instructional support', values.support], ['access conditions', values.access], ['transfer rule', values.transfer],
  ].filter(([, value]) => !value.trim()).map(([name]) => name), [values])

  const update = <Key extends keyof SetupValues>(key: Key, value: SetupValues[Key]) => {
    setValues((current) => ({ ...current, [key]: value }))
    setFaults([])
    setStatus('')
    setServerError('')
  }

  const draftPayload = (): AssessmentDraft => ({
    bloom_process: values.bloomProcess,
    knowledge_dimension: values.knowledgeDimension,
    purpose: values.purpose,
    claim: values.claim.trim(),
    supporting_evidence: { required: values.evidence.trim() },
    contradicting_evidence: { source: values.source.trim() },
    insufficient_evidence: { next_action: 'Return the attempt with the approved reassessment rule.' },
    task_conditions: { source: values.source.trim(), outcome: values.outcome.trim() },
    next_action_contract: { next_action: 'Explain the missing evidence and reassessment path.' },
    permitted_tools: list(values.tools),
    instructional_support: list(values.support),
    access_conditions: list(values.access),
    transfer_rule: { rule: values.transfer.trim() },
    evidence_sufficiency: { required: values.evidence.trim() },
    formal_result_eligible: true,
    criteria: [{
      stable_key: 'required-evidence', learner_description: values.criterion.trim(),
      evidence_description: values.evidence.trim(), mandatory: true,
      evidence_source_types: ['learner_response'], met_rule: values.criterion.trim(),
      not_met_rule: 'The required evidence is absent or does not meet this criterion.',
      not_evaluable_rule: 'The evidence cannot be evaluated safely.', approved_anchors: {}, critical_error_rules: {},
    }],
    pass_rule_expression: { all_mandatory_criteria_must_be_met: ['required-evidence'] },
    task_forms: [{
      learning_task_id: values.taskId.trim(), source_version: values.sourceVersion.trim(),
      source_digest: values.sourceDigest.trim(), task_family: values.taskFamily.trim(),
      context: { source: values.source.trim() }, constraints: { access: list(values.access) },
    }],
  })

  const saveDraft = async (event: FormEvent) => {
    event.preventDefault()
    if (requiredFields.length) {
      setFaults(requiredFields)
      setStatus('Complete every required field before saving this assessment draft.')
      return
    }
    setBusy('save')
    setServerError('')
    try {
      const created = await assessmentApi.createDraft(values.courseId, values.outcomeId.trim(), draftPayload())
      setDefinition(created)
      setHistory([created])
      setStale(false)
      setStatus('Draft saved. Review the pass rule, then approve when ready.')
    } catch (error) {
      setServerError(safeError(error))
    } finally {
      setBusy(null)
    }
  }

  const loadHistory = async () => {
    if (!definition) return
    setBusy('history')
    setServerError('')
    try {
      setHistory(await assessmentApi.history(values.courseId, definition.assessment_definition_id))
      setStale(false)
      setStatus('Server history reloaded. Your local form values were not changed.')
    } catch (error) {
      setServerError(safeError(error))
    } finally {
      setBusy(null)
    }
  }

  const publish = async () => {
    if (!definition) return
    const approvalFaults = [...requiredFields, ...(!values.approvalReason.trim() ? ['approval reason'] : [])]
    if (approvalFaults.length) {
      setFaults(approvalFaults)
      setStatus('Complete every required field and record an approval reason before publishing.')
      return
    }
    setBusy('publish')
    setServerError('')
    try {
      const approved = await assessmentApi.publish(
        values.courseId, definition.assessment_definition_id, definition.version, values.approvalReason.trim(),
      )
      setDefinition(approved)
      setHistory((current) => [...current.filter((item) => item.id !== approved.id), approved])
      setStale(false)
      setStatus('Assessment approved and published.')
    } catch (error) {
      setServerError(safeError(error))
      setStale(error instanceof ApiError && error.status === 409)
    } finally {
      setBusy(null)
    }
  }

  const checkAccess = async () => {
    setBusy('access')
    try {
      const active = await onCheckAccess()
      if (!active) onAccessRevoked()
      else setStatus('Assessor access is still active for this course.')
    } catch {
      setServerError('Assessor access could not be refreshed. Existing controls have not changed.')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="screen assessment-setup">
      <PageHeading
        eyebrow="Assessor workspace"
        title="Assessment setup"
        description="Set the approved evidence rules before learners begin an assessed task."
        actions={<button className="button button--secondary" onClick={() => void checkAccess()} disabled={busy === 'access'}>Check assessor access</button>}
      />
      <p className="assessment-notice" role="note"><strong>Bloom is not a score.</strong> It names the evidence target. The approved criteria decide whether evidence meets the standard.</p>
      {serverError && <p className="form-error" role="alert">{serverError}</p>}
      {status && <p className="form-status" role="status">{status}</p>}
      {faults.length > 0 && <section className="form-error" role="alert" aria-labelledby="assessment-faults"><h2 id="assessment-faults">Complete the setup</h2><p>Missing: {faults.join(', ')}.</p></section>}
      <form onSubmit={saveDraft} noValidate>
        <Panel title="Assessment target" eyebrow="Outcome and source">
          <div className="assessment-form-grid">
            <label className="field"><span>Assigned course</span><select aria-label="Assigned course" value={values.courseId} onChange={(event) => update('courseId', event.target.value)} aria-describedby="course-help"><option value="">Select an assigned course</option>{assessorAssignments.map((assignment) => <option key={assignment.id} value={assignment.course_id}>{assignment.course_id}</option>)}</select><small id="course-help">Only courses in your active assessor assignment are available.</small></label>
            <label className="field"><span>Outcome ID</span><input aria-label="Outcome ID" value={values.outcomeId} onChange={(event) => update('outcomeId', event.target.value)} required /></label>
            <label className="field field--full"><span>Outcome wording</span><textarea aria-label="Outcome wording" value={values.outcome} onChange={(event) => update('outcome', event.target.value)} required /></label>
            <label className="field"><span>Source</span><input aria-label="Source" value={values.source} onChange={(event) => update('source', event.target.value)} required /></label>
            <label className="field"><span>Source version</span><input aria-label="Source version" value={values.sourceVersion} onChange={(event) => update('sourceVersion', event.target.value)} required /></label>
            <label className="field field--full"><span>Source digest</span><input aria-label="Source digest" value={values.sourceDigest} onChange={(event) => update('sourceDigest', event.target.value)} required /></label>
          </div>
        </Panel>
        <Panel title="Evidence and pass rule" eyebrow="Bloom target">
          <div className="assessment-form-grid">
            <label className="field"><span>Bloom process</span><select aria-label="Bloom process" value={values.bloomProcess} onChange={(event) => update('bloomProcess', event.target.value as SetupValues['bloomProcess'])}>{bloomProcessValues.map((value) => <option key={value} value={value}>{label(value)}</option>)}</select></label>
            <label className="field"><span>Knowledge dimension</span><select aria-label="Knowledge dimension" value={values.knowledgeDimension} onChange={(event) => update('knowledgeDimension', event.target.value as SetupValues['knowledgeDimension'])}>{bloomKnowledgeValues.map((value) => <option key={value} value={value}>{label(value)}</option>)}</select></label>
            <label className="field"><span>Assessment purpose</span><select aria-label="Assessment purpose" value={values.purpose} onChange={(event) => update('purpose', event.target.value as SetupValues['purpose'])}>{assessmentPurposeValues.map((value) => <option key={value} value={value}>{label(value)}</option>)}</select></label>
            <label className="field field--full"><span>Claim</span><textarea aria-label="Claim" value={values.claim} onChange={(event) => update('claim', event.target.value)} required /></label>
            <label className="field field--full"><span>Required evidence</span><textarea aria-label="Required evidence" value={values.evidence} onChange={(event) => update('evidence', event.target.value)} required /></label>
            <label className="field field--full"><span>Mandatory criterion</span><textarea aria-label="Mandatory criterion" value={values.criterion} onChange={(event) => update('criterion', event.target.value)} required /></label>
          </div>
          <aside className="assessment-pass-rule" aria-label="Pass rule preview"><h3>Pass rule preview</h3><p>Pass when every mandatory criterion is met for the selected Bloom target.</p><p>Each listed mandatory criterion must be met.</p></aside>
        </Panel>
        <Panel title="Task conditions" eyebrow="Form, tools, and access">
          <div className="assessment-form-grid">
            <label className="field"><span>Task form ID</span><input aria-label="Task form ID" value={values.taskId} onChange={(event) => update('taskId', event.target.value)} required /></label>
            <label className="field"><span>Task family</span><input aria-label="Task family" value={values.taskFamily} onChange={(event) => update('taskFamily', event.target.value)} required /></label>
            <label className="field field--full"><span>Permitted tools</span><input aria-label="Permitted tools" value={values.tools} onChange={(event) => update('tools', event.target.value)} required /><small>Separate items with commas.</small></label>
            <label className="field field--full"><span>Instructional support</span><textarea aria-label="Instructional support" value={values.support} onChange={(event) => update('support', event.target.value)} required /></label>
            <label className="field field--full"><span>Access conditions</span><textarea aria-label="Access conditions" value={values.access} onChange={(event) => update('access', event.target.value)} required /></label>
            <label className="field field--full"><span>Transfer rule</span><textarea aria-label="Transfer rule" value={values.transfer} onChange={(event) => update('transfer', event.target.value)} required /></label>
          </div>
        </Panel>
        <div className="assessment-actions"><button className="button button--primary" type="submit" disabled={busy === 'save'}>{busy === 'save' ? 'Saving draft…' : 'Save assessment draft'}</button></div>
      </form>
      <Panel title="Approval and history" eyebrow="Assessor decision">
        {!definition ? <p className="assessment-muted">Save a complete draft before it can be approved.</p> : <div className="assessment-approval"><p><strong>Status:</strong> {definition.approval_state === 'APPROVED' ? 'Published' : 'Draft'}</p><label className="field"><span>Approval reason</span><textarea aria-label="Approval reason" value={values.approvalReason} onChange={(event) => update('approvalReason', event.target.value)} required /></label><div className="assessment-actions"><button className="button button--secondary" onClick={() => void loadHistory()} disabled={busy === 'history'}>{busy === 'history' ? 'Loading history…' : 'Reload server history'}</button><button className="button button--primary" onClick={() => void publish()} disabled={busy === 'publish' || definition.approval_state === 'APPROVED'}>{busy === 'publish' ? 'Publishing…' : 'Approve and publish'}</button></div>{stale && <section className="assessment-conflict" role="alert"><h3>Another version is available</h3><p>Your local values have not been replaced. Reload server history to compare versions, then decide what to keep.</p><details><summary>Compare local draft</summary><p><strong>Local claim:</strong> {values.claim}</p><p><strong>Local criterion:</strong> {values.criterion}</p></details></section>}<ol className="assessment-history" aria-label="Approval history">{history.map((item) => <li key={item.id}><strong>{item.approval_state === 'APPROVED' ? 'Published' : 'Draft'}</strong><span>Version {item.version}</span>{item.approved_at && <span>Approved {new Date(item.approved_at).toLocaleString()}</span>}</li>)}</ol></div>}
      </Panel>
    </div>
  )
}
