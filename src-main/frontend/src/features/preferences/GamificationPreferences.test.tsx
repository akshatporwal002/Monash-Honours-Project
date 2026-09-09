import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { GamificationPreferences } from './GamificationPreferences'

test('opt-out persists and a failed save keeps the choice and retry key', async () => {
  const writes: string[] = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (_path, init) => {
    if (init?.method !== 'PUT')
      return Response.json({ enabled: true, revision: 0 })
    writes.push(String(init.body))
    return writes.length === 1
      ? Response.json({ detail: 'Retry the save' }, { status: 503 })
      : Response.json({ enabled: false, revision: 1 })
  })
  const user = userEvent.setup()
  render(<GamificationPreferences />)
  const toggle = await screen.findByRole('checkbox', {
    name: 'Enable optional points and achievements',
  })
  await user.click(toggle)
  await user.click(
    screen.getByRole('button', { name: 'Save gamification preference' }),
  )
  expect(await screen.findByRole('alert')).toHaveTextContent('Retry the save')
  expect(toggle).not.toBeChecked()
  await user.click(
    screen.getByRole('button', { name: 'Save gamification preference' }),
  )
  expect(await screen.findByRole('status')).toHaveTextContent('are off')
  expect(writes[0]).toEqual(writes[1])
})

test('a saved opt-out loads as off', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    Response.json({ enabled: false, revision: 2 }),
  )
  render(<GamificationPreferences />)
  expect(await screen.findByRole('checkbox')).not.toBeChecked()
})
