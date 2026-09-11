import { useState } from 'react'
import type { ScopedRoleAssignment } from '../../app/types'
import { Button, PageHeader } from '../../components/ui'
import { AssessorSetupApproval, AssessorSetupFields } from './AssessorSetupPanels'
import { useAssessorSetup } from './useAssessorSetup'
import styles from './assessment.module.css'
import { AssessorDefinitionEditor } from './AssessorDefinitionEditor'

export function AssessorSetup({
  assignments,
  onCheckAccess,
  onAccessRevoked,
  initialDefinitionId,
  initialCourseId,
}: {
  assignments: ScopedRoleAssignment[]
  onCheckAccess: (courseId: string) => Promise<boolean>
  onAccessRevoked: () => void
  initialDefinitionId?: string
  initialCourseId?: string
}) {
  const [existing, setExisting] = useState(Boolean(initialDefinitionId))
  const [editorTarget, setEditorTarget] = useState({ courseId: initialCourseId, definitionId: initialDefinitionId, version: 0 })
  const setup = useAssessorSetup({ assignments, onCheckAccess, onAccessRevoked })
  const {
    assessorAssignments,
    values,
    definition,
    history,
    faults,
    status,
    serverError,
    stale,
    dirty,
    busy,
    update,
    saveDraft,
    loadHistory,
    publish,
    checkAccess,
  } = setup

  return (
    <div className={styles.screen}>
      <PageHeader
        eyebrow="Assessor workspace"
        title="Assessment setup"
        description="Set the approved evidence rules before learners begin an assessed task."
        actions={
          !existing && <Button
            variant="secondary"
            onClick={() => void checkAccess()}
            disabled={busy === 'access'}
          >
            Check assessor access
          </Button>
        }
      />
      <p className={styles.notice} role="note">
        <strong>Bloom is not a score.</strong> It names the evidence target. The approved criteria
        decide whether evidence meets the standard.
      </p>
      <Button variant="secondary" onClick={() => setExisting((current) => !current)}>
        {existing ? 'Set up a new assessment' : 'Edit an existing definition'}
      </Button>
      <div hidden={!existing}>
        <AssessorDefinitionEditor key={`${editorTarget.courseId}-${editorTarget.definitionId}-${editorTarget.version}`} assignments={assignments} initialDefinitionId={editorTarget.definitionId} initialCourseId={editorTarget.courseId} autoLoad={Boolean(editorTarget.definitionId && editorTarget.courseId)} onCheckAccess={onCheckAccess} onAccessRevoked={onAccessRevoked} />
      </div>
      {!existing && <div>
      {serverError && <p className={styles.alert} role="alert">{serverError}</p>}
      {status && <p className={styles.status} role="status">{status}</p>}
      {faults.length > 0 && (
        <section className={styles.alert} role="alert" aria-labelledby="assessment-faults">
          <h2 id="assessment-faults">Complete the setup</h2>
          <p>Missing: {faults.join(', ')}.</p>
        </section>
      )}
      <form className={styles.form} onSubmit={saveDraft} noValidate>
        <AssessorSetupFields
          values={values}
          assignments={assessorAssignments}
          lockedIdentity={definition !== null || busy === 'save'}
          onUpdate={update}
          onSaved={(saved) => {
            setEditorTarget({ courseId: saved.course_id, definitionId: saved.assessment_definition_id, version: saved.version })
            setExisting(true)
          }}
        />
        <div className={styles.actions}>
          <Button variant="primary" type="submit" disabled={busy === 'save'}>
            {busy === 'save' ? 'Saving draft...' : 'Save assessment draft'}
          </Button>
        </div>
      </form>
      {definition && <section aria-label="Complete approval policy">
        <p>Complete the feedback and adaptation plan in the definition editor before approval. Your saved criteria and policies will be loaded there.</p>
        {dirty && <p>Save your current changes before continuing to the definition editor.</p>}
        <Button variant="primary" disabled={Boolean(busy) || dirty || stale} onClick={() => {
          setEditorTarget({ courseId: definition.course_id, definitionId: definition.assessment_definition_id, version: definition.version })
          setExisting(true)
        }}>Complete feedback and adaptation in definition editor</Button>
      </section>}
      <AssessorSetupApproval
        definition={definition}
        values={values}
        history={history}
        stale={stale}
        dirty={dirty}
        busy={busy}
        onUpdate={update}
        onLoadHistory={() => void loadHistory()}
        onPublish={() => void publish()}
      />
      </div>}
    </div>
  )
}
