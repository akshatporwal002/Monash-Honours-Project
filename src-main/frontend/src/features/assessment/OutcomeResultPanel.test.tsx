import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { OutcomeResultPanel } from './OutcomeResultPanel'

test('outcome result links to authorised fresh work and clears on access loss', async () => {
  const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    Response.json({
      result: 'INCOMPLETE',
      status: 'Current outcome result',
      explanation: 'Earlier decisions remain readable.',
      evidence_response_ids: ['response'],
      authorisations: [
        {
          id: 'grant',
          task_id: 'fresh',
          task_title: 'Fresh explanation',
          learner_notice: 'Try the fresh scenario.',
          available: true,
          replacement_response_id: null,
        },
      ],
    }),
  )
  const user = userEvent.setup()
  render(
    <MemoryRouter>
      <OutcomeResultPanel responseId="response" />
    </MemoryRouter>,
  )
  expect(
    await screen.findByRole('link', { name: 'Open fresh reassessment' }),
  ).toHaveAttribute('href', '/student/tasks/fresh')
  expect(screen.getByText('INCOMPLETE')).toBeVisible()
  fetch.mockResolvedValue(
    Response.json({ detail: 'Access ended' }, { status: 403 }),
  )
  await user.click(screen.getByRole('button', { name: 'Refresh outcome' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Access ended')
  expect(screen.queryByText('INCOMPLETE')).not.toBeInTheDocument()
})
