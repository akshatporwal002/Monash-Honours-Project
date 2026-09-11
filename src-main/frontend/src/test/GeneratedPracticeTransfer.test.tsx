import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { api } from '../app/api'
import type { LearningTask } from '../app/types'
import { TaskView } from '../components/TaskView'

test('standalone application alone enables and submits the typed practice response', async () => {
  const task: LearningTask = { id: 'source-transfer', title: 'New-context practice', module: 'Gates', description: 'Apply the source relationship to a changed condition', instructions: 'Explain the new example', task_type: 'transfer', difficulty: 'beginner', points: 0, position: 1, status: 'in_progress' }
  vi.spyOn(api.student, 'draft').mockResolvedValue(null)
  vi.spyOn(api.student, 'attempts').mockResolvedValue([])
  const submit = vi.spyOn(api.student, 'submit').mockResolvedValue({ id: 'saved', attempt_number: 1, status: 'submitted', feedback: null })
  render(<TaskView task={task} onClose={() => {}} onSubmitted={async () => {}} />)
  await waitFor(() => expect(screen.queryByText('Restoring your saved work…')).not.toBeInTheDocument())
  const button = screen.getByRole('button', { name: 'Submit activity' })
  expect(button).toBeDisabled()
  const user = userEvent.setup()
  await user.click(screen.getByLabelText('New-context application'))
  await user.paste('Change the input and explain the consequence.')
  expect(button).toBeEnabled()
  await user.click(button)
  expect(submit).toHaveBeenCalledWith(task.id, expect.objectContaining({ episode: expect.objectContaining({ supported: expect.objectContaining({ application: { answer: 'Change the input and explain the consequence.' } }) }) }))
  expect(screen.queryByRole('button', { name: 'Start assessed task' })).not.toBeInTheDocument()
})
