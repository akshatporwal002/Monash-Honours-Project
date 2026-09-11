import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'
import { request } from '../../app/api'
import { ProfileReview } from './ProfileReview'

vi.mock('../../app/api', () => ({ request: vi.fn() }))
afterEach(() => { cleanup(); vi.clearAllMocks() })

test('review requires evidence and sends the visible version, uncertainty and interpretation', async () => {
  vi.mocked(request).mockResolvedValue({ version: 3 })
  const saved = vi.fn()
  render(<MemoryRouter><ProfileReview course="course" learner={7} outcome="outcome" version={2} evidence={[{ evidence_id: 'reasoning', kind: 'REASONING' }]} onSaved={saved} /></MemoryRouter>)
  fireEvent.click(screen.getByText('Record an educator interpretation'))
  expect(screen.getByRole('button', { name: 'Record interpretation' })).toBeDisabled()
  fireEvent.change(screen.getByLabelText('Reason and observed strategy or explanation form'), { target: { value: 'The worked circuit supported the learner explanation.' } })
  fireEvent.change(screen.getByLabelText('Relationship for reasoning'), { target: { value: 'SUPPORTS' } })
  fireEvent.click(screen.getByRole('button', { name: 'Record interpretation' }))
  await waitFor(() => expect(saved).toHaveBeenCalledOnce())
  const [url, options] = vi.mocked(request).mock.calls[0]
  expect(url).toContain('/learners/7/outcomes/outcome/reviews')
  expect(JSON.parse(String(options?.body))).toMatchObject({ expected_version: 2, dimension: 'USEFUL_EXPLANATION_FORM', uncertainty: 0.5, evidence: [{ evidence_id: 'reasoning', relation: 'SUPPORTS' }] })
})

test('an unchanged failed submission reuses its key and does not report success', async () => {
  vi.mocked(request).mockRejectedValue(new Error('The profile changed; refresh before reviewing it'))
  const saved = vi.fn()
  render(<MemoryRouter><ProfileReview course="course" learner={7} outcome="outcome" version={2} evidence={[{ evidence_id: 'reasoning', kind: 'REASONING' }]} onSaved={saved} /></MemoryRouter>)
  fireEvent.click(screen.getByText('Record an educator interpretation'))
  fireEvent.change(screen.getByLabelText('Reason and observed strategy or explanation form'), { target: { value: 'The worked circuit supported the learner explanation.' } })
  fireEvent.change(screen.getByLabelText('Relationship for reasoning'), { target: { value: 'CONTRADICTS' } })
  fireEvent.click(screen.getByRole('button', { name: 'Record interpretation' }))
  await screen.findByRole('alert')
  fireEvent.click(screen.getByRole('button', { name: 'Record interpretation' }))
  await waitFor(() => expect(request).toHaveBeenCalledTimes(2))
  expect(saved).not.toHaveBeenCalled()
  expect(JSON.parse(String(vi.mocked(request).mock.calls[0][1]?.body)).idempotency_key).toBe(JSON.parse(String(vi.mocked(request).mock.calls[1][1]?.body)).idempotency_key)
})
