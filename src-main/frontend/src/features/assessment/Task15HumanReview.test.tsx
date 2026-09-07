import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AssessorReviewUnresolved } from './AssessorReviewUnresolved'
import { AssessorReviewResponse } from './AssessorReviewResponse'
import { humanReviewApi } from './assessmentReviewApi'
import type { UnresolvedAssessment } from './assessmentReviewApi'

vi.mock('./assessmentReviewApi', () => ({ humanReviewApi: { queue: vi.fn(), detail: vi.fn(), finalise: vi.fn() } }))

const record: UnresolvedAssessment = {
  assessment_attempt_id: 'attempt-15', course_id: 'course-15', state: 'PENDING',
  job_state: 'review_required', failure_category: 'provider_unavailable', expected_token: 'a'.repeat(64),
  response: null, response_history: [], versions: {}, simulations: [], history: [], issues: [], can_finalise: true,
  created_at: '2026-09-07T00:00:00Z',
  criteria: [{ criterion_version_id: 'criterion-15', criterion_version: 1, learner_description: 'Explain your circuit choice',
    evidence_description: 'A causal account of the selected operation', mandatory: true, evidence_source_types: ['learner_response'],
    met_rule: 'The cause is linked to its effect', not_met_rule: 'No causal account', not_evaluable_rule: 'Missing evidence',
    approved_anchors: { example: 'Approved explanation' }, critical_error_rules: {}, evaluator_type: 'human', decision: null, reason: null }],
}

function frozenRecord(): UnresolvedAssessment {
  return { ...record, response: {
    assessment_work_start_id: 'work-15', task_form_version_id: 'form-15',
    declared_conditions: { accessibility: 'keyboard', hints: 'unlimited' },
    reference: { assessment: { assessment_attempt_id: 'attempt-15', response_version_id: 'response-15', course_id: 'course-15',
      assessment_definition_id: 'definition', assessment_definition_version: 1, outcome_id: 'outcome', outcome_version: 1,
      bloom_target_id: 'bloom', bloom_target_version: 1, criterion_set_id: 'criteria', criterion_set_version: 1,
      pass_rule_id: 'rule', pass_rule_version: 1, task_id: 'task', task_form_version: 1 },
      evidence_id: 'response-15', evidence_type: 'learner_response', schema_version: 'assessment.response.v2', record_version: 1,
      content_digest: `sha256:${'a'.repeat(64)}`, source_record_id: 'response-15', source_record_version: 1, occurred_at: '2026-09-07T00:00:00Z' },
    content: { answer: 'Supported answer', code: 'if ready:\n    apply_h()', circuit: { qubits: 1, operations: [{ gate: 'h', targets: [0] }] } },
    episode: { supported: { prediction: { answer: 'My original prediction' }, reasoning: 'My reasoning', explanation: 'My explanation', reflection: 'My reflection' },
      transfer: { stage_start_id: 'transfer-start', part_id: 'fresh', content: { answer: 'Fresh independent answer' }, process: { explanation: 'Fresh explanation' } } },
  } }
}

beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(humanReviewApi.queue).mockResolvedValue([frozenRecord()])
  vi.mocked(humanReviewApi.detail).mockResolvedValue(frozenRecord())
  vi.mocked(humanReviewApi.finalise).mockResolvedValue({ action_id: 'human-15', assessment_attempt_id: 'attempt-15', decision_id: 'decision-15', result: 'PASS', result_state: 'CONFIRMED', revision: 1, replayed: false })
})

describe('Task 15 human assessment', () => {
  it('shows full frozen content with explicit stage labels and formatted code', () => {
    render(<AssessorReviewResponse response={frozenRecord().response} />)
    expect(screen.getByText('My original prediction')).toBeInTheDocument()
    expect(screen.getByText('Fresh independent answer')).toBeInTheDocument()
    expect(screen.getByText('My reasoning')).toBeInTheDocument()
    expect(screen.getByText('My reflection')).toBeInTheDocument()
    expect(screen.getByText(/if ready:/)).toHaveTextContent('if ready:')
    expect(screen.getByLabelText('Submitted circuit data')).toBeInTheDocument()
  })

  it('requires human criterion entries and confirms the frozen pass rule', async () => {
    const finalised = vi.fn()
    render(<AssessorReviewUnresolved courseId="course-15" onCheckAccess={vi.fn().mockResolvedValue(true)} onAccessRevoked={vi.fn()} onFinalised={finalised} />)
    fireEvent.click(await screen.findByRole('button', { name: /Inspect attempt/ }))
    await screen.findByText('My original prediction')
    const group = screen.getByRole('group', { name: 'Explain your circuit choice (required)' })
    expect(within(group).getByText('Approved anchors and critical error rules')).toBeInTheDocument()
    fireEvent.change(within(group).getByRole('combobox'), { target: { value: 'MET' } })
    fireEvent.change(within(group).getByLabelText(/Criterion reason/), { target: { value: 'The explanation links the chosen gate to the prediction.' } })
    fireEvent.click(within(group).getByRole('checkbox'))
    fireEvent.change(screen.getByLabelText('Formal confirmation reason'), { target: { value: 'I inspected the complete evidence.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Apply frozen pass rule and confirm result' }))
    await waitFor(() => expect(humanReviewApi.finalise).toHaveBeenCalledTimes(1))
    expect(vi.mocked(humanReviewApi.finalise).mock.calls[0][1]).toMatchObject({ expected_token: 'a'.repeat(64), criteria: [{ decision: 'MET', evidence_ids: ['response-15'] }] })
    await screen.findByText(/Formal result PASS confirmed/)
    expect(finalised).toHaveBeenCalledTimes(1)
  })

  it('keeps technical faults visible and disables result writes', async () => {
    vi.mocked(humanReviewApi.detail).mockResolvedValue({ ...frozenRecord(), issues: ['Simulation timed out. Keep this attempt under review.'], can_finalise: false })
    render(<AssessorReviewUnresolved courseId="course-15" onCheckAccess={vi.fn().mockResolvedValue(true)} onAccessRevoked={vi.fn()} onFinalised={vi.fn()} />)
    fireEvent.click(await screen.findByRole('button', { name: /Inspect attempt/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Simulation timed out')
    expect(screen.getByRole('button', { name: 'Apply frozen pass rule and confirm result' })).toBeDisabled()
    expect(humanReviewApi.finalise).not.toHaveBeenCalled()
  })

  it('removes saved evidence when current assessor access is revoked', async () => {
    const access = vi.fn().mockResolvedValue(true)
    const revoked = vi.fn()
    render(<AssessorReviewUnresolved courseId="course-15" onCheckAccess={access} onAccessRevoked={revoked} onFinalised={vi.fn()} />)
    fireEvent.click(await screen.findByRole('button', { name: /Inspect attempt/ }))
    await screen.findByText('My original prediction')
    access.mockResolvedValue(false)
    fireEvent.click(screen.getByRole('button', { name: 'Reload unresolved work' }))
    await waitFor(() => expect(revoked).toHaveBeenCalled())
    expect(screen.queryByText('My original prediction')).not.toBeInTheDocument()
  })
  it('opens criterion entry for the selected existing formal record', async () => {
    render(<AssessorReviewUnresolved courseId="course-15" reviewedAttemptId="previous-attempt" onCheckAccess={vi.fn().mockResolvedValue(true)} onAccessRevoked={vi.fn()} onFinalised={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: 'Record or correct criteria for the selected review record' }))
    await screen.findByText('My original prediction')
    expect(humanReviewApi.detail).toHaveBeenCalledWith('previous-attempt')
  })

  it('loads later unresolved attempts through the bounded queue API', async () => {
    vi.mocked(humanReviewApi.queue).mockResolvedValueOnce(Array.from({ length: 50 }, (_, index) => ({ ...record, assessment_attempt_id: `attempt-${index}` }))).mockResolvedValueOnce([{ ...record, assessment_attempt_id: 'attempt-51' }])
    render(<AssessorReviewUnresolved courseId="course-15" onCheckAccess={vi.fn().mockResolvedValue(true)} onAccessRevoked={vi.fn()} onFinalised={vi.fn()} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Load more unresolved attempts' }))
    await screen.findByRole('button', { name: /Inspect attempt attempt-51/ })
    expect(humanReviewApi.queue).toHaveBeenLastCalledWith('course-15', 50)
    expect(screen.queryByRole('button', { name: 'Load more unresolved attempts' })).not.toBeInTheDocument()
  })

})

