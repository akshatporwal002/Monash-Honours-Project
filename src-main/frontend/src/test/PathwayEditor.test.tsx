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
  render(<PathwayEditor courseId="course-1" />)
  await screen.findByRole('option', { name: /Outcome containing Practice/ })
  await user.selectOptions(screen.getByLabelText('Outcome'), 'outcome-1')
  await user.type(screen.getByLabelText('Pathway title'), 'Hadamard practice')
  for (const index of [1, 2, 3]) {
    await user.type(screen.getByLabelText(`Concept for step ${index}`), 'Hadamard')
    await user.type(screen.getByLabelText(`Evidence guidance for step ${index}`), 'Explain the transformation')
  }
  await user.type(screen.getByLabelText('Approved diagnostic prompt'), 'Explain H twice')
  await user.type(screen.getByLabelText('Independent conditions'), 'Unaided, with approved access support')
  await user.type(screen.getByLabelText('Publication reason'), 'Reviewed against approved sources')
  await user.click(screen.getByRole('button', { name: 'Approve and publish pathway' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Your draft is retained')
  await user.click(screen.getByRole('button', { name: 'Approve and publish pathway' }))
  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Pathway version 1 published'))
  expect(posts).toHaveLength(2)
  expect(posts[0]).toEqual(posts[1])
  expect(posts[0].steps).toEqual(expect.arrayContaining([expect.objectContaining({ task_id: 'task-3', prerequisites: ['task-2'] })]))
})
