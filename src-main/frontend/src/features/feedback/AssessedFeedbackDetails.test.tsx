import axe from 'axe-core'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { createFeedbackApiClient } from './api'
import { AssessedFeedbackDetails } from './AssessedFeedbackDetails'
import fixture from './fixtures/task16-response.json'

async function parsed(body: unknown = fixture) {
  return createFeedbackApiClient({
    fetch: vi.fn<typeof fetch>(async () => new Response(JSON.stringify(body), {
      headers: { 'Content-Type': 'application/json' },
    })),
  }).get(fixture.submission_id)
}

test('keeps frozen references and exposes criterion evidence through its disclosure', async () => {
  const result = await parsed()
  const feedback = result.response.feedback
  if (feedback?.kind !== 'validated' || !feedback.assessed) throw new Error('Missing assessed feedback')
  expect(feedback.assessed.response_version_id).toBe(fixture.submission_id)
  expect(feedback.assessed.source_claims).toEqual(fixture.feedback.assessed.source_claims)
  const { container } = render(<AssessedFeedbackDetails feedback={feedback.assessed} />)
  const disclosure = screen.getByText('Inspect recorded evidence')
  await userEvent.click(disclosure)
  expect(screen.getByText('Submitted answer is recorded.')).toBeVisible()
  expect(screen.getByRole('heading', { name: 'Reflection' })).toBeVisible()
  expect(container.textContent).not.toMatch(/PASS|INCOMPLETE/)
  expect((await axe.run(container)).violations).toEqual([])
})

test('renders a quoted source as text and never creates source-supplied HTML', async () => {
  const body = structuredClone(fixture)
  const quote = '<img src=x onerror=alert(1)>'
  body.feedback.assessed.source_claims[0].support_quote = quote
  body.feedback.assessed.source_claims[0].claim = quote
  const result = await parsed(body)
  const feedback = result.response.feedback
  if (feedback?.kind !== 'validated' || !feedback.assessed) throw new Error('Missing assessed feedback')
  const { container } = render(<AssessedFeedbackDetails feedback={feedback.assessed} />)
  expect(screen.getByText(quote)).toBeVisible()
  expect(container.querySelector('img')).toBeNull()
})

test('rejects malformed assessed feedback instead of dropping its grounding fields', async () => {
  const body = structuredClone(fixture)
  body.feedback.assessed.source_claims[0].claim = 'An unsupported claim'
  await expect(parsed(body)).rejects.toMatchObject({ code: 'invalid_response' })
})
