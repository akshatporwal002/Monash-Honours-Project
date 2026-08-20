import type { ScopedRoleAssignment } from '../../app/types'
import { Button, PageHeader } from '../../components/ui'
import { AssessorSetupApproval, AssessorSetupFields } from './AssessorSetupPanels'
import { useAssessorSetup } from './useAssessorSetup'
import styles from './assessment.module.css'

export function AssessorSetup({
  assignments,
  onCheckAccess,
  onAccessRevoked,
}: {
  assignments: ScopedRoleAssignment[]
  onCheckAccess: (courseId: string) => Promise<boolean>
  onAccessRevoked: () => void
}) {
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
          <Button
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
        />
        <div className={styles.actions}>
          <Button variant="primary" type="submit" disabled={busy === 'save'}>
            {busy === 'save' ? 'Saving draft...' : 'Save assessment draft'}
          </Button>
        </div>
      </form>
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
    </div>
  )
}
