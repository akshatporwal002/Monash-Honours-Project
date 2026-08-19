import axe from 'axe-core'
import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import type { ApiSchemas } from '../../api/generated'
import { AssessorReviewQueue } from './AssessorReviewQueue'

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

const assignments = [{
  id: 'assignment-1', course_id: 'course-1', role: 'assessor' as const, version: 1,
  valid_from: '2026-08-16T00:00:00Z', valid_until: null,
}]

const review: ApiSchemas['AssessmentReviewDetailRead'] = {
  decision_id: 'decision-1', course_id: 'course-1', outcome_id: 'outcome-1',
  response_text: 'The learner applied the Hadamard gate and explained superposition.',
  response_conditions: { task_form: 'circuit-v2' }, result: 'INCOMPLETE' as const,
  result_state: 'PROVISIONAL' as const, system_reason: 'CRITERIA_NOT_MET',
  review_revision: 2, quality_review_status: 'APPROVED', versions: { criterion_set: 4, task_form: 2 },
  criteria: [{ criterion_version_id: 'criterion-1', criterion_version: 4, decision: 'NOT_MET',
    reason: 'The explanation does not describe the measured state.', evidence_references: { response_span: '1:24' },
    evaluator_reference: 'criterion-engine', model_version: 'model-1', prompt_version: 'prompt-1', retrieval_version: 'source-1' }],
  missing_criterion_version_ids: ['criterion-2'],
  history: [{ id: 'history-1', review_revision: 1, assessor_user_id: 7, action: 'WITHHOLD', prior_result: null,
    new_result: null, reason: 'Awaiting source review.', reviewed_at: '2026-08-16T00:00:00Z' }],
  created_at: '2026-08-16T00:00:00Z',
}

function installQueueFetch(overrides: {
  actionStatuses?: number[]
  actionError?: Error
  queueDetail?: ApiSchemas['AssessmentReviewDetailRead']
  detail?: ApiSchemas['AssessmentReviewDetailRead']
} = {}) {
  let actionIndex = 0
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input)
    if (url.includes('/review-queue')) return response([overrides.queueDetail ?? review])
    if (url.includes('/decisions/decision-1/review') && init?.method === 'POST') {
      if (overrides.actionError) throw overrides.actionError
      const status = overrides.actionStatuses?.[actionIndex] ?? 200
      actionIndex += 1
      return response({ decision_id: 'decision-1', review_id: 'history-2', result: 'INCOMPLETE', result_state: 'CONFIRMED', review_revision: 3, replayed: false }, status)
    }
    if (url.includes('/decisions/decision-1/review')) return response(overrides.detail ?? { ...review, review_revision: 3 })
    throw new Error(`Unexpected request: ${url}`)
  })
}

function renderQueue(overrides: Partial<Parameters<typeof AssessorReviewQueue>[0]> = {}) {
  return render(<AssessorReviewQueue assignments={assignments} onCheckAccess={async () => true} onAccessRevoked={() => undefined} {...overrides} />)
}

beforeEach(() => vi.restoreAllMocks())

test('review queue shows evidence before decision controls', async () => {
  installQueueFetch()
  renderQueue()

  const responseHeading = await screen.findByRole('heading', { name: 'Response and evidence' })
  expect(screen.getByText('The learner applied the Hadamard gate and explained superposition.')).toBeInTheDocument()
  expect(screen.getByText('The explanation does not describe the measured state.')).toBeInTheDocument()
  expect(screen.getByText('criterion-2')).toBeInTheDocument()
  expect(screen.getByText('criterion set')).toBeInTheDocument()
  expect(screen.getByText('CRITERIA_NOT_MET')).toBeInTheDocument()
  expect(screen.getByText('approved')).toBeInTheDocument()
  expect(screen.getByText(/Evaluator: criterion-engine/)).toBeInTheDocument()
  const actionHeading = screen.getByRole('heading', { name: 'Assessor action' })
  expect(responseHeading.compareDocumentPosition(actionHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
})

test('override void withhold and return require a reason', async () => {
  installQueueFetch()
  const user = userEvent.setup()
  renderQueue()
  await screen.findByRole('button', { name: 'Override result' })

  for (const label of ['Confirm result', 'Override result', 'Void result', 'Withhold result', 'Return for review']) {
    await user.click(screen.getByRole('button', { name: label }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: label }))
    expect(screen.getByRole('alert')).toHaveTextContent('Record a reason before submitting')
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }))
  }
})

test('stale review keeps typed reason and reloads current state', async () => {
  const current = { ...review, review_revision: 3, history: [...review.history, {
    id: 'history-2', review_revision: 2, assessor_user_id: 8, action: 'CONFIRM' as const, prior_result: 'INCOMPLETE' as const,
    new_result: 'INCOMPLETE' as const, reason: 'Another assessor confirmed.', reviewed_at: '2026-08-16T00:10:00Z',
  }] }
  const fetchSpy = installQueueFetch({ actionStatuses: [409, 200], queueDetail: review, detail: current })
  const user = userEvent.setup()
  renderQueue()
  await screen.findByRole('button', { name: 'Confirm result' })
  await user.click(screen.getByRole('button', { name: 'Confirm result' }))
  const dialog = await screen.findByRole('dialog')
  await user.type(within(dialog).getByLabelText('Reason'), 'Evidence was independently checked.')
  await user.click(within(dialog).getByRole('button', { name: 'Confirm result' }))

  expect(await screen.findByRole('status')).toHaveTextContent('Current history was reloaded')
  expect(within(dialog).getByDisplayValue('Evidence was independently checked.')).toBeInTheDocument()
  expect(screen.getByText((_, element) => element?.tagName === 'LI'
    && element.textContent?.includes('Another assessor confirmed.') === true)).toBeInTheDocument()
  await user.click(within(dialog).getByRole('button', { name: 'Confirm result' }))
  expect(await screen.findByRole('status')).toHaveTextContent('Confirm result recorded')
  const actionBodies = fetchSpy.mock.calls
    .filter(([input, init]) => String(input).includes('/decisions/decision-1/review') && init?.method === 'POST')
    .map(([, init]) => JSON.parse(String(init?.body)))
  expect(actionBodies.map((body) => body.expected_review_revision)).toEqual([2, 3])
})

test('revoked assessor cannot use cached action controls', async () => {
  installQueueFetch()
  const user = userEvent.setup()
  const onAccessRevoked = vi.fn()
  const onCheckAccess = vi.fn().mockResolvedValueOnce(true).mockResolvedValue(false)
  renderQueue({ onCheckAccess, onAccessRevoked })
  await screen.findByRole('button', { name: 'Confirm result' })
  await user.click(screen.getByRole('button', { name: 'Confirm result' }))

  expect(onAccessRevoked).toHaveBeenCalledOnce()
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(screen.getByText('Assessor access has expired. Review action controls were removed.')).toBeInTheDocument()
  expect(screen.queryByRole('heading', { name: 'Response and evidence' })).not.toBeInTheDocument()
})

test('revoked assessor cannot reload cached review records', async () => {
  installQueueFetch()
  const user = userEvent.setup()
  const onAccessRevoked = vi.fn()
  const onCheckAccess = vi.fn().mockResolvedValueOnce(true).mockResolvedValue(false)
  renderQueue({ onCheckAccess, onAccessRevoked })
  await screen.findByRole('heading', { name: 'Response and evidence' })
  await user.click(screen.getByRole('button', { name: 'Reload queue' }))

  expect(onAccessRevoked).toHaveBeenCalledOnce()
  expect(screen.queryByRole('heading', { name: 'Response and evidence' })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Confirm result' })).not.toBeInTheDocument()
})

test('access refresh is scoped to the selected course when another assignment remains', async () => {
  const fetchSpy = installQueueFetch()
  const onAccessRevoked = vi.fn()
  const onCheckAccess = vi.fn(async (courseId: string) => courseId === 'course-2')
  renderQueue({
    assignments: [
      ...assignments,
      {
        id: 'assignment-2',
        course_id: 'course-2',
        role: 'assessor',
        version: 1,
        valid_from: '2026-08-16T00:00:00Z',
        valid_until: null,
      },
    ],
    onCheckAccess,
    onAccessRevoked,
  })

  expect(await screen.findByText(
    'Assessor access has expired. Review action controls were removed.',
  )).toBeInTheDocument()
  expect(onCheckAccess).toHaveBeenCalledWith('course-1')
  expect(onAccessRevoked).toHaveBeenCalledOnce()
  expect(screen.getByLabelText('Assigned course')).toHaveValue('')
  expect(fetchSpy).not.toHaveBeenCalled()
})

test('review queue supports keyboard focus containment and axe checks', async () => {
  installQueueFetch()
  const user = userEvent.setup()
  const { container } = renderQueue()
  const action = await screen.findByRole('button', { name: 'Confirm result' })
  action.focus()
  expect(action).toHaveFocus()
  await user.keyboard('{Enter}')
  const dialog = await screen.findByRole('dialog')
  expect(within(dialog).getByLabelText('Reason')).toHaveFocus()
  expect((await axe.run(dialog)).violations).toEqual([])
  await user.type(within(dialog).getByLabelText('Reason'), 'I confirmed the response against the evidence.')
  await user.keyboard('{Tab}')
  expect(within(dialog).getByRole('button', { name: 'Cancel' })).toHaveFocus()
  await user.keyboard('{Tab}')
  expect(within(dialog).getByRole('button', { name: 'Confirm result' })).toHaveFocus()
  fireEvent.keyDown(within(dialog).getByRole('button', { name: 'Confirm result' }), { key: 'Tab' })
  expect(within(dialog).getByLabelText('Reason')).toHaveFocus()
  fireEvent.keyDown(within(dialog).getByLabelText('Reason'), { key: 'Tab', shiftKey: true })
  expect(within(dialog).getByRole('button', { name: 'Confirm result' })).toHaveFocus()
  await user.keyboard('{Enter}')
  expect(await screen.findByRole('status')).toHaveTextContent('Confirm result recorded')
  expect(action).toHaveFocus()
  expect((await axe.run(container)).violations).toEqual([])
})

test('network failure retains the typed reason and active filters', async () => {
  const fetchSpy = installQueueFetch({ actionError: new Error('offline') })
  const user = userEvent.setup()
  renderQueue()
  await screen.findByRole('button', { name: 'Confirm result' })
  await user.type(screen.getByLabelText('Outcome ID'), 'outcome-1')
  await user.selectOptions(screen.getByLabelText('Result'), 'INCOMPLETE')
  await user.click(screen.getByRole('button', { name: 'Apply filters' }))
  await user.click(screen.getByRole('button', { name: 'Confirm result' }))
  const dialog = await screen.findByRole('dialog')
  await user.type(within(dialog).getByLabelText('Reason'), 'The source service is unavailable.')
  await user.click(within(dialog).getByRole('button', { name: 'Confirm result' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('typed reason remain available')
  expect(within(dialog).getByDisplayValue('The source service is unavailable.')).toBeInTheDocument()
  expect(screen.getByLabelText('Outcome ID')).toHaveValue('outcome-1')
  expect(screen.getByLabelText('Result')).toHaveValue('INCOMPLETE')
  expect(fetchSpy.mock.calls.some(([input]) => String(input).includes('outcome_id=outcome-1') && String(input).includes('result=INCOMPLETE'))).toBe(true)
})
