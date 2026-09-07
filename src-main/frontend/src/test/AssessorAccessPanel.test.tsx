import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { AssessorAccessPanel } from '../components/AssessorAccessPanel'

const approval = { id: 'approval-1', subject_user_id: 7, actor_user_id: 2, version: 3, state: 'APPROVED', reason: 'Teaching checked', created_at: '2026-09-07T00:00:00Z' }
const candidate = { subject_user_id: 7, full_name: 'Teaching Staff', currently_eligible: true, latest_approval: approval }
const grant = { id: 'grant-1', subject_user_id: 7, assigned_by_user_id: 1, role: 'assessor', version: 1, reason: 'Course appointment', currently_active: true, assigned_at: '2026-09-07T01:00:00Z', valid_from: '2026-09-07T01:00:00Z', revoked_at: null }
function response(body: unknown, status = 200) { return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }) }

test('course lead records an explicit eligibility change against the displayed version', async () => {
  const writes: unknown[] = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    if (init?.method === 'POST') { writes.push(JSON.parse(String(init.body))); return response(approval, 201) }
    return response(String(input).includes('assessor-candidates') ? [candidate] : [approval])
  })
  render(<AssessorAccessPanel courseId="course-1" />)
  const user = userEvent.setup()
  await screen.findByText('Currently eligible')
  expect(screen.queryByRole('button', { name: 'Grant assessor access' })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Withdraw teaching eligibility' })).toBeDisabled()
  await user.type(screen.getByRole('textbox', { name: /Access change reason/ }), 'Teaching duties ended')
  await user.click(screen.getByRole('button', { name: 'Withdraw teaching eligibility' }))
  await screen.findByText(/Eligibility withdrawn/)
  expect(writes).toEqual([{ subject_user_id: 7, state: 'WITHDRAWN', expected_version: 3, reason: 'Teaching duties ended', valid_until: null }])
})

test('administrator grants access separately and records a reason when revoking it', async () => {
  const writes: Array<{ method: string; body: unknown }> = []
  let revoked = false
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    if (init?.method === 'POST' || init?.method === 'DELETE') {
      writes.push({ method: init.method, body: JSON.parse(String(init.body)) })
      if (init.method === 'DELETE') revoked = true
      return response(grant, init.method === 'POST' ? 201 : 200)
    }
    return response(String(input).includes('assessor-candidates') ? [candidate] : String(input).includes('assessor-eligibility') ? [approval] : [{ ...grant, currently_active: !revoked, revoked_at: revoked ? '2026-09-07T02:00:00Z' : null, revocation_reason: revoked ? 'Appointment ended' : null }])
  })
  render(<AssessorAccessPanel courseId="course-1" administrator />)
  const user = userEvent.setup()
  await screen.findByText('Active')
  expect(screen.queryByRole('button', { name: 'Approve teaching eligibility' })).not.toBeInTheDocument()
  await user.type(screen.getByRole('textbox', { name: /Access change reason/ }), 'Appointed for course')
  await user.click(screen.getByRole('button', { name: 'Grant assessor access' }))
  await screen.findByText('Assessor grant recorded.')
  await waitFor(() => expect(screen.getByRole('textbox', { name: /Access change reason/ })).toBeEnabled())
  await user.type(screen.getByRole('textbox', { name: /Access change reason/ }), 'Appointment ended')
  await user.click(screen.getByRole('button', { name: /Revoke grant for staff 7/ }))
  await screen.findByText('Inactive')
  expect(writes).toEqual([
    { method: 'POST', body: { subject_user_id: 7, role: 'assessor', reason: 'Appointed for course', valid_until: null } },
    { method: 'DELETE', body: { reason: 'Appointment ended' } },
  ])
})

test('a stale approval conflict requires a reload before another change', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => init?.method === 'POST'
    ? response({ detail: 'Assessor eligibility changed; reload its history' }, 409)
    : response(String(input).includes('assessor-candidates') ? [candidate] : [approval]))
  render(<AssessorAccessPanel courseId="course-1" />)
  const user = userEvent.setup()
  await user.type(await screen.findByRole('textbox', { name: /Access change reason/ }), 'Checked again')
  await user.click(screen.getByRole('button', { name: 'Approve teaching eligibility' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Assessor eligibility changed')
  expect(screen.queryByText(/Eligibility approved\./)).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Approve teaching eligibility' })).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Reload assessor access' }))
  expect(await screen.findByRole('button', { name: 'Approve teaching eligibility' })).toBeEnabled()
})
