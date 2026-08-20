import axe from 'axe-core'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
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

async function fillRequiredTextFields(user: ReturnType<typeof userEvent.setup>) {
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

const bloomVerificationLabel = 'I verified that this task elicits the selected Bloom process.'
const accessVerificationLabel = 'I verified that each access mode preserves the assessed construct.'

async function fillRequiredFields(user: ReturnType<typeof userEvent.setup>) {
  await fillRequiredTextFields(user)
  await user.click(screen.getByLabelText(bloomVerificationLabel))
  await user.click(screen.getByLabelText(accessVerificationLabel))
}

async function chooseOption(
  user: ReturnType<typeof userEvent.setup>,
  fieldLabel: string,
  optionLabel: string,
) {
  await user.click(screen.getByLabelText(fieldLabel))
  await user.click(await screen.findByRole('option', { name: optionLabel }))
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

test('setup requires explicit Bloom and access verification before creating a draft', async () => {
  const fetchSpy = vi.spyOn(globalThis, 'fetch')
  const user = userEvent.setup()
  renderSetup()
  await fillRequiredTextFields(user)

  await user.click(screen.getByRole('button', { name: 'Save assessment draft' }))

  expect(screen.getByRole('status')).toHaveTextContent('Complete every required field')
  expect(screen.getByRole('alert')).toHaveTextContent('access preservation verification')
  expect(screen.getByRole('alert')).toHaveTextContent('Bloom elicitation verification')
  expect(fetchSpy).not.toHaveBeenCalled()
  expect(screen.queryByRole('button', { name: 'Approve and publish' })).not.toBeInTheDocument()
}, 15_000)

test('changing verified Bloom, task-form, or access inputs requires fresh verification', async () => {
  const fetchSpy = vi.spyOn(globalThis, 'fetch')
  const user = userEvent.setup()
  renderSetup()
  await fillRequiredFields(user)

  await chooseOption(user, 'Bloom process', 'Analyse')
  expect(screen.getByLabelText(bloomVerificationLabel)).not.toBeChecked()
  await user.click(screen.getByRole('button', { name: 'Save assessment draft' }))
  expect(screen.getByRole('alert')).toHaveTextContent('Bloom elicitation verification')

  await user.click(screen.getByLabelText(bloomVerificationLabel))
  fireEvent.change(screen.getByLabelText('Access conditions'), {
    target: { value: 'A revised access mode' },
  })
  expect(screen.getByLabelText(accessVerificationLabel)).not.toBeChecked()

  await user.click(screen.getByLabelText(accessVerificationLabel))
  fireEvent.change(screen.getByLabelText('Task family'), {
    target: { value: 'revised_quantum_circuit' },
  })
  expect(screen.getByLabelText(bloomVerificationLabel)).not.toBeChecked()
  expect(screen.getByLabelText(accessVerificationLabel)).not.toBeChecked()
  await user.click(screen.getByRole('button', { name: 'Save assessment draft' }))
  expect(screen.getByRole('alert')).toHaveTextContent('access preservation verification')
  expect(screen.getByRole('alert')).toHaveTextContent('Bloom elicitation verification')
  expect(fetchSpy).not.toHaveBeenCalled()
}, 15_000)

test('stale save preserves local values and offers conflict recovery', async () => {
  let postedDraft: Record<string, unknown> | null = null
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input)
    if (url.includes('/publish')) return response({ detail: 'internal conflict detail' }, 409)
    if (url.includes('/definitions') && init?.method === 'POST') {
      postedDraft = JSON.parse(String(init.body)) as Record<string, unknown>
      return response(createdDefinition, 201)
    }
    if (url.includes('/history')) return response([createdDefinition])
    throw new Error(`Unexpected request: ${url}`)
  })
  const user = userEvent.setup()
  renderSetup()
  await fillRequiredFields(user)
  screen.getByRole('button', { name: 'Save assessment draft' }).focus()
  await user.keyboard('{Enter}')
  await screen.findByText('Draft saved. Review the pass rule, then approve when ready.')
  expect(postedDraft).toMatchObject({
    permitted_tools: { allowed: ['Qiskit Aer'] },
    instructional_support: { allowed: ['Read the approved source before starting.'] },
    access_conditions: {
      modes: [{ mode: 'Screen reader compatible text circuit', preserves_construct: true }],
    },
    pass_rule_expression: {
      operator: 'ALL_OF',
      clauses: [{ criterion: 'required_evidence' }],
    },
    task_forms: [{
      constraints: {
        access_modes: ['Screen reader compatible text circuit'],
        elicited_bloom_processes: ['APPLY'],
      },
    }],
  })
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
  const onCheckAccess = vi.fn(async () => false)
  const { container } = renderSetup({ onCheckAccess, onAccessRevoked })

  screen.getByRole('button', { name: 'Check assessor access' }).focus()
  expect(screen.getByRole('button', { name: 'Check assessor access' })).toHaveFocus()
  await user.keyboard('{Enter}')
  expect(onCheckAccess).toHaveBeenCalledWith('course-1')
  expect(onAccessRevoked).toHaveBeenCalledOnce()
  expect((await axe.run(container)).violations).toEqual([])
})

test('edited values must be saved as a new version before publication', async () => {
  const revisedDefinition = {
    ...createdDefinition,
    id: 'definition-version-2',
    version: 2,
    claim: 'Revised claim.',
  }
  const requests: Array<{ method: string, body: Record<string, unknown> }> = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input)
    const method = init?.method ?? 'GET'
    const body = init?.body ? JSON.parse(String(init.body)) as Record<string, unknown> : {}
    requests.push({ method, body })
    if (url.includes('/publish')) {
      return response({ ...revisedDefinition, approval_state: 'APPROVED' })
    }
    if (url.includes('/definitions') && method === 'PUT') return response(revisedDefinition)
    if (url.includes('/definitions') && method === 'POST') return response(createdDefinition, 201)
    throw new Error(`Unexpected request: ${url}`)
  })
  const user = userEvent.setup()
  renderSetup()
  await fillRequiredFields(user)
  await user.click(screen.getByRole('button', { name: 'Save assessment draft' }))
  await screen.findByText('Draft saved. Review the pass rule, then approve when ready.')

  await user.clear(screen.getByLabelText('Claim'))
  await user.type(screen.getByLabelText('Claim'), 'Revised claim.')

  expect(screen.getByRole('button', { name: 'Approve and publish' })).toBeDisabled()
  expect(screen.getByText(/Save the current changes as a new draft version/)).toBeInTheDocument()
  expect(screen.getByLabelText('Assigned course')).toBeDisabled()
  expect(screen.getByLabelText('Outcome ID')).toBeDisabled()
  expect(requests.filter((request) => request.method === 'POST')).toHaveLength(1)

  await user.click(screen.getByLabelText(bloomVerificationLabel))
  await user.click(screen.getByLabelText(accessVerificationLabel))
  await user.click(screen.getByRole('button', { name: 'Save assessment draft' }))
  await screen.findByText('Draft revision saved. Review the new version before approval.')
  const update = requests.find((request) => request.method === 'PUT')
  expect(update?.body).toMatchObject({ expected_version: 1, claim: 'Revised claim.' })

  await user.type(screen.getByLabelText('Approval reason'), 'Verified revised evidence rules.')
  await user.click(screen.getByRole('button', { name: 'Approve and publish' }))
  await screen.findByText('Assessment approved and published.')
  const publish = requests.at(-1)
  expect(publish).toMatchObject({ method: 'POST', body: { expected_version: 2 } })
}, 15_000)

test('an edit made during a pending save remains dirty after the request completes', async () => {
  let resolveUpdate!: (value: Response) => void
  const pendingUpdate = new Promise<Response>((resolve) => { resolveUpdate = resolve })
  const updateBodies: Record<string, unknown>[] = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input)
    const method = init?.method ?? 'GET'
    if (url.includes('/definitions') && method === 'PUT') {
      updateBodies.push(JSON.parse(String(init?.body)) as Record<string, unknown>)
      return pendingUpdate
    }
    if (url.includes('/definitions') && method === 'POST') return response(createdDefinition, 201)
    throw new Error(`Unexpected request: ${url}`)
  })
  const user = userEvent.setup()
  renderSetup()
  await fillRequiredFields(user)
  await user.click(screen.getByRole('button', { name: 'Save assessment draft' }))
  await screen.findByText('Draft saved. Review the pass rule, then approve when ready.')

  fireEvent.change(screen.getByLabelText('Claim'), { target: { value: 'First revised claim.' } })
  await user.click(screen.getByLabelText(bloomVerificationLabel))
  await user.click(screen.getByLabelText(accessVerificationLabel))
  await user.click(screen.getByRole('button', { name: 'Save assessment draft' }))
  await waitFor(() => expect(updateBodies).toHaveLength(1))
  fireEvent.change(screen.getByLabelText('Claim'), { target: { value: 'Newer local claim.' } })
  resolveUpdate(response({
    ...createdDefinition,
    id: 'definition-version-2',
    version: 2,
    claim: 'First revised claim.',
  }))

  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent(
    'Draft saved, but newer local changes still need saving.',
  ))
  expect(updateBodies[0]).toMatchObject({ expected_version: 1, claim: 'First revised claim.' })
  expect(screen.getByDisplayValue('Newer local claim.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Approve and publish' })).toBeDisabled()
}, 15_000)
