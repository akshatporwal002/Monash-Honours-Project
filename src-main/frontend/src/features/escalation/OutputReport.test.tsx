import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { OutputReport, ReportNotices } from './OutputReport'

test('reply reports retain a failed request and show a receipt after retry', async () => {
  const writes: string[] = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (_path, init) => {
    writes.push(String(init?.body))
    return writes.length === 1
      ? Response.json({ detail: 'Please retry' }, { status: 503 })
      : Response.json({ id: 'report' })
  })
  const user = userEvent.setup()
  render(<OutputReport sourceId="reply-1" />)
  await user.click(screen.getByRole('button', { name: 'Report this reply' }))
  const reason = screen.getByLabelText('Describe the concern (required)')
  await user.type(reason, 'The explanation contradicts the approved source.')
  await user.click(screen.getByRole('button', { name: 'Send reply report' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Please retry')
  expect(reason).toHaveValue('The explanation contradicts the approved source.')
  await user.click(screen.getByRole('button', { name: 'Send reply report' }))
  expect(await screen.findByRole('status')).toHaveTextContent(
    'saved for human review',
  )
  expect(writes[1]).toEqual(writes[0])
})

test('learner report updates show notices and clear when course access ends', async () => {
  const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    Response.json([
      {
        id: 'report',
        queue_kind: 'ASSESSOR',
        status: 'RESOLVED',
        created_at: '2026-09-09T00:00:00Z',
        resolution_due_at: null,
        notices: [
          {
            revision: 1,
            learner_notice: 'We reviewed the explanation.',
            created_at: '2026-09-09T01:00:00Z',
          },
        ],
      },
    ]),
  )
  const user = userEvent.setup()
  render(<ReportNotices taskId="task" />)
  await screen.findByText(/We reviewed the explanation/)
  fetch.mockResolvedValue(
    Response.json({ detail: 'Access ended' }, { status: 403 }),
  )
  await user.click(screen.getByRole('button', { name: 'Refresh reports' }))
  await screen.findByRole('alert')
  expect(
    screen.queryByText(/We reviewed the explanation/),
  ).not.toBeInTheDocument()
})
