import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { LearnerResultPanel } from './LearnerResultPanel'

const result = {
  response_version_id: 'response-1',
  assessment_attempt_id: 'attempt-1',
  decision_id: 'decision-1',
  result: null,
  status: 'Awaiting assessor review',
  bloom_process: 'UNDERSTAND',
  outcome: 'Explain the observation.',
  criteria: [
    {
      id: 'criterion-1',
      description: 'Link evidence to the claim',
      evidence_description: 'Use the saved observation.',
      mandatory: true,
      decision: null,
    },
  ],
  evidence_response_id: 'response-1',
  reason: 'Your response is saved.',
  next_action: 'Review your evidence.',
  review_revision: 0,
  can_request_review: true,
  history: [],
  requests: [],
}

test('pending review is distinct from a result and failed requests keep the typed reason', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (_input, init) =>
    init?.method === 'POST'
      ? Response.json({ detail: 'Please retry' }, { status: 503 })
      : Response.json(result),
  )
  const user = userEvent.setup()
  render(<LearnerResultPanel responseId="response-1" />)
  const input = await screen.findByLabelText('What would you like your assessor to review?')
  expect(screen.queryByText('PASS', { exact: true })).not.toBeInTheDocument()
  await user.type(input, 'Please explain the missing evidence.')
  await user.click(screen.getByRole('button', { name: 'Request assessor review' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Please retry')
  expect(input).toHaveValue('Please explain the missing evidence.')
})

test('void state has no contradictory awaiting-result label', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    Response.json({ ...result, status: 'Attempt voided' }),
  )
  render(<LearnerResultPanel responseId="response-1" />)
  expect(await screen.findByText('Attempt voided')).toBeVisible()
  expect(screen.queryByText('Awaiting review', { exact: true })).not.toBeInTheDocument()
})

test('revoked access clears a previously released result', async () => {
  const fetch = vi
    .spyOn(globalThis, 'fetch')
    .mockResolvedValue(
      Response.json({ ...result, result: 'PASS', status: 'Confirmed by assessor' }),
    )
  const user = userEvent.setup()
  render(<LearnerResultPanel responseId="response-1" />)
  await screen.findByText('PASS', { exact: true })
  fetch.mockResolvedValue(Response.json({ detail: 'Access ended' }, { status: 404 }))
  await user.click(screen.getByRole('button', { name: 'Refresh result' }))
  await screen.findByRole('alert')
  expect(screen.queryByText('PASS', { exact: true })).not.toBeInTheDocument()
})
