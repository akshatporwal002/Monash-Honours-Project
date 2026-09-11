import { fireEvent, render, screen, waitFor } from '@testing-library/react'
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
