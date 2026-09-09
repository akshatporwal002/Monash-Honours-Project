import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import axe from 'axe-core'
import { activityContinuation, type Activity } from '../app/activityContinuation'
import { ActivityContinuation, CourseActivityContinuations } from '../components/ActivityContinuation'

beforeEach(() => vi.restoreAllMocks())

const suggestion: Activity = {
  learner_label: 'Test learner', workflow_id: 'workflow', state: 'suggested', reason: 'The next approved practice meets its prerequisites.',
  uncertainty: 1, snapshot_id: 'snapshot', rule_version: 'approved-activity.v1', evidence_ids: ['evidence'],
  preference_version: 1, pathway_id: 'pathway', next_task_id: 'next',
  options: [{ task_id: 'next', title: 'Approved next practice', support_level: 'guided' }],
  version: 0, history: [], can_override: false,
}

test('learner retry keeps its request key and saved choice exposes the approved link', async () => {
  vi.spyOn(activityContinuation, 'submission').mockResolvedValue(suggestion)
  const save = vi.spyOn(activityContinuation, 'act').mockRejectedValueOnce(new Error('lost response')).mockResolvedValue({ ...suggestion, state: 'accept', version: 1 })
  const user = userEvent.setup()
  render(<MemoryRouter><ActivityContinuation submissionId="submission" /></MemoryRouter>)
  await user.click(await screen.findByRole('button', { name: 'Accept suggestion' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Your choice was not confirmed')
  await user.click(screen.getByRole('button', { name: 'Accept suggestion' }))
  expect(await screen.findByRole('link', { name: 'Open chosen activity' })).toHaveAttribute('href', '/student/tasks/next')
  expect(save.mock.calls[0][1].request_key).toBe(save.mock.calls[1][1].request_key)
})

test('educator failure retains reason and choice, while explicit refresh uses current version', async () => {
  vi.spyOn(activityContinuation, 'course').mockResolvedValue([{ ...suggestion, can_override: true }])
  vi.spyOn(activityContinuation, 'read').mockResolvedValue({ ...suggestion, can_override: true, version: 2 })
  const save = vi.spyOn(activityContinuation, 'act').mockRejectedValueOnce(new Error('conflict')).mockResolvedValue({ ...suggestion, can_override: true, version: 3, state: 'educator_override' })
  const user = userEvent.setup()
  render(<MemoryRouter><CourseActivityContinuations courseId="course" /></MemoryRouter>)
  await user.selectOptions(await screen.findByLabelText('Approved alternatives'), 'next')
  await user.type(screen.getByLabelText('Reason for educator override'), 'Use the approved practice')
  await user.click(screen.getByRole('button', { name: 'Save educator override' }))
  expect(await screen.findByRole('alert')).toBeVisible()
  expect(screen.getByLabelText('Reason for educator override')).toHaveValue('Use the approved practice')
  await user.click(screen.getByRole('button', { name: 'Refresh saved suggestion' }))
  await user.click(screen.getByRole('button', { name: 'Save educator override' }))
  expect(save.mock.calls[1][1].expected_version).toBe(2)
  expect(save.mock.calls[1][1].reason).toBe('Use the approved practice')
})

test('no eligible activity stays usable and the mounted controls pass Axe', async () => {
  vi.spyOn(activityContinuation, 'submission').mockResolvedValue({ ...suggestion, state: 'no_eligible_activity', next_task_id: null, options: [], reason: 'No new activity meets the prerequisites.' })
  const { container } = render(<MemoryRouter><ActivityContinuation submissionId="submission" /></MemoryRouter>)
  expect(await screen.findByText('No new activity meets the prerequisites.')).toBeVisible()
  expect(screen.getByRole('button', { name: 'Accept suggestion' })).toBeDisabled()
  expect(screen.queryByRole('link')).not.toBeInTheDocument()
  expect((await axe.run(container)).violations).toEqual([])
})
