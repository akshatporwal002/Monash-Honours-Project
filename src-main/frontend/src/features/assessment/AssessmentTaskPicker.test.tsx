import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { AssessmentTaskPicker } from './AssessmentTaskPicker'

const task = {
  task_id: 'task-1', title: 'Prepare superposition', task_type: 'circuit',
  outcome_id: 'outcome-1', outcome_statement: 'Apply a Hadamard gate.',
  revision_id: 'revision-1', content_digest: 'sha256:reviewed', reviewed: true, issues: [],
  source_materials: [{ material_id: 'material-1', label: 'Saved lesson' }],
}

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

beforeEach(() => vi.restoreAllMocks())

test('selects saved reviewed task identity and exposes source passages without approval controls', async () => {
  const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => response(String(url).includes('authoring-tasks') ? [task] : [{
    id: 'source-revision', version: 1, source_label: 'Saved lesson', approval_state: 'APPROVED',
    created_at: '2026-09-07T00:00:00Z', approvals: [],
    passages: [{ id: 'passage-1', chunk_index: 0, chunk_text: 'Exact reviewed Hadamard passage.' }],
  }]))
  const update = vi.fn()
  const user = userEvent.setup()
  render(<AssessmentTaskPicker courseId="course-1" lockedIdentity={false} onUpdate={update} />)
  expect(fetchSpy).not.toHaveBeenCalled()
  await user.click(screen.getByRole('button', { name: 'Browse saved course tasks' }))
  await user.click(await screen.findByLabelText('Saved course task'))
  await user.click(await screen.findByRole('option', { name: task.title }))
  await user.click(screen.getByRole('button', { name: 'Use this reviewed task' }))
  expect(update.mock.calls).toEqual([
    ['taskId', 'task-1'], ['outcomeId', 'outcome-1'], ['outcome', task.outcome_statement],
    ['sourceVersion', 'task-revision:revision-1'], ['sourceDigest', task.content_digest],
    ['source', 'Saved lesson'], ['taskFamily', 'circuit'],
  ])
  await user.click(screen.getByRole('button', { name: 'Read source: Saved lesson' }))
  expect(await screen.findByText('Exact reviewed Hadamard passage.')).toBeVisible()
  expect(screen.queryByRole('button', { name: /Approve source|Revoke source/ })).not.toBeInTheDocument()
  expect(screen.queryByRole('textbox', { name: /Source review reason/ })).not.toBeInTheDocument()
})

test.each(['unreviewed', 'no-source', 'locked'])('blocks selection of %s tasks', async (state) => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(response([{ ...task,
    reviewed: state !== 'unreviewed', source_materials: state === 'no-source' ? [] : task.source_materials,
  }]))
  const user = userEvent.setup()
  render(<AssessmentTaskPicker courseId="course-1" lockedIdentity={state === 'locked'} onUpdate={vi.fn()} />)
  await user.click(screen.getByRole('button', { name: 'Browse saved course tasks' }))
  await user.click(await screen.findByLabelText('Saved course task'))
  await user.click(await screen.findByRole('option', { name: task.title }))
  expect(screen.getByRole('button', { name: 'Use this reviewed task' })).toBeDisabled()
})

test('clears stale choices when refresh loses access', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(response([task]))
    .mockResolvedValueOnce(response({ detail: 'Assessor access ended' }, 403))
  const user = userEvent.setup()
  render(<AssessmentTaskPicker courseId="course-1" lockedIdentity={false} onUpdate={vi.fn()} />)
  await user.click(screen.getByRole('button', { name: 'Browse saved course tasks' }))
  await screen.findByLabelText('Saved course task')
  await user.click(screen.getByRole('button', { name: 'Browse saved course tasks' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Assessor access ended')
  expect(screen.queryByLabelText('Saved course task')).not.toBeInTheDocument()
})
