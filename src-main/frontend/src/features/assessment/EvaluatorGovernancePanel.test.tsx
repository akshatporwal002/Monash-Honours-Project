import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { EvaluatorGovernancePanel } from './EvaluatorGovernancePanel'
import { AssessorSuggestionPanel } from './AssessorSuggestionPanel'

afterEach(() => vi.restoreAllMocks())

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}
const status = { state: 'VALIDATED', validation_id: 'validation-1', fingerprint: 'a'.repeat(64), reason: 'Evidence recorded', ai_activation: 'PENDING' }
const governance = { status, forms: [{ id: 'form-1', title: 'Quantum task', version: 2, approved: true }], history: [{ id: 'validation-1', revision: 1, state: 'VALIDATED', reason: 'Evidence recorded', actor_id: 1, created_at: '2026-09-11T00:00:00Z', expires_at: '2026-09-15T00:00:00Z', evidence: { assessment_gate: { experts: [{ name: 'Named expert', training_reference: 'Training record' }] } } }] }

test('administrator records a separate exact-form release from explicitly supplied authority', async () => {
  const writes: Record<string, unknown>[] = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (_, init) => {
    if (init?.method === 'POST') { writes.push(JSON.parse(String(init.body))); return response({}) }
    return response(governance)
  })
  const user = userEvent.setup()
  render(<EvaluatorGovernancePanel courseId="course-1" />)
  await screen.findByText(/Suggestions: PENDING/)
  await user.click(screen.getByText('Evidence references'))
  expect(screen.getByText('Training record')).toBeVisible()
  await user.click(screen.getByText('Record a signed release'))
  expect(screen.getByRole('button', { name: 'Record signed release' })).toBeDisabled()
  for (const [label, value] of Object.entries({
    'Release authority name': 'Appointed authority', 'Release authority role': 'Course director',
    'Signed release reference': 'Signed decision 123', 'Approved provider': 'local', 'Approved model': 'recorded-model',
    'Approved prompt version': 'prompt-2', 'Approved retrieval version': 'retrieval-3',
  })) await user.type(screen.getByLabelText(label), value)
  // Native datetime inputs are set through their actual change event.
  fireEvent.change(screen.getByLabelText('Release approved at'), { target: { value: '2026-09-11T12:00' } })
  fireEvent.change(screen.getByLabelText('Release expires at'), { target: { value: '2026-09-12T12:00' } })
  await user.click(screen.getByLabelText('Quantum task, version 2'))
  await user.click(screen.getByRole('button', { name: 'Record signed release' }))
  await screen.findByText(/Decision recorded/)
  expect(writes).toHaveLength(1)
  expect(writes[0]).toMatchObject({ validation_id: 'validation-1', expected_fingerprint: status.fingerprint, task_form_version_ids: ['form-1'], approval_reference: 'Signed decision 123', authority_name: 'Appointed authority' })
  expect(writes[0].idempotency_key).toEqual(expect.any(String))
})

test('course switch discards a late validation response', async () => {
  let resolveFirst!: (value: Response) => void
  vi.spyOn(globalThis, 'fetch').mockImplementation(async input => String(input).includes('course-1')
    ? new Promise(resolve => { resolveFirst = resolve })
    : response({ ...governance, status: { ...status, reason: 'Second course' } }))
  const view = render(<EvaluatorGovernancePanel courseId="course-1" />)
  view.rerender(<EvaluatorGovernancePanel courseId="course-2" />)
  await screen.findByText(/Second course/)
  await act(async () => resolveFirst(response({ ...governance, status: { ...status, reason: 'First course private record' } })))
  expect(screen.queryByText(/First course private record/)).not.toBeInTheDocument()
})

test('permission loss clears retained governance records and supports reload', async () => {
  let allowed = true
  vi.spyOn(globalThis, 'fetch').mockImplementation(async () => allowed ? response(governance) : response({ detail: 'Access withdrawn' }, 403))
  const user = userEvent.setup()
  render(<EvaluatorGovernancePanel courseId="course-1" />)
  await screen.findByText(/Suggestions: PENDING/)
  allowed = false
  await user.click(screen.getByRole('button', { name: 'Reload validation history' }))
  await screen.findByRole('alert')
  expect(screen.queryByText('Named expert')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Record validation evidence' })).not.toBeInTheDocument()
})

test('independent moderation does not request or show AI suggestions', () => {
  const fetch = vi.spyOn(globalThis, 'fetch')
  render(<AssessorSuggestionPanel attemptId="attempt-1" independent />)
  expect(screen.getByText(/not displayed during independent moderation/)).toBeVisible()
  expect(fetch).not.toHaveBeenCalled()
})

test('assessor suggestions are read-only and disappear after release revocation is reloaded', async () => {
  let released = true
  vi.spyOn(globalThis, 'fetch').mockImplementation(async () => response(released ? {
    status: 'RELEASED', reason: 'Human confirmation required', records: [{ id: 'output-1', recorded_by: 7, output: { output_reference: 'Retained output', provider: 'local', model: 'model', generated_at: '2026-09-11T00:00:00Z', criteria: [{ criterion_version_id: 'criterion-1', decision: 'MET', reason: 'Advisory reasoning', evidence_ids: ['response-1'] }] } }],
  } : { status: 'PENDING', reason: 'Release revoked', records: [] }))
  const user = userEvent.setup()
  render(<AssessorSuggestionPanel attemptId="attempt-1" independent={false} />)
  await user.click(screen.getByRole('button', { name: 'Open AI suggestion records' }))
  expect(await screen.findByText('Suggested MET')).toBeVisible()
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  released = false
  await user.click(screen.getByRole('button', { name: 'Reload suggestion records' }))
  await screen.findByText(/Release revoked/)
  expect(screen.queryByText('Suggested MET')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Import suggestion record' })).not.toBeInTheDocument()
})

test('validation packet fingerprint mismatch cannot be submitted', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(response(governance))
  const user = userEvent.setup()
  render(<EvaluatorGovernancePanel courseId="course-1" />)
  await screen.findByText(/Suggestions: PENDING/)
  const file = new File(['ignored'], 'validation.json', { type: 'application/json' })
  Object.defineProperty(file, 'text', { value: async () => JSON.stringify({ expected_fingerprint: 'b'.repeat(64), expires_at: '2026-09-15T00:00:00Z', evidence: {} }) })
  await user.upload(screen.getByLabelText('Validation packet'), file)
  await waitFor(() => expect(screen.getByText(/Fingerprint differs/)).toBeVisible())
  expect(screen.getByRole('button', { name: 'Record validation evidence' })).toBeDisabled()
})

test('actual output import requires explicit findings for all ten quality dimensions', async () => {
  const writes: { path: string; body: Record<string, unknown> }[] = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const path = String(input)
    if (init?.method === 'POST') {
      writes.push({ path, body: JSON.parse(String(init.body)) })
      return response(path.endsWith('quality-context') ? {
        request_digest: 'c'.repeat(64), reviewer: { kind: 'human', reference: 'user:7', version: 'fr17-complete-review.v1' },
        request: { output: { reason: 'Candidate for review' }, evidence: [{ reference: 'response-1', content: 'Frozen response' }] },
      } : { quality_decision: 'REJECTED' })
    }
    return response({ status: 'RELEASED', reason: 'Human confirmation required', records: [] })
  })
  const user = userEvent.setup()
  render(<AssessorSuggestionPanel attemptId="attempt-1" independent={false} />)
  await user.click(screen.getByRole('button', { name: 'Open AI suggestion records' }))
  const file = new File(['ignored'], 'actual-output.json', { type: 'application/json' })
  Object.defineProperty(file, 'text', { value: async () => JSON.stringify({ idempotency_key: 'recorded-1', release_id: 'release-1' }) })
  await user.upload(await screen.findByLabelText('Recorded AI output'), file)
  await user.click(screen.getByRole('button', { name: 'Prepare output quality review' }))
  await screen.findByText('Candidate output quality review')
  expect(screen.getAllByRole('combobox')).toHaveLength(10)
  expect(screen.getAllByRole('combobox').every(select => (select as HTMLSelectElement).value === '')).toBe(true)
  for (const select of screen.getAllByRole('combobox')) fireEvent.change(select, { target: { value: 'UNVERIFIED' } })
  for (const reason of screen.getAllByRole('textbox')) fireEvent.change(reason, { target: { value: 'Insufficient evidence to establish this dimension.' } })
  await user.click(screen.getByRole('button', { name: 'Record quality review and import' }))
  await screen.findByText(/Quality review: REJECTED/)
  expect(writes).toHaveLength(2)
  expect(writes[1].body).toMatchObject({ quality_review: { request_digest: 'c'.repeat(64), reviewer: { reference: 'user:7' }, findings: expect.arrayContaining([{ dimension: 'factual_accuracy', outcome: 'UNVERIFIED', basis: 'human', reason: 'Insufficient evidence to establish this dimension.', evidence_references: [] }]) } })
  expect(writes.every(write => write.path.includes('/ai-suggestions'))).toBe(true)
  expect(screen.queryByText('Suggested MET')).not.toBeInTheDocument()
})
