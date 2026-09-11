import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import { request } from '../../app/api'
import { AssessmentModerationPanel } from './AssessmentModerationPanel'

vi.mock('../../app/api', async importOriginal => ({ ...await importOriginal<typeof import('../../app/api')>(), request: vi.fn() }))
const access = vi.fn().mockResolvedValue(true)
const revoked = vi.fn()
const recorded = vi.fn()

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(request).mockImplementation(async url => url.endsWith('/moderation')
    ? { policy_status: 'POLICY_REQUIRED', records: [] }
    : { state: 'PENDING', reason: 'No approved evaluator evidence', ai_activation: 'PENDING' })
})

it('shows missing policy and leaves all proposed sampling numbers blank', async () => {
  render(<AssessmentModerationPanel courseId="course-a" onCheckAccess={access} onAccessRevoked={revoked} onRecorded={recorded} />)
  expect(await screen.findByText(/Approved sampling policy required/)).toBeVisible()
  expect(screen.getByText(/AI activation: PENDING/)).toBeVisible()
  for (const control of screen.getAllByRole('spinbutton', { hidden: true })) expect(control).toHaveValue(null)
  expect(screen.queryByRole('button', { name: /^Review / })).not.toBeInTheDocument()
})

it('shows disagreement and preserves history without offering an ineligible review action', async () => {
  vi.mocked(request).mockImplementation(async url => url.endsWith('/moderation')
    ? { policy_status: 'CONFIGURED', records: [{ attempt_id: 'attempt-a', task_family: 'explanation', sequence: 1, policy_id: 'policy-a', drift_check: false, state: 'DISAGREEMENT', next_stage: null, history: [{ stage: 'ORIGINAL', result: 'PASS' }, { stage: 'SECOND', result: 'INCOMPLETE' }] }] }
    : { state: 'INVALIDATED', reason: 'Material model change', ai_activation: 'PENDING' })
  render(<AssessmentModerationPanel courseId="course-a" onCheckAccess={access} onAccessRevoked={revoked} onRecorded={recorded} />)
  expect(await screen.findByText(/third assessor resolution required/)).toBeVisible()
  expect(screen.getByText('Another authorised assessor is required.')).toBeVisible()
  expect(screen.queryByRole('button', { name: /^Review / })).not.toBeInTheDocument()
  fireEvent.click(screen.getByText('Preserved moderation history'))
  expect(screen.getByLabelText('Original, independent and resolved decisions')).toHaveTextContent('INCOMPLETE')
})

it('clears evidence when the current course permission is revoked', async () => {
  access.mockResolvedValueOnce(false)
  render(<AssessmentModerationPanel courseId="course-a" onCheckAccess={access} onAccessRevoked={revoked} onRecorded={recorded} />)
  await waitFor(() => expect(revoked).toHaveBeenCalledOnce())
  expect(request).not.toHaveBeenCalled()
  expect(screen.getByRole('alert')).toHaveTextContent('Check assessor access')
})

it('discards a delayed course-A reload after switching to course B and clears prior form state', async () => {
  let resolveAQueue!: (value: unknown) => void
  let resolveAValidation!: (value: unknown) => void
  const slowQueue = new Promise(resolve => { resolveAQueue = resolve })
  const slowValidation = new Promise(resolve => { resolveAValidation = resolve })
  let aQueueReads = 0
  let aValidationReads = 0
  const queue = (course: string) => ({ policy_status: 'CONFIGURED', records: [{ attempt_id: `attempt-${course}`, task_family: `family-${course}`, sequence: 1, policy_id: `policy-${course}`, drift_check: false, state: 'ORIGINAL_REQUIRED', next_stage: 'ORIGINAL', history: [] }] })
  vi.mocked(request).mockImplementation(async url => {
    if (url.includes('course-a')) {
      if (url.endsWith('/moderation')) return ++aQueueReads === 1 ? queue('a') : slowQueue
      return ++aValidationReads === 1 ? { state: 'PENDING', reason: 'validation-a', ai_activation: 'PENDING' } : slowValidation
    }
    return url.endsWith('/moderation') ? queue('b') : { state: 'PENDING', reason: 'validation-b', ai_activation: 'PENDING' }
  })
  const view = render(<AssessmentModerationPanel courseId="course-a" onCheckAccess={access} onAccessRevoked={revoked} onRecorded={recorded} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Review attempt-a' }))
  expect(screen.getByRole('button', { name: 'Inspect moderation evidence' })).toBeVisible()
  fireEvent.click(screen.getByText('Record an approved sampling policy'))
  fireEvent.change(screen.getByLabelText('Sampling approval reference'), { target: { value: 'course-A draft approval' } })
  fireEvent.click(screen.getByRole('button', { name: 'Reload moderation' }))
  await waitFor(() => expect(aValidationReads).toBe(2))
  view.rerender(<AssessmentModerationPanel courseId="course-b" onCheckAccess={access} onAccessRevoked={revoked} onRecorded={recorded} />)
  expect(await screen.findByRole('button', { name: 'Review attempt-b' })).toBeVisible()
  expect(screen.queryByRole('button', { name: 'Inspect moderation evidence' })).not.toBeInTheDocument()
  expect(screen.getByLabelText('Sampling approval reference')).toHaveValue('')
  await act(async () => {
    resolveAQueue(queue('late-a'))
    resolveAValidation({ state: 'VALIDATED', reason: 'late-validation-a', ai_activation: 'PENDING' })
  })
  expect(screen.getByRole('button', { name: 'Review attempt-b' })).toBeVisible()
  expect(screen.queryByText(/late-validation-a/)).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Review attempt-late-a' })).not.toBeInTheDocument()
  expect(screen.getByText(/validation-b/)).toBeVisible()
  expect(screen.getByRole('button', { name: 'Reload moderation' })).toBeEnabled()
  expect(revoked).not.toHaveBeenCalled()
})
