import type { ScopedRoleAssignment } from '../../app/types'
import { Panel } from '../../components/ScreenPrimitives'
import type { AssessmentDefinition } from './api'
import type { SetupValues } from './assessmentDraft'
import { assessmentPurposeValues, bloomKnowledgeValues, bloomProcessValues } from './types'

export type SetupUpdate = <Key extends keyof SetupValues>(
  key: Key,
  value: SetupValues[Key],
) => void

function label(value: string): string {
  return value.toLowerCase().replaceAll('_', ' ')
}

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
    <Panel title="Assessment target" eyebrow="Outcome and source">
      <div className="assessment-form-grid">
        <label className="field">
          <span>Assigned course</span>
          <select
            aria-label="Assigned course"
            value={values.courseId}
            onChange={(event) => onUpdate('courseId', event.target.value)}
            aria-describedby="course-help"
            disabled={lockedIdentity}
          >
            <option value="">Select an assigned course</option>
            {assignments.map((assignment) => (
              <option key={assignment.id} value={assignment.course_id}>
                {assignment.course_id}
              </option>
            ))}
          </select>
          <small id="course-help">Only courses in your active assessor assignment are available.</small>
        </label>
        <label className="field">
          <span>Outcome ID</span>
          <input
            aria-label="Outcome ID"
            value={values.outcomeId}
            onChange={(event) => onUpdate('outcomeId', event.target.value)}
            disabled={lockedIdentity}
            required
          />
        </label>
        <label className="field field--full">
          <span>Outcome wording</span>
          <textarea
            aria-label="Outcome wording"
            value={values.outcome}
            onChange={(event) => onUpdate('outcome', event.target.value)}
            required
          />
        </label>
        <label className="field">
          <span>Source</span>
          <input
            aria-label="Source"
            value={values.source}
            onChange={(event) => onUpdate('source', event.target.value)}
            required
          />
        </label>
        <label className="field">
          <span>Source version</span>
          <input
            aria-label="Source version"
            value={values.sourceVersion}
            onChange={(event) => onUpdate('sourceVersion', event.target.value)}
            required
          />
        </label>
        <label className="field field--full">
          <span>Source digest</span>
          <input
            aria-label="Source digest"
            value={values.sourceDigest}
            onChange={(event) => onUpdate('sourceDigest', event.target.value)}
            required
          />
        </label>
      </div>
    </Panel>
  )
}

function EvidenceRuleFields({ values, onUpdate }: { values: SetupValues, onUpdate: SetupUpdate }) {
  return (
    <Panel title="Evidence and pass rule" eyebrow="Bloom target">
      <div className="assessment-form-grid">
        <label className="field">
          <span>Bloom process</span>
          <select
            aria-label="Bloom process"
            value={values.bloomProcess}
            onChange={(event) => (
              onUpdate('bloomProcess', event.target.value as SetupValues['bloomProcess'])
            )}
          >
            {bloomProcessValues.map((value) => (
              <option key={value} value={value}>{label(value)}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Knowledge dimension</span>
          <select
            aria-label="Knowledge dimension"
            value={values.knowledgeDimension}
            onChange={(event) => (
              onUpdate(
                'knowledgeDimension',
                event.target.value as SetupValues['knowledgeDimension'],
              )
            )}
          >
            {bloomKnowledgeValues.map((value) => (
              <option key={value} value={value}>{label(value)}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Assessment purpose</span>
          <select
            aria-label="Assessment purpose"
            value={values.purpose}
            onChange={(event) => (
              onUpdate('purpose', event.target.value as SetupValues['purpose'])
            )}
          >
            {assessmentPurposeValues.map((value) => (
              <option key={value} value={value}>{label(value)}</option>
            ))}
          </select>
        </label>
        <label className="field field--full">
          <span>Claim</span>
          <textarea
            aria-label="Claim"
            value={values.claim}
            onChange={(event) => onUpdate('claim', event.target.value)}
            required
          />
        </label>
        <label className="field field--full">
          <span>Required evidence</span>
          <textarea
            aria-label="Required evidence"
            value={values.evidence}
            onChange={(event) => onUpdate('evidence', event.target.value)}
            required
          />
        </label>
        <label className="field field--full">
          <span>Mandatory criterion</span>
          <textarea
            aria-label="Mandatory criterion"
            value={values.criterion}
            onChange={(event) => onUpdate('criterion', event.target.value)}
            required
          />
        </label>
        <label className="field field--full">
          <input
            aria-label="Verified Bloom elicitation"
            type="checkbox"
            checked={values.bloomVerified}
            onChange={(event) => onUpdate('bloomVerified', event.target.checked)}
          />
          <span>I verified that this task elicits the selected Bloom process.</span>
        </label>
      </div>
      <aside className="assessment-pass-rule" aria-label="Pass rule preview">
        <h3>Pass rule preview</h3>
        <p>Pass when every mandatory criterion is met for the selected Bloom target.</p>
        <p>Each listed mandatory criterion must be met.</p>
      </aside>
    </Panel>
  )
}

function TaskConditionFields({ values, onUpdate }: { values: SetupValues, onUpdate: SetupUpdate }) {
  return (
    <Panel title="Task conditions" eyebrow="Form, tools, and access">
      <div className="assessment-form-grid">
        <label className="field">
          <span>Task form ID</span>
          <input
            aria-label="Task form ID"
            value={values.taskId}
            onChange={(event) => onUpdate('taskId', event.target.value)}
            required
          />
        </label>
        <label className="field">
          <span>Task family</span>
          <input
            aria-label="Task family"
            value={values.taskFamily}
            onChange={(event) => onUpdate('taskFamily', event.target.value)}
            required
          />
        </label>
        <label className="field field--full">
          <span>Permitted tools</span>
          <input
            aria-label="Permitted tools"
            value={values.tools}
            onChange={(event) => onUpdate('tools', event.target.value)}
            required
          />
          <small>Separate items with commas.</small>
        </label>
        <label className="field field--full">
          <span>Instructional support</span>
          <textarea
            aria-label="Instructional support"
            value={values.support}
            onChange={(event) => onUpdate('support', event.target.value)}
            required
          />
        </label>
        <label className="field field--full">
          <span>Access conditions</span>
          <textarea
            aria-label="Access conditions"
            value={values.access}
            onChange={(event) => onUpdate('access', event.target.value)}
            required
          />
        </label>
        <label className="field field--full">
          <input
            aria-label="Verified construct-preserving access"
            type="checkbox"
            checked={values.accessVerified}
            onChange={(event) => onUpdate('accessVerified', event.target.checked)}
          />
          <span>I verified that each access mode preserves the assessed construct.</span>
        </label>
        <label className="field field--full">
          <span>Transfer rule</span>
          <textarea
            aria-label="Transfer rule"
            value={values.transfer}
            onChange={(event) => onUpdate('transfer', event.target.value)}
            required
          />
        </label>
      </div>
    </Panel>
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
    <ol className="assessment-history" aria-label="Approval history">
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
    <Panel title="Approval and history" eyebrow="Assessor decision">
      {!definition ? (
        <p className="assessment-muted">Save a complete draft before it can be approved.</p>
      ) : (
        <div className="assessment-approval">
          <p>
            <strong>Status:</strong>{' '}
            {definition.approval_state === 'APPROVED' ? 'Published' : 'Draft'}
          </p>
          {dirty && (
            <p className="assessment-muted" role="note">
              Save the current changes as a new draft version before publishing.
            </p>
          )}
          <label className="field">
            <span>Approval reason</span>
            <textarea
              aria-label="Approval reason"
              value={values.approvalReason}
              onChange={(event) => onUpdate('approvalReason', event.target.value)}
              required
            />
          </label>
          <div className="assessment-actions">
            <button
              className="button button--secondary"
              onClick={onLoadHistory}
              disabled={busy === 'history'}
            >
              {busy === 'history' ? 'Loading history...' : 'Reload server history'}
            </button>
            <button
              className="button button--primary"
              onClick={onPublish}
              disabled={
                busy === 'publish'
                || definition.approval_state === 'APPROVED'
                || dirty
              }
            >
              {busy === 'publish' ? 'Publishing...' : 'Approve and publish'}
            </button>
          </div>
          {stale && (
            <section className="assessment-conflict" role="alert">
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
    </Panel>
  )
}
