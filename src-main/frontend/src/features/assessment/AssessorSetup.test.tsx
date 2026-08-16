import axe from 'axe-core'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import { AssessorSetup } from './AssessorSetup'

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

const assignments = [{
  id: 'assignment-1', course_id: 'course-1', role: 'assessor' as const, version: 1,
  valid_from: '2026-08-16T00:00:00Z', valid_until: null,
}]

const createdDefinition = {
  id: 'definition-version-1', assessment_definition_id: 'definition-1', course_id: 'course-1',
  outcome_version_id: 'outcome-version-1', version: 1, approval_state: 'DRAFT',
  purpose: 'SUMMATIVE', bloom_process: 'APPLY', knowledge_dimension: 'PROCEDURAL',
  claim: 'Apply a Hadamard gate.', supporting_evidence: {}, contradicting_evidence: {},
  insufficient_evidence: {}, task_conditions: {}, next_action_contract: {}, permitted_tools: [],
  instructional_support: [], access_conditions: [], transfer_rule: {}, evidence_sufficiency: {},
  criteria: [], pass_rule_expression: {}, task_forms: [], formal_result_eligible: true,
  approved_at: null, approved_by_user_id: null,
}

function renderSetup(overrides: Partial<Parameters<typeof AssessorSetup>[0]> = {}) {
  return render(
    <AssessorSetup
      assignments={assignments}
      onCheckAccess={async () => true}
      onAccessRevoked={() => undefined}
      {...overrides}
    />,
  )
}

async function fillRequiredFields(user: ReturnType<typeof userEvent.setup>) {
  const values: Record<string, string> = {
    'Outcome ID': 'outcome-1', 'Outcome wording': 'Apply a Hadamard gate to prepare superposition.',
    Source: 'Week 1 course notes', 'Source version': '2026.08', 'Source digest': 'sha256:source',
    Claim: 'The learner applies the gate and explains the result.',
    'Required evidence': 'A circuit and explanation show the required behaviour.',
    'Mandatory criterion': 'The learner applies the gate and explains the observed state.',
    'Task form ID': 'task-1', 'Task family': 'quantum_circuit', 'Permitted tools': 'Qiskit Aer',
    'Instructional support': 'Read the approved source before starting.',
    'Access conditions': 'Screen reader compatible text circuit', 'Transfer rule': 'Apply the same reasoning in a new circuit.',
  }
  for (const [field, value] of Object.entries(values)) await user.type(screen.getByLabelText(field), value)
}

beforeEach(() => vi.restoreAllMocks())

test('setup blocks approval until every required field is complete', async () => {
  const user = userEvent.setup()
  renderSetup()

  await user.click(screen.getByRole('button', { name: 'Save assessment draft' }))

  expect(screen.getByRole('status')).toHaveTextContent('Complete every required field')
  expect(screen.getByText(/Missing: outcome ID/)).toBeInTheDocument()
  expect(screen.getByText('Save a complete draft before it can be approved.')).toBeInTheDocument()
})

test('pass rule preview has no score weight or percentage language', () => {
  renderSetup()
  const preview = screen.getByLabelText('Pass rule preview')

  expect(preview).toHaveTextContent('every mandatory criterion is met')
  expect(preview).not.toHaveTextContent(/score|weight|percentage|%/i)
})

test('stale save preserves local values and offers conflict recovery', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input)
    if (url.includes('/publish')) return response({ detail: 'internal conflict detail' }, 409)
    if (url.includes('/definitions') && init?.method === 'POST') return response(createdDefinition, 201)
    if (url.includes('/history')) return response([createdDefinition])
    throw new Error(`Unexpected request: ${url}`)
  })
  const user = userEvent.setup()
  renderSetup()
  await fillRequiredFields(user)
  screen.getByRole('button', { name: 'Save assessment draft' }).focus()
  await user.keyboard('{Enter}')
  await screen.findByText('Draft saved. Review the pass rule, then approve when ready.')
  await user.type(screen.getByLabelText('Approval reason'), 'Checked against the approved source.')
  screen.getByRole('button', { name: 'Approve and publish' }).focus()
  await user.keyboard('{Enter}')

  expect(await screen.findByText('This assessment changed elsewhere. Your local values are still available below.')).toBeInTheDocument()
  expect(screen.queryByText('internal conflict detail')).not.toBeInTheDocument()
  expect(screen.getByText('Another version is available')).toBeInTheDocument()
  expect(screen.getByDisplayValue('The learner applies the gate and explains the result.')).toBeInTheDocument()
  expect(screen.getByText(/Your local values have not been replaced/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Reload server history' })).toBeEnabled()
}, 15_000)

test('setup supports keyboard and has no detectable axe violations', async () => {
  const user = userEvent.setup()
  const onAccessRevoked = vi.fn()
  const { container } = renderSetup({ onCheckAccess: async () => false, onAccessRevoked })

  screen.getByRole('button', { name: 'Check assessor access' }).focus()
  expect(screen.getByRole('button', { name: 'Check assessor access' })).toHaveFocus()
  await user.keyboard('{Enter}')
  expect(onAccessRevoked).toHaveBeenCalledOnce()
  expect((await axe.run(container)).violations).toEqual([])
})
