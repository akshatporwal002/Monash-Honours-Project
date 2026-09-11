import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, expect, test, vi } from 'vitest'
import { StudyParticipationPage } from '../features/research/StudyParticipationPage'
import { ResearchStudyPage } from '../features/research/ResearchStudyPage'
import { studyApi } from '../features/research/api'
import type { AuthUser } from '../app/types'

vi.mock('../features/research/api', async importOriginal => ({ ...await importOriginal<typeof import('../features/research/api')>(), studyApi: {
  participation: vi.fn(), forms: vi.fn(), submit: vi.fn(), governance: vi.fn(), plan: vi.fn(), packet: vi.fn(), decision: vi.fn(), records: vi.fn(), export: vi.fn(),
} }))
const student: AuthUser = { id: 3, role: 'student', email: 'synthetic@example.invalid', full_name: 'Synthetic', scoped_assignments: [] }
const researcher: AuthUser = { ...student, id: 4, role: 'educator', scoped_assignments: [{ id: 'grant', course_id: 'course', role: 'research', version: 1, valid_from: '', valid_until: null }] }
function page(research = false, user = research ? researcher : student) {
  return render(<MemoryRouter initialEntries={['/study/study/course']}><Routes><Route path="/study/:studyId/:courseId" element={research ? <ResearchStudyPage user={user} /> : <StudyParticipationPage user={user} />} /></Routes></MemoryRouter>)
}
beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(studyApi.participation).mockResolvedValue({ study_id: 'study', scope_id: 'scope', revision: 7, production_active: false, consent: null, scope: { consent_version: 'external-v1', fields: ['instrument.choice_code'], purposes: ['study_instruments'] } } as Awaited<ReturnType<typeof studyApi.participation>>)
  vi.mocked(studyApi.forms).mockResolvedValue([])
  vi.mocked(studyApi.plan).mockResolvedValue({ id: 'plan', revision: 1, plan: { conditions: ['a'], stages: [{ stage: 'T0_BASELINE', form_id: 'form' }], rubrics: [] } })
})
test('consent requires explicit acknowledgement; withdrawal submits only self and no fields', async () => {
  page()
  expect(await screen.findByText(/Current choice/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Record consent' })).toBeDisabled()
  fireEvent.click(screen.getByLabelText('instrument.choice_code'))
  fireEvent.click(screen.getByLabelText(/I have read/))
  expect(screen.getByRole('button', { name: 'Record consent' })).toBeEnabled()
  fireEvent.click(screen.getByRole('button', { name: 'Withdraw participation' }))
  await waitFor(() => expect(studyApi.governance).toHaveBeenCalledWith('study', expect.objectContaining({ expected_revision: 7, decision: expect.objectContaining({ subject_user_id: 3, decision: 'withdrawn', fields: [], purposes: [] }) })))
})
test('skipped answer is submitted explicitly and failure preserves the response', async () => {
  vi.mocked(studyApi.forms).mockResolvedValue([{ allocation_id: 'allocation', stages: [{ stage: 'T0_BASELINE', form: { id: 'form', version: 1, definition: { title: 'Synthetic item', items: [{ item_id: 'one', prompt: 'Synthetic question', response_type: 'choice', choices: ['a', 'b'] }] } } }] }] as Awaited<ReturnType<typeof studyApi.forms>>)
  vi.mocked(studyApi.submit).mockRejectedValue(new Error('denied'))
  page()
  fireEvent.change(await screen.findByLabelText('Response status'), { target: { value: 'participant_skipped' } })
  fireEvent.click(screen.getByRole('button', { name: 'Submit study response' }))
  await screen.findByText(/Your answers are still here/)
  expect(studyApi.submit).toHaveBeenCalledWith('study', 'course', expect.objectContaining({ allocation_id: 'allocation', record: expect.objectContaining({ subject_user_id: 3, stage: 'T0_BASELINE', answers: [{ item_id: 'one', missing_reason: 'participant_skipped' }] }) }))
  expect(screen.getByLabelText('Response status')).toHaveValue('participant_skipped')
})
test('researcher needs the matching course assignment', () => {
  page(true, { ...researcher, scoped_assignments: [] })
  expect(screen.getByRole('alert')).toHaveTextContent('research assignment')
  expect(studyApi.plan).not.toHaveBeenCalled()
})
test('assigned packet displays the supplied rubric and submits a coded rating', async () => {
  vi.mocked(studyApi.packet).mockResolvedValue({ id: 'packet', stage: 'T0_BASELINE', rubric: { code: 'rubric', wording: 'Synthetic rubric', values: ['observed'] }, redacted_evidence: 'Synthetic blinded evidence' })
  page(true)
  fireEvent.change(screen.getByLabelText('Packet reference'), { target: { value: 'packet' } })
  fireEvent.click(screen.getByRole('button', { name: 'Open assigned packet' }))
  await screen.findByText('Synthetic blinded evidence')
  fireEvent.change(screen.getByLabelText('Study rating'), { target: { value: 'observed' } })
  fireEvent.click(screen.getByRole('button', { name: 'Record study rating' }))
  await waitFor(() => expect(studyApi.decision).toHaveBeenCalledWith('study', 'course', expect.objectContaining({ decision: { kind: 'rating', packet_id: 'packet', value_code: 'observed' } })))
})
test('export sends only checked fields and stages', async () => {
  page(true)
  const field = await screen.findByLabelText('study.condition')
  fireEvent.click(field)
  fireEvent.click(await screen.findByLabelText('T0_BASELINE'))
  fireEvent.click(screen.getByRole('button', { name: 'Download study export' }))
  await waitFor(() => expect(studyApi.export).toHaveBeenCalledWith('study', 'course', ['study.condition'], ['T0_BASELINE'], 'json'))
})
