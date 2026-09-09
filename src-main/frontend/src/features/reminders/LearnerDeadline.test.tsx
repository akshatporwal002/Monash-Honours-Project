import { render, screen } from '@testing-library/react'
import { LearnerDeadline } from './LearnerDeadline'

test('shows the effective deadline in course time and the learner notice', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    Response.json({
      task_id: 'task',
      time_zone: 'Australia/Sydney',
      original_due_at: '2030-01-02T06:00:00Z',
      effective_due_at: '2030-01-05T06:00:00Z',
      arrangement_active: true,
      reminders_paused: true,
      learner_notice: 'Your extension is approved.',
      reason: 'Private reason must not render',
    }),
  )
  render(<LearnerDeadline taskId="task" />)
  expect(await screen.findByText('Your extension is approved.')).toBeVisible()
  expect(screen.getByText(/5 Jan 2030/)).toHaveTextContent('5:00 pm')
  expect(
    screen.queryByText('Private reason must not render'),
  ).not.toBeInTheDocument()
})
