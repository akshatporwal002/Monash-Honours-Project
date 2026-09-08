import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'

import { LearnerModelTimeline } from '../components/LearnerModelTimeline'

test('loads metadata-only evidence and keeps an annotation draft on failure', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input)
    if (init?.method === 'POST') return new Response(JSON.stringify({ detail: 'Unavailable' }), { status: 503 })
    if (url.includes('/learner-model/me/timeline')) return new Response(JSON.stringify({ evidence: [{ id: 'e-1', type: 'REASONING', occurred_at: '2026-09-08T00:00:00Z' }], snapshots: [], corrections: [], entries: [], next_cursor: null }))
    throw new Error(`Unexpected ${url}`)
  })
  render(<LearnerModelTimeline />)
  const user = userEvent.setup()
  const inputs = screen.getAllByRole('textbox')
  await user.type(inputs[0], 'course-1'); await user.type(inputs[1], 'outcome-1')
  await user.click(screen.getByRole('button', { name: 'Load history' }))
  expect(await screen.findByText(/REASONING/)).toBeVisible()
  const annotationInputs = screen.getAllByRole('textbox')
  await user.type(annotationInputs[2], 'e-1'); await user.type(annotationInputs[3], 'Needs context')
  await user.click(screen.getByRole('button', { name: 'Add context' }))
  expect(annotationInputs[3]).toHaveValue('Needs context')
})
