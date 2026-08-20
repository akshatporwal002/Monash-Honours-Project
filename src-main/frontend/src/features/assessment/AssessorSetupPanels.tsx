import type { ScopedRoleAssignment } from '../../app/types'
import {
  Button,
  Card,
  Checkbox,
  Field,
  Input,
  Select,
  Textarea,
  bloomKnowledgeLabels,
  bloomProcessDescriptors,
  bloomProcessLabels,
} from '../../components/ui'
import type { AssessmentDefinition } from './api'
import type { SetupValues } from './assessmentDraft'
import { purposeLabels } from './assessmentReviewPresentation'
import { assessmentPurposeValues, bloomKnowledgeValues, bloomProcessValues } from './types'
import styles from './assessment.module.css'

export type SetupUpdate = <Key extends keyof SetupValues>(
  key: Key,
  value: SetupValues[Key],
) => void

function AssessmentTargetFields({
  values,
  assignments,
  lockedIdentity,
  onUpdate,
}: {
  values: SetupValues
  assignments: ScopedRoleAssignment[]
  lockedIdentity: boolean
  onUpdate: SetupUpdate
}) {
  return (
    <Card eyebrow="Outcome and source">
      <fieldset className={styles.fieldset}>
        <legend className={styles.legend}>Assessment target</legend>
        <div className={styles.formGrid}>
          <Field
            label="Assigned course"
            help="Only courses in your active assessor assignment are available."
          >
            <Select
              options={assignments.map((assignment) => ({
                value: assignment.course_id,
                label: assignment.course_id,
              }))}
              value={values.courseId || undefined}
              onValueChange={(value) => onUpdate('courseId', value)}
              placeholder="Select an assigned course"
              disabled={lockedIdentity}
            />
          </Field>
          <Field label="Outcome ID">
            <Input
              value={values.outcomeId}
              onChange={(event) => onUpdate('outcomeId', event.target.value)}
              disabled={lockedIdentity}
              required
            />
          </Field>
          <Field label="Outcome wording" className={styles.fieldFull}>
            <Textarea
              value={values.outcome}
              onChange={(event) => onUpdate('outcome', event.target.value)}
              required
            />
          </Field>
          <Field label="Source">
            <Input
              value={values.source}
              onChange={(event) => onUpdate('source', event.target.value)}
              required
            />
          </Field>
          <Field label="Source version">
            <Input
              value={values.sourceVersion}
              onChange={(event) => onUpdate('sourceVersion', event.target.value)}
              required
            />
          </Field>
          <Field label="Source digest" className={styles.fieldFull}>
            <Input
              value={values.sourceDigest}
              onChange={(event) => onUpdate('sourceDigest', event.target.value)}
              required
            />
          </Field>
        </div>
      </fieldset>
    </Card>
  )
}

function EvidenceRuleFields({ values, onUpdate }: { values: SetupValues, onUpdate: SetupUpdate }) {
  return (
    <Card eyebrow="Bloom target">
      <fieldset className={styles.fieldset}>
        <legend className={styles.legend}>Evidence and pass rule</legend>
        <div className={styles.formGrid}>
          <Field label="Bloom process" help={bloomProcessDescriptors[values.bloomProcess]}>
            <Select
              options={bloomProcessValues.map((value) => ({
                value,
                label: bloomProcessLabels[value],
              }))}
              value={values.bloomProcess}
              onValueChange={(value) => (
                onUpdate('bloomProcess', value as SetupValues['bloomProcess'])
              )}
            />
          </Field>
          <Field label="Knowledge dimension">
            <Select
              options={bloomKnowledgeValues.map((value) => ({
                value,
                label: bloomKnowledgeLabels[value],
              }))}
              value={values.knowledgeDimension}
              onValueChange={(value) => (
                onUpdate('knowledgeDimension', value as SetupValues['knowledgeDimension'])
              )}
            />
          </Field>
          <Field label="Assessment purpose">
            <Select
              options={assessmentPurposeValues.map((value) => ({
                value,
                label: purposeLabels[value],
              }))}
              value={values.purpose}
              onValueChange={(value) => onUpdate('purpose', value as SetupValues['purpose'])}
            />
          </Field>
          <Field label="Claim" className={styles.fieldFull}>
            <Textarea
              value={values.claim}
              onChange={(event) => onUpdate('claim', event.target.value)}
              required
            />
          </Field>
          <Field label="Required evidence" className={styles.fieldFull}>
            <Textarea
              value={values.evidence}
              onChange={(event) => onUpdate('evidence', event.target.value)}
              required
            />
          </Field>
          <Field label="Mandatory criterion" className={styles.fieldFull}>
            <Textarea
              value={values.criterion}
              onChange={(event) => onUpdate('criterion', event.target.value)}
              required
            />
          </Field>
          <Checkbox
            className={styles.fieldFull}
            label="I verified that this task elicits the selected Bloom process."
            checked={values.bloomVerified}
            onChange={(event) => onUpdate('bloomVerified', event.target.checked)}
          />
        </div>
        <aside className={styles.passRule} aria-label="Pass rule preview">
          <p className={styles.passRuleTitle}>Pass rule preview</p>
          <p>Pass when every mandatory criterion is met for the selected Bloom target.</p>
          <p>Each listed mandatory criterion must be met.</p>
        </aside>
      </fieldset>
    </Card>
  )
}

function TaskConditionFields({ values, onUpdate }: { values: SetupValues, onUpdate: SetupUpdate }) {
  return (
    <Card eyebrow="Form, tools, and access">
      <fieldset className={styles.fieldset}>
        <legend className={styles.legend}>Task conditions</legend>
        <div className={styles.formGrid}>
          <Field label="Task form ID">
            <Input
              value={values.taskId}
              onChange={(event) => onUpdate('taskId', event.target.value)}
              required
            />
          </Field>
          <Field label="Task family">
            <Input
              value={values.taskFamily}
              onChange={(event) => onUpdate('taskFamily', event.target.value)}
              required
            />
          </Field>
          <Field
            label="Permitted tools"
            help="Separate items with commas."
            className={styles.fieldFull}
          >
            <Input
              value={values.tools}
              onChange={(event) => onUpdate('tools', event.target.value)}
              required
            />
          </Field>
          <Field label="Instructional support" className={styles.fieldFull}>
            <Textarea
              value={values.support}
              onChange={(event) => onUpdate('support', event.target.value)}
              required
            />
          </Field>
          <Field label="Access conditions" className={styles.fieldFull}>
            <Textarea
              value={values.access}
              onChange={(event) => onUpdate('access', event.target.value)}
              required
            />
          </Field>
          <Checkbox
            className={styles.fieldFull}
            label="I verified that each access mode preserves the assessed construct."
            checked={values.accessVerified}
            onChange={(event) => onUpdate('accessVerified', event.target.checked)}
          />
          <Field label="Transfer rule" className={styles.fieldFull}>
            <Textarea
              value={values.transfer}
              onChange={(event) => onUpdate('transfer', event.target.value)}
              required
            />
          </Field>
        </div>
      </fieldset>
    </Card>
  )
}

export function AssessorSetupFields({
  values,
  assignments,
  lockedIdentity,
  onUpdate,
}: {
  values: SetupValues
  assignments: ScopedRoleAssignment[]
  lockedIdentity: boolean
  onUpdate: SetupUpdate
}) {
  return (
    <>
      <AssessmentTargetFields
        values={values}
        assignments={assignments}
        lockedIdentity={lockedIdentity}
        onUpdate={onUpdate}
      />
      <EvidenceRuleFields values={values} onUpdate={onUpdate} />
      <TaskConditionFields values={values} onUpdate={onUpdate} />
    </>
  )
}

function ApprovalHistory({ history }: { history: AssessmentDefinition[] }) {
  return (
    <ol className={styles.history} aria-label="Approval history">
      {history.map((item) => (
        <li key={item.id}>
          <strong>{item.approval_state === 'APPROVED' ? 'Published' : 'Draft'}</strong>
          <span>Version {item.version}</span>
          {item.approved_at && (
            <span>Approved {new Date(item.approved_at).toLocaleString()}</span>
          )}
        </li>
      ))}
    </ol>
  )
}

export function AssessorSetupApproval({
  definition,
  values,
  history,
  stale,
  dirty,
  busy,
  onUpdate,
  onLoadHistory,
  onPublish,
}: {
  definition: AssessmentDefinition | null
  values: SetupValues
  history: AssessmentDefinition[]
  stale: boolean
  dirty: boolean
  busy: 'save' | 'publish' | 'history' | 'access' | null
  onUpdate: SetupUpdate
  onLoadHistory: () => void
  onPublish: () => void
}) {
  return (
    <Card eyebrow="Assessor decision" heading="Approval and history">
      {!definition ? (
        <p className={styles.muted}>Save a complete draft before it can be approved.</p>
      ) : (
        <div className={styles.approval}>
          <p className={styles.approvalStatus}>
            <strong>Status:</strong>{' '}
            {definition.approval_state === 'APPROVED' ? 'Published' : 'Draft'}
          </p>
          {dirty && (
            <p className={styles.muted} role="note">
              Save the current changes as a new draft version before publishing.
            </p>
          )}
          <Field label="Approval reason">
            <Textarea
              value={values.approvalReason}
              onChange={(event) => onUpdate('approvalReason', event.target.value)}
              required
            />
          </Field>
          <div className={styles.actions}>
            <Button
              variant="secondary"
              onClick={onLoadHistory}
              disabled={busy === 'history'}
            >
              {busy === 'history' ? 'Loading history...' : 'Reload server history'}
            </Button>
            <Button
              variant="primary"
              onClick={onPublish}
              disabled={
                busy === 'publish'
                || definition.approval_state === 'APPROVED'
                || dirty
              }
            >
              {busy === 'publish' ? 'Publishing...' : 'Approve and publish'}
            </Button>
          </div>
          {stale && (
            <section className={styles.conflict} role="alert">
              <h3>Another version is available</h3>
              <p>
                Your local values have not been replaced. Reload server history to compare
                versions, then decide what to keep.
              </p>
              <details>
                <summary>Compare local draft</summary>
                <p><strong>Local claim:</strong> {values.claim}</p>
                <p><strong>Local criterion:</strong> {values.criterion}</p>
              </details>
            </section>
          )}
          <ApprovalHistory history={history} />
        </div>
      )}
    </Card>
  )
}
