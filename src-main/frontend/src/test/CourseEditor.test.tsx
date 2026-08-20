import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { CourseEditor } from '../components/CourseEditor'

function response(body: unknown, status = 200): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

const course = {
  id: 'course-1',
  educator_id: 2,
  code: 'QL-101',
  title: 'Quantum Foundations',
  description: 'Qubits, gates and measurement.',
  state: 'draft',
  enrollment_open: false,
  module_count: 1,
  student_count: 3,
  progress_percentage: 20,
}

const module = {
  id: 'module-1',
  course_id: 'course-1',
  title: 'Measurement',
  description: 'Single-qubit measurement.',
  position: 1,
}

const weeklyOutcome = {
  id: 'outcome-1',
  module_id: 'module-1',
  title: 'Explain measurement',
  statement: 'Explain single-qubit measurement probabilities.',
  kind: 'weekly',
  week_number: 2,
  position: 1,
}

test('reloads and edits persisted modules, weekly outcomes, and enrollment status', async () => {
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input)
    const method = init?.method ?? 'GET'

    if (url.endsWith('/courses') && method === 'GET') return response([course])
    if (url.endsWith('/courses/course-1/materials/list')) {
      return response([{
        id: 'material-1',
        original_filename: 'week-2.pdf',
        source_url: null,
        indexing_status: 'indexed',
      }])
    }
    if (url.endsWith('/courses/course-1/modules')) return response([module])
    if (url.endsWith('/modules/module-1/outcomes')) return response([weeklyOutcome])
    if (url.endsWith('/courses/course-1') && method === 'PATCH') return response(course)
    if (url.endsWith('/modules/module-1') && method === 'PATCH') return response(module)
    if (url.endsWith('/outcomes/outcome-1') && method === 'PATCH') {
      const payload = JSON.parse(String(init?.body))
      return response({ ...weeklyOutcome, ...payload })
    }
    if (url.endsWith('/outcomes/outcome-1') && method === 'DELETE') {
      return response(undefined, 204)
    }
    throw new Error(`Unexpected request: ${method} ${url}`)
  })

  render(<CourseEditor />)
  const user = userEvent.setup()

  await user.click(await screen.findByRole('combobox', { name: 'Choose a course to edit' }))
  await user.click(await screen.findByRole('option', { name: 'QL-101 · Quantum Foundations' }))
  expect(await screen.findByDisplayValue('Quantum Foundations')).toBeInTheDocument()
  expect(screen.getByRole('checkbox', { name: /Enrollment open/ })).not.toBeChecked()

  await user.click(screen.getByRole('button', { name: /Save and add materials/ }))
  await user.click(await screen.findByRole('button', { name: /Define outcomes/ }))

  expect(await screen.findByDisplayValue('Measurement')).toBeInTheDocument()
  expect(screen.getByText('Explain single-qubit measurement probabilities.')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Edit' }))
  expect(screen.getByRole('combobox', { name: 'Outcome schedule' })).toHaveTextContent('Weekly')
  expect(screen.getByLabelText('Week number')).toHaveValue(2)

  await user.click(screen.getByRole('combobox', { name: 'Outcome schedule' }))
  await user.click(await screen.findByRole('option', { name: 'Topic-based' }))
  const editor = screen.getByLabelText(/Edit learning outcome/)
  await user.clear(editor)
  await user.type(editor, 'Explain how measurement changes a qubit state.')
  await user.click(screen.getByRole('button', { name: /Update outcome/ }))

  await user.click(await screen.findByRole('button', { name: 'Back' }))
  expect(
    await screen.findAllByText('Explain how measurement changes a qubit state.'),
  ).toHaveLength(2)
  await user.click(screen.getByRole('button', { name: 'Delete' }))
  await waitFor(() => {
    expect(
      screen.queryAllByText('Explain how measurement changes a qubit state.'),
    ).toHaveLength(0)
  })

  const coursePatch = fetchMock.mock.calls.find(([input, request]) =>
    String(input).endsWith('/courses/course-1') && request?.method === 'PATCH')
  expect(JSON.parse(String(coursePatch?.[1]?.body))).toMatchObject({
    enrollment_open: false,
  })
  const outcomePatch = fetchMock.mock.calls.find(([input, request]) =>
    String(input).endsWith('/outcomes/outcome-1') && request?.method === 'PATCH')
  expect(JSON.parse(String(outcomePatch?.[1]?.body))).toMatchObject({
    kind: 'topic',
    week_number: null,
  })
})
