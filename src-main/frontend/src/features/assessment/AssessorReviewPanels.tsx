import { Check, CircleDot, HelpCircle } from 'lucide-react'
import type { ReactNode } from 'react'

import type { ScopedRoleAssignment } from '../../app/types'
import {
  AlertDialog,
  Button,
  Card,
  CodeBlock,
  DescriptionList,
  Field,
  Input,
  JudgeTag,
  LifecycleTag,
  ResultSeal,
  Select,
  cx,
} from '../../components/ui'
import type { ButtonVariant } from '../../components/ui'
import type {
  AssessmentResult,
  AssessmentReviewAction,
  AssessmentReviewDetail,
  ResultState,
} from './api'
import {
  actionLabels,
  criterionDecisionLabels,
  lifecycleLabels,
  readable,
  resultLabels,
} from './assessmentReviewPresentation'
import type { CriterionDecision } from './types'
import { assessmentResultValues, resultStateValues } from './types'
import styles from './assessment.module.css'

export type ReviewFilters = {
  courseId: string
  outcomeId: string
  result: '' | AssessmentResult
  resultState: '' | ResultState
  reviewFlag: string
  minimumAgeHours: string
}

export type PendingAction = {
  action: AssessmentReviewAction
  detail: AssessmentReviewDetail
}

/* Radix Select items cannot carry an empty value, so the "no filter" choice
   uses a sentinel that maps back to '' in the filter state. */
const allFilterValue = '__ALL__'

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return 'Not recorded'
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }
  return JSON.stringify(value)
}

/**
 * Structured payloads render as a readable DescriptionList with the exact JSON
 * behind a "View raw" disclosure (plan 006 Step 7 - replaces bare
 * JSON.stringify output).
 */
function StructuredValue({ value, label }: { value: unknown, label: string }) {
  if (value === null || value === undefined || value === '') return <p>Not recorded</p>
  if (typeof value !== 'object') return <p>{displayValue(value)}</p>
  const entries: [string, unknown][] = Array.isArray(value)
    ? value.map((item, index) => [`Item ${index + 1}`, item])
    : Object.entries(value)
  return (
    <div className={styles.structured}>
      {entries.length ? (
        <DescriptionList
          items={entries.map(([key, item]) => ({
            term: readable(key),
            description: displayValue(item),
          }))}
        />
      ) : (
        <p>Nothing recorded.</p>
      )}
      <details className={styles.raw}>
        <summary>View raw</summary>
        <CodeBlock code={JSON.stringify(value, null, 2)} label={`${label} raw data`} />
      </details>
    </div>
  )
}

const decisionChipClass: Record<CriterionDecision, string> = {
  MET: styles.chipMet,
  NOT_MET: styles.chipNotMet,
  NOT_EVALUABLE: styles.chipNotEvaluable,
}

const decisionChipIcon: Record<CriterionDecision, ReactNode> = {
  MET: <Check aria-hidden="true" />,
  NOT_MET: <CircleDot aria-hidden="true" />,
  NOT_EVALUABLE: <HelpCircle aria-hidden="true" />,
}

function DecisionChip({ decision }: { decision: CriterionDecision }) {
  return (
    <span className={cx(styles.chip, decisionChipClass[decision])}>
      {decisionChipIcon[decision]}
      {criterionDecisionLabels[decision]}
    </span>
  )
}

export function ReviewFiltersPanel({
  assignments,
  filters,
  summaries,
  loading,
  onUpdate,
  onRefresh,
}: {
  assignments: ScopedRoleAssignment[]
  filters: ReviewFilters
  summaries: { state: ResultState, count: number }[]
  loading: boolean
  onUpdate: <Key extends keyof ReviewFilters>(key: Key, value: ReviewFilters[Key]) => void
  onRefresh: () => void
}) {
  return (
    <Card eyebrow="Assigned course and review state" heading="Queue filters">
      <div className={styles.formGrid}>
        <Field label="Assigned course">
          <Select
            options={assignments.map((assignment) => ({
              value: assignment.course_id,
              label: assignment.course_id,
            }))}
            value={filters.courseId || undefined}
            onValueChange={(value) => onUpdate('courseId', value)}
            placeholder="Select an assigned course"
          />
        </Field>
        <Field label="Outcome ID">
          <Input
            value={filters.outcomeId}
            onChange={(event) => onUpdate('outcomeId', event.target.value)}
          />
        </Field>
        <Field label="Result">
          <Select
            options={[
              { value: allFilterValue, label: 'All results' },
              ...assessmentResultValues.map((result) => ({
                value: result,
                label: resultLabels[result],
              })),
            ]}
            value={filters.result || allFilterValue}
            onValueChange={(value) => onUpdate(
              'result',
              (value === allFilterValue ? '' : value) as ReviewFilters['result'],
            )}
          />
        </Field>
        <Field label="Result state">
          <Select
            options={[
              { value: allFilterValue, label: 'All result states' },
              ...resultStateValues.map((state) => ({
                value: state,
                label: lifecycleLabels[state],
              })),
            ]}
            value={filters.resultState || allFilterValue}
            onValueChange={(value) => onUpdate(
              'resultState',
              (value === allFilterValue ? '' : value) as ReviewFilters['resultState'],
            )}
          />
        </Field>
        <Field label="Review flag">
          <Input
            value={filters.reviewFlag}
            onChange={(event) => onUpdate('reviewFlag', event.target.value)}
          />
        </Field>
        <Field label="Minimum age in hours">
          <Input
            type="number"
            min="0"
            value={filters.minimumAgeHours}
            onChange={(event) => onUpdate('minimumAgeHours', event.target.value)}
          />
        </Field>
      </div>
      <div className={styles.actions}>
        <Button variant="primary" onClick={onRefresh} disabled={loading}>
          {loading ? 'Loading queue...' : 'Apply filters'}
        </Button>
      </div>
      <ul className={styles.summary} aria-label="Result state summary">
        {summaries.map(({ state, count }) => (
          <li key={state}><strong>{count}</strong><span>{lifecycleLabels[state]}</span></li>
        ))}
      </ul>
    </Card>
  )
}

function ReviewRecordList({
  records,
  selected,
  onSelect,
}: {
  records: AssessmentReviewDetail[]
  selected: AssessmentReviewDetail
  onSelect: (record: AssessmentReviewDetail) => void
}) {
  return (
    <ul className={styles.recordList}>
      {records.map((record) => (
        <li key={record.decision_id}>
          <button
            type="button"
            className={cx(
              styles.recordButton,
              record.decision_id === selected.decision_id && styles.recordActive,
            )}
            aria-pressed={record.decision_id === selected.decision_id}
            onClick={() => onSelect(record)}
          >
            <strong className={styles.recordOutcome}>{record.outcome_id}</strong>
            <span className={styles.recordStatus}>
              <LifecycleTag lifecycle={record.result_state} />
              {record.result && (
                <ResultSeal result={record.result} lifecycle={record.result_state} size="sm" />
              )}
            </span>
            <small className={styles.recordMeta}>Revision {record.review_revision}</small>
          </button>
        </li>
      ))}
    </ul>
  )
}

function EvidenceDetail({ selected }: { selected: AssessmentReviewDetail }) {
  const judgeDecision = selected.quality_review_status === 'APPROVED'
    || selected.quality_review_status === 'REJECTED'
    ? selected.quality_review_status
    : null
  return (
    <>
      <Card eyebrow="Read before acting" heading="Response and evidence">
        <div className={styles.detail}>
          <section className={styles.section}>
            <h3>System and Quality Review</h3>
            <p>
              <strong>System reason:</strong>{' '}
              <span className={styles.systemReason}>{selected.system_reason}</span>
            </p>
            {judgeDecision ? (
              <JudgeTag decision={judgeDecision} />
            ) : (
              <p>Quality review: {displayValue(selected.quality_review_status)}</p>
            )}
          </section>
          <section className={styles.section}>
            <h3>Original response</h3>
            <p>{selected.response_text || 'No response text was recorded.'}</p>
          </section>
        </div>
      </Card>
      <Card heading="Response conditions">
        <StructuredValue value={selected.response_conditions} label="Response conditions" />
      </Card>
      <Card heading="Criterion decisions">
        <ul className={styles.criterionList}>
          {selected.criteria.map((criterion) => (
            <li key={criterion.criterion_version_id} className={styles.criterionItem}>
              <DecisionChip decision={criterion.decision} />
              <p>{criterion.reason}</p>
              <StructuredValue
                value={criterion.evidence_references}
                label="Evidence references"
              />
              <small className={styles.recordMeta}>
                Criterion version {criterion.criterion_version}.
              </small>
              <small className={styles.provenance}>
                Evaluator: {criterion.evaluator_reference}. Model:{' '}
                {displayValue(criterion.model_version)}. Prompt:{' '}
                {displayValue(criterion.prompt_version)}. Retrieval:{' '}
                {displayValue(criterion.retrieval_version)}.
              </small>
            </li>
          ))}
        </ul>
      </Card>
      <Card heading="Missing evidence">
        {selected.missing_criterion_version_ids.length ? (
          <ul className={styles.missingList}>
            {selected.missing_criterion_version_ids.map((id) => <li key={id}>{id}</li>)}
          </ul>
        ) : (
          <p className={styles.muted}>No missing criteria were recorded.</p>
        )}
      </Card>
      <Card heading="Versions">
        <DescriptionList
          items={Object.entries(selected.versions).map(([key, value]) => ({
            term: readable(key),
            description: displayValue(value),
          }))}
        />
      </Card>
      <Card heading="Review history">
        {selected.history.length ? (
          <ol className={styles.historyList}>
            {selected.history.map((item) => (
              <li key={item.id}>
                <strong>{actionLabels[item.action]}</strong>, revision {item.review_revision}.{' '}
                {item.reason}
              </li>
            ))}
          </ol>
        ) : (
          <p className={styles.muted}>No assessor actions have been recorded.</p>
        )}
      </Card>
    </>
  )
}

/* Confirm affirms; Void is destructive; the rest are neutral secondary acts */
const actionVariants: Record<AssessmentReviewAction, ButtonVariant> = {
  CONFIRM: 'primary',
  OVERRIDE: 'secondary',
  WITHHOLD: 'secondary',
  VOID: 'danger',
  RETURN: 'secondary',
}

function ReviewActions({
  selected,
  accessActive,
  onOpenAction,
}: {
  selected: AssessmentReviewDetail
  accessActive: boolean
  onOpenAction: (action: AssessmentReviewAction) => void
}) {
  const actions: AssessmentReviewAction[] = [
    'CONFIRM',
    'OVERRIDE',
    'WITHHOLD',
    'VOID',
    'RETURN',
  ]
  return (
    <Card eyebrow="Record a reviewed decision" heading="Assessor action">
      <div className={styles.resultLine}>
        {selected.result ? (
          <ResultSeal result={selected.result} lifecycle={selected.result_state} size="sm" />
        ) : (
          <LifecycleTag lifecycle={selected.result_state} />
        )}
        <p className={styles.muted}>Every action needs a recorded reason.</p>
      </div>
      {accessActive ? (
        <div className={cx(styles.actions, styles.actionsStart)}>
          {actions.map((action) => (
            <Button
              key={action}
              variant={actionVariants[action]}
              data-review-action={action}
              onClick={() => onOpenAction(action)}
            >
              {actionLabels[action]}
            </Button>
          ))}
        </div>
      ) : (
        <p className={styles.alert} role="alert">
          Assessor access is no longer active. Action controls are unavailable.
        </p>
      )}
    </Card>
  )
}

export function ReviewWorkspace({
  records,
  selected,
  accessActive,
  onSelect,
  onOpenAction,
}: {
  records: AssessmentReviewDetail[]
  selected: AssessmentReviewDetail
  accessActive: boolean
  onSelect: (record: AssessmentReviewDetail) => void
  onOpenAction: (action: AssessmentReviewAction) => void
}) {
  return (
    <div className={styles.layout}>
      <Card eyebrow="Select a learner response" heading="Review records">
        <ReviewRecordList records={records} selected={selected} onSelect={onSelect} />
      </Card>
      <div className={styles.detail}>
        <EvidenceDetail selected={selected} />
        <ReviewActions
          selected={selected}
          accessActive={accessActive}
          onOpenAction={onOpenAction}
        />
      </div>
    </div>
  )
}

export function ReviewActionDialog({
  pendingAction,
  overrideResult,
  busy,
  error,
  status,
  onOverrideChange,
  onClose,
  onSubmit,
}: {
  pendingAction: PendingAction
  overrideResult: AssessmentResult
  busy: boolean
  error: string
  status: string
  onOverrideChange: (value: AssessmentResult) => void
  onClose: () => void
  onSubmit: (reason: string) => void
}) {
  const { action } = pendingAction
  return (
    <AlertDialog
      open
      onOpenChange={(open) => {
        if (!open && !busy) onClose()
      }}
      title={actionLabels[action]}
      description="Record why this action is appropriate for the response and evidence shown above."
      tone={action === 'VOID' ? 'danger' : 'default'}
      confirmLabel={actionLabels[action]}
      reasonLabel="Reason"
      confirmLoading={busy}
      onConfirm={(reason) => onSubmit(reason ?? '')}
    >
      <div className={styles.dialogExtras}>
        {action === 'OVERRIDE' && (
          <Field label="Replacement result">
            <Select
              options={assessmentResultValues.map((result) => ({
                value: result,
                label: resultLabels[result],
              }))}
              value={overrideResult}
              onValueChange={(value) => onOverrideChange(value as AssessmentResult)}
            />
          </Field>
        )}
        {/* The page-level messages are aria-hidden behind the modal, so they
            repeat here while the dialog is open. */}
        {error && <p className={styles.alert} role="alert">{error}</p>}
        {status && <p className={styles.status} role="status">{status}</p>}
      </div>
    </AlertDialog>
  )
}
