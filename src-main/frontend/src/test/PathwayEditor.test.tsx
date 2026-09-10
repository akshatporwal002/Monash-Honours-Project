import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import { PathwayEditor } from '../components/PathwayEditor'

afterEach(() => vi.restoreAllMocks())

test('educator publishes three ordered tasks and retries a lost response without losing the approval draft', async () => {
  const posts: Record<string, unknown>[] = []
  const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } })
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const path = String(input)
    if (path.endsWith('/courses/course-1/tasks')) return response([1, 2, 3].map(index => ({
      id: `task-${index}`, title: `Practice ${index}`, course_id: 'course-1', learning_outcome_id: 'outcome-1', position: index,
      prerequisite_task_ids: index > 1 ? [`task-${index - 1}`] : [], assessment: null,
    })))
    if (path.endsWith('/courses/course-1/pathways')) return response([])
    if (path.endsWith('/outcomes/outcome-1/pathways')) {
      const body = JSON.parse(String(init?.body))
      posts.push(body)
      if (posts.length === 1) return response({ detail: 'Connection lost' }, 503)
      return response({ ...body, id: 'path-1', outcome_id: 'outcome-1', course_id: 'course-1', version: 1, bindings: {} })
    }
    throw new Error(`Unexpected request ${path}`)
  })
  const user = userEvent.setup()
  // Exercise typing on the title; paste the remaining fixture prose so each
  // character does not re-render the whole pathway form before publication.
  const pasteField = async (label: string, value: string) => {
    await user.click(screen.getByLabelText(label))
    await user.paste(value)
  }
  render(<PathwayEditor courseId="course-1" />)
  await screen.findByRole('option', { name: /Outcome containing Practice/ })
  await user.selectOptions(screen.getByLabelText('Outcome'), 'outcome-1')
  await user.tab()
  expect(screen.getByLabelText('Pathway title')).toHaveFocus()
  await user.type(screen.getByLabelText('Pathway title'), 'Hadamard practice')
  for (const index of [1, 2, 3]) {
    await pasteField(`Concept for step ${index}`, 'Hadamard')
    await pasteField(`Evidence guidance for step ${index}`, 'Explain the transformation')
  }
  await pasteField('Approved diagnostic prompt', 'Explain H twice')
  await pasteField('Independent conditions', 'Unaided, with approved access support')
  await pasteField('Publication reason', 'Reviewed against approved sources')
  await user.click(screen.getByRole('button', { name: 'Approve and publish pathway' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Your draft is retained')
  expect(posts).toHaveLength(1)
  expect(screen.getByLabelText('Pathway title')).toHaveValue('Hadamard practice')
  for (const index of [1, 2, 3]) {
    expect(screen.getByLabelText(`Concept for step ${index}`)).toHaveValue('Hadamard')
    expect(screen.getByLabelText(`Evidence guidance for step ${index}`)).toHaveValue('Explain the transformation')
  }
  expect(screen.getByLabelText('Approved diagnostic prompt')).toHaveValue('Explain H twice')
  expect(screen.getByLabelText('Independent conditions')).toHaveValue('Unaided, with approved access support')
  expect(screen.getByLabelText('Publication reason')).toHaveValue('Reviewed against approved sources')
  await user.click(screen.getByRole('button', { name: 'Approve and publish pathway' }))
  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Pathway version 1 published'))
  expect(posts).toHaveLength(2)
  expect(posts[0]).toEqual(posts[1])
  expect(posts[0].steps).toEqual(expect.arrayContaining([expect.objectContaining({ task_id: 'task-3', prerequisites: ['task-2'] })]))
  expect(posts[0]).toMatchObject({
    expected_version: 0,
    request_key: expect.any(String),
    title: 'Hadamard practice',
    diagnostic_task_id: 'task-1',
    diagnostic_prompt: 'Explain H twice',
    independent_conditions: 'Unaided, with approved access support',
    reason: 'Reviewed against approved sources',
    steps: [1, 2, 3].map(index => ({
      task_id: `task-${index}`,
      concept: 'Hadamard',
      prerequisites: index > 1 ? [`task-${index - 1}`] : [],
      support_level: 'guided',
      faded_support_level: 'concept_cue',
      exit_rule: 'accepted_response',
      evidence_rule: 'Explain the transformation',
    })),
  })
})
