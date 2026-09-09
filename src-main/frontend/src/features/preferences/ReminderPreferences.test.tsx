import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ReminderPreferences } from './ReminderPreferences'

test('a failed preference save preserves the choice and reuses the request key', async () => {
  const writes: string[] = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (_url, init) => {
    if (init?.method !== 'PUT')
      return Response.json({ enabled: true, revision: 0 })
    writes.push(String(init.body))
    return writes.length === 1
      ? Response.json({ detail: 'Please retry' }, { status: 503 })
      : Response.json({ enabled: false, revision: 1 })
  })
  const user = userEvent.setup()
  render(<ReminderPreferences />)
  const toggle = screen.getByRole('checkbox', {
    name: 'Receive task reminders',
  })
  await waitFor(() => expect(toggle).toBeEnabled())
  await user.click(toggle)
  await user.click(
    screen.getByRole('button', { name: 'Save reminder settings' }),
  )
  expect(await screen.findByText('Please retry')).toBeVisible()
  expect(toggle).not.toBeChecked()
  await user.click(
    screen.getByRole('button', { name: 'Save reminder settings' }),
  )
  expect(await screen.findByText('Reminder settings saved.')).toBeVisible()
  expect(writes[1]).toEqual(writes[0])
})

test('revision conflicts require reloading the saved preference', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (_url, init) =>
    init?.method === 'PUT'
      ? Response.json({ detail: 'Changed in another session' }, { status: 409 })
      : Response.json({ enabled: true, revision: 2 }),
  )
  const user = userEvent.setup()
  render(<ReminderPreferences />)
  const save = screen.getByRole('button', { name: 'Save reminder settings' })
  await waitFor(() => expect(save).toBeEnabled())
  await user.click(save)
  await screen.findByText('Changed in another session')
  expect(save).toBeDisabled()
  await user.click(
    screen.getByRole('button', { name: 'Reload saved reminder settings' }),
  )
  await waitFor(() => expect(save).toBeEnabled())
})
