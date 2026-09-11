import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { GeneratedAssessmentDraft } from './GeneratedAssessmentDraft'

beforeEach(() => vi.restoreAllMocks())

const proposal = {
  claim: 'Apply the Hadamard transformation', purpose: 'SUMMATIVE', bloom_process: 'APPLY', knowledge_dimension: 'PROCEDURAL',
  criteria: ['prediction', 'reasoning', 'explanation', 'reflection', 'transfer'].map(stable_key => ({
    stable_key, learner_description: `Review ${stable_key}`, met_rule: 'Explain the evidence relationship',
    not_met_rule: 'Missing relationship', evidence_description: 'Original response evidence',
    not_evaluable_rule: 'Missing provenance', approved_anchors: { met: ['Example relationship'], not_met: ['Bare answer'] },
  })),
}
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

test.each([false, true])('generated assessment design requires an explicit draft save and respects stale review: %s', async stale => {
  const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation(async (_url, init) => {
    if (init?.method === 'POST') return stale ? response({ detail: 'Reload the current reviewed task' }, 409) : response({ version: 1 })
    return response(proposal)
  })
  render(<GeneratedAssessmentDraft courseId="course" taskId="task" revisionId="reviewed-revision" />)
  const user = userEvent.setup()
  expect(fetch).not.toHaveBeenCalled()
  await user.click(screen.getByRole('button', { name: 'Preview generated assessment design' }))
  expect(await screen.findByText('Review transfer')).toBeVisible()
  expect(screen.getByText(/All 5 criteria are required/)).toBeVisible()
  expect(fetch.mock.calls.every(([, init]) => init?.method !== 'POST')).toBe(true)
  await user.click(screen.getByRole('button', { name: 'Save generated assessment draft' }))
  if (stale) {
    expect(await screen.findByRole('alert')).toHaveTextContent('Reload the current reviewed task')
    expect(screen.queryByRole('button', { name: 'Save generated assessment draft' })).not.toBeInTheDocument()
  } else {
    expect(await screen.findByRole('status')).toHaveTextContent('It has not been approved')
    expect(screen.getByRole('button', { name: 'Save generated assessment draft' })).toBeDisabled()
  }
  const writes = fetch.mock.calls.filter(([, init]) => init?.method === 'POST')
  expect(writes).toHaveLength(1)
  expect(String(writes[0][0])).toContain('generated-assessment-draft?expected_revision_id=reviewed-revision')
})
