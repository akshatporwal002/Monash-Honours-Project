import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { DeadlineArrangementsPanel } from './DeadlineArrangementsPanel'

test('an uncertain save retries the same arrangement and stale history requires reload', async () => {
  const writes: string[] = []
  let historyReads = 0
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input)
    if (url.includes('/enrollments'))
      return Response.json([{ student_id: 7, student_name: 'Test learner' }])
    if (url.endsWith('/tasks'))
      return Response.json([{ id: 'task', title: 'Quantum task' }])
    if (init?.method !== 'PUT') {
      historyReads += 1
      return Response.json([])
    }
    writes.push(String(init.body))
    return Response.json(
      {
        detail:
          writes.length === 1 ? 'Retry the save' : 'History changed; reload',
      },
      { status: writes.length === 1 ? 503 : 409 },
    )
  })
  const user = userEvent.setup()
  render(
    <DeadlineArrangementsPanel courseId="course" timeZone="Australia/Sydney" />,
  )
  await waitFor(() =>
    expect(
      screen.queryByText('Loading course participants and tasks…'),
    ).not.toBeInTheDocument(),
  )
  await user.click(screen.getByRole('combobox', { name: 'Learner' }))
  await user.click(await screen.findByRole('option', { name: 'Test learner' }))
  await user.click(screen.getByRole('combobox', { name: 'Task' }))
  await user.click(await screen.findByRole('option', { name: 'Quantum task' }))
  const save = await screen.findByRole('button', {
    name: 'Save arrangement',
  })
  await waitFor(() => expect(save).toBeEnabled())
  fireEvent.change(
    screen.getByLabelText('Extended deadline (Australia/Sydney)'),
    { target: { value: '2035-01-05T17:00' } },
  )
  await user.type(
    screen.getByLabelText('Private staff reason'),
    'Scheduling review',
  )
  await user.type(
    screen.getByLabelText('Notice shown to the learner'),
    'Your extension is approved.',
  )
  await user.click(save)
  await screen.findByText('Retry the save')
  await user.click(save)
  await screen.findByText('History changed; reload')
  expect(writes[1]).toEqual(writes[0])
  expect(JSON.parse(writes[0])).toMatchObject({
    expected_revision: 0,
    local_due_at: '2035-01-05T17:00:00',
    time_zone: 'Australia/Sydney',
  })
  expect(save).toBeDisabled()
  await user.click(
    screen.getByRole('button', { name: 'Reload arrangement history' }),
  )
  await waitFor(() => expect(save).toBeEnabled())
  expect(historyReads).toBe(2)
  expect(screen.getByLabelText('Private staff reason')).toHaveValue(
    'Scheduling review',
  )
})
