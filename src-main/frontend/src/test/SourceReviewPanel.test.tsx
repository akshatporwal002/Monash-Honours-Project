import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { SourceReviewPanel } from '../components/SourceReviewPanel'

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

function source(state = 'UNREVIEWED') {
  return {
    id: 'revision-1', version: 1, source_label: 'Hadamard lesson', created_at: '2026-09-07T00:00:00Z', approval_state: state,
    approvals: state === 'UNREVIEWED' ? [] : [{ id: 'approval-1', sequence: 1, state, reason: 'Teaching source checked', created_at: '2026-09-07T01:00:00Z' }],
    passages: [{ id: 'passage-1', chunk_index: 0, heading: 'Single-qubit measurement', location_label: 'Page 2', chunk_text: 'H applied to zero gives equal measurement probabilities.' }],
  }
}

test('reviews exact saved passages and records the expected source approval sequence', async () => {
  let state = 'UNREVIEWED'
  const actions: unknown[] = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (_input, init) => {
    if (init?.method === 'POST') {
      const payload = JSON.parse(String(init.body))
      actions.push(payload)
      state = payload.state
      return response({ id: 'approval-1', state }, 201)
    }
    return response([source(state)])
  })
  render(<SourceReviewPanel courseId="course-1" materialId="material-1" />)
  const user = userEvent.setup()
  expect(await screen.findByText('H applied to zero gives equal measurement probabilities.')).toBeVisible()
  expect(screen.getByText('Page 2')).toBeVisible()
  expect(screen.getByRole('button', { name: 'Approve source revision' })).toBeDisabled()
  await user.type(screen.getByRole('textbox', { name: /Source review reason/ }), 'Teaching source checked')
  await user.click(screen.getByRole('button', { name: 'Approve source revision' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Revoke source approval' })).toBeDisabled())
  await screen.findByText('Approved')
  expect(actions).toEqual([{ state: 'APPROVED', expected_sequence: 0, reason: 'Teaching source checked' }])
  await user.type(screen.getByRole('textbox', { name: /Source review reason/ }), 'Passage needs correction')
  await user.click(screen.getByRole('button', { name: 'Revoke source approval' }))
  expect(actions[1]).toEqual({ state: 'REVOKED', expected_sequence: 1, reason: 'Passage needs correction' })
})

test('shows a source review conflict without replacing its displayed approval state', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (_input, init) => init?.method === 'POST'
    ? response({ detail: { code: 'source_approval_conflict', message: 'Source review changed; reload before recording another action' } }, 409)
    : response([source()]))
  render(<SourceReviewPanel courseId="course-1" materialId="material-1" />)
  const user = userEvent.setup()
  await user.type(await screen.findByRole('textbox', { name: /Source review reason/ }), 'Checked')
  await user.click(screen.getByRole('button', { name: 'Approve source revision' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Source review changed; reload before recording another action')
  expect(screen.getByText('Unreviewed')).toBeVisible()
})
