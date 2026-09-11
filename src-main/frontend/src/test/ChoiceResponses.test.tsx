import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { api } from '../app/api'
import type { LearningTask } from '../app/types'
import { TaskView } from '../components/TaskView'

const base: LearningTask = { id: 'choice-task', title: 'Reviewed choices', module: 'Quantum', description: 'Choose a response', instructions: 'Use the reviewed options', task_type: 'multiple_choice', difficulty: 'beginner', points: 0, position: 1, status: 'in_progress' }

test.each(['multiple_choice', 'multiple_answer'] as const)('%s does not invent missing choices and keeps historical answers visible', async task_type => {
  vi.spyOn(api.student, 'draft').mockResolvedValue(null)
  vi.spyOn(api.student, 'attempts').mockResolvedValue([{ id: 'legacy-attempt', attempt_number: 1, answer: 'legacy choice response', status: 'submitted', feedback: 'Recorded response', feedback_reference: null }])
  const submit = vi.spyOn(api.student, 'submit')
  render(<TaskView task={{ ...base, task_type }} onClose={() => {}} onSubmitted={async () => {}} />)
  expect(await screen.findByText('Reviewed choices are unavailable. Ask your educator to review this task.')).toBeVisible()
  await waitFor(() => expect(screen.queryByText('Restoring your saved work…')).not.toBeInTheDocument())
  expect(screen.queryAllByRole('radio')).toHaveLength(0)
  expect(screen.queryAllByRole('checkbox')).toHaveLength(0)
  expect(screen.getByRole('button', { name: 'Submit activity' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Save draft' })).toBeDisabled()
  await userEvent.setup().click(await screen.findByText('Saved response'))
  expect(screen.getByText('legacy choice response')).toBeVisible()
  expect(submit).not.toHaveBeenCalled()
})
