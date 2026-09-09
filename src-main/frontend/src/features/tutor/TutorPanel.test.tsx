import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { TutorPanel } from './TutorPanel'

const state = {
  context_token: 'reviewed-task',
  revision: 0,
  instructional_help_available: true,
  status: 'Explain your reasoning.',
  turns: [],
  next_offset: null,
}

test('a failed send preserves the message and its retry key', async () => {
  const requests: string[] = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (_input, init) => {
    if (init?.method !== 'POST') return Response.json(state)
    requests.push(String(init.body))
    if (requests.length === 1)
      return Response.json({ detail: 'Temporarily unavailable' }, { status: 503 })
    return Response.json(
      {
        id: 'turn-1',
        revision: 1,
        message: 'My explanation',
        reply: 'What evidence supports it?',
        kind: 'probe',
        created_at: '2026-09-09T00:00:00Z',
        source_references: [],
      },
      { status: 201 },
    )
  })
  const user = userEvent.setup()
  render(<TutorPanel taskId="task-1" />)
  const input = await screen.findByLabelText('Your reasoning or question')
  await user.type(input, 'My explanation')
  await user.click(screen.getByRole('button', { name: 'Send to tutor' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Temporarily unavailable')
  expect(input).toHaveValue('My explanation')
  await user.click(screen.getByRole('button', { name: 'Send to tutor' }))
  expect(await screen.findByText('What evidence supports it?')).toBeVisible()
  expect(requests[1]).toEqual(requests[0])
  expect(input).toHaveValue('')
})

test('transfer refresh removes dialogue and sending controls', async () => {
  let transfer = false
  vi.spyOn(globalThis, 'fetch').mockImplementation(async () =>
    Response.json(
      transfer
        ? {
            ...state,
            instructional_help_available: false,
            status: 'Fresh application is unaided.',
          }
        : state,
    ),
  )
  const user = userEvent.setup()
  render(<TutorPanel taskId="task-1" />)
  await screen.findByLabelText('Your reasoning or question')
  transfer = true
  await user.click(screen.getByRole('button', { name: 'Reload conversation' }))
  await waitFor(() =>
    expect(screen.queryByLabelText('Your reasoning or question')).not.toBeInTheDocument(),
  )
  expect(screen.getByText('Fresh application is unaided.')).toBeVisible()
})

test('revoked access clears cached dialogue', async () => {
  const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue(Response.json(state))
  const user = userEvent.setup()
  render(<TutorPanel taskId="task-1" />)
  await screen.findByLabelText('Your reasoning or question')
  fetch.mockResolvedValue(Response.json({ detail: 'Access ended' }, { status: 404 }))
  await user.click(screen.getByRole('button', { name: 'Reload conversation' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Access ended')
  expect(screen.queryByLabelText('Your reasoning or question')).not.toBeInTheDocument()
})
