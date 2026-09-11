import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import { CourseHistoryPanel } from '../components/CourseHistoryPanel'

afterEach(() => vi.restoreAllMocks())
const revisions = [2, 1].map(version => ({
  id: `revision-${version}`, version,
  metadata_snapshot: { code: 'Q1', title: `Title ${version}`, description: 'Saved description', state: 'draft', enrollment_open: true, time_zone: 'UTC' },
  context_snapshot: { modules: [{ id: 'module', title: 'Original module', description: 'Context', position: 1 }], enrollments: [{ id: 'enrolment', student_id: 3, status: 'active' }], sources: [{ material_id: 'material', revision_id: 'source-v1', retired: false }] },
  actor_id: 'owner', action: 'UPDATED', reason: '', restored_from_id: null, created_at: '2026-09-10T00:00:00Z',
}))
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

test('inspects context and restores an older revision with reason and latest version', async () => {
  const onRestored = vi.fn().mockResolvedValue(undefined)
  const actions: unknown[] = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (_url, init) => {
    if (init?.method === 'POST') { actions.push(JSON.parse(String(init.body))); return response({}) }
    return response(revisions)
  })
  render(<CourseHistoryPanel courseId="course" onRestored={onRestored} />)
  const user = userEvent.setup()
  await screen.findByText('Revision 1: Title 1 — draft')
  await user.click(screen.getByText('Revision 1: Title 1 — draft'))
  const restore = screen.getByRole('button', { name: 'Restore revision 1' })
  expect(restore).toBeDisabled()
  expect(screen.getByText('Learner 3: active', { selector: 'details[open] li' })).toBeVisible()
  await user.type(screen.getByRole('textbox', { name: 'Reason for restoration' }), 'Recover earlier wording')
  await user.click(restore)
  await waitFor(() => expect(onRestored).toHaveBeenCalledOnce())
  expect(actions).toEqual([{ expected_version: 2, reason: 'Recover earlier wording' }])
  expect(await screen.findByRole('status')).toHaveTextContent('restored from revision 1')
})

test('keeps history and reason when restoration conflicts', async () => {
  const onRestored = vi.fn()
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (_url, init) => init?.method === 'POST'
    ? response({ detail: 'Course history changed; reload before restoring' }, 409) : response(revisions))
  render(<CourseHistoryPanel courseId="course" onRestored={onRestored} />)
  const user = userEvent.setup()
  await user.click(await screen.findByText('Revision 1: Title 1 — draft'))
  await user.type(screen.getByRole('textbox', { name: 'Reason for restoration' }), 'Recover wording')
  await user.click(screen.getByRole('button', { name: 'Restore revision 1' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('history changed')
  expect(screen.getByRole('textbox', { name: 'Reason for restoration' })).toHaveValue('Recover wording')
  expect(onRestored).not.toHaveBeenCalled()
})
