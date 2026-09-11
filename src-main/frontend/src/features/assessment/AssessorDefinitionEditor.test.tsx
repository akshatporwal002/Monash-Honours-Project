import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import { ApiError, api } from '../../app/api'
import { AssessorSetup } from './AssessorSetup'
import { AssessorDefinitionEditor } from './AssessorDefinitionEditor'
import { definitionEditingApi } from './definitionEditingApi'
import { definitionToDraft, editableRule, newCriterion, validateDefinitionDraft } from './definitionEditing'
import type { AuthoringDefinition } from './definitionEditing'

const assignments = [{ id: 'assignment', course_id: 'course', role: 'assessor' as const,
  version: 1, valid_from: '2026-09-01T00:00:00Z', valid_until: null }]
function fixture(): AuthoringDefinition {
  return {
    id: 'version-3', assessment_definition_id: 'definition', course_id: 'course', outcome_id: 'outcome',
    outcome_version_id: 'outcome-version', version: 3, approval_state: 'DRAFT',
    claim: 'Explain interference', purpose: 'SUMMATIVE', bloom_process: 'ANALYSE', knowledge_dimension: 'CONCEPTUAL',
    supporting_evidence: { nested: { preserved: ['evidence', { source: 'reviewed' }] } },
    contradicting_evidence: [{ arbitrary: true }], insufficient_evidence: { followup: 'human' },
    task_conditions: { review: { policy: 'retain' } }, next_action_contract: { review_required: true },
    permitted_tools: { allowed: ['notes'], limits: { hints: 2 } }, instructional_support: ['worked example'],
    access_conditions: { modes: [{ mode: 'text', preserves_construct: true }], extra: 'retain' },
    transfer_rule: { required: true, fresh_context: { gates: ['X'] } }, evidence_sufficiency: { minimum: 2 },
    formal_result_eligible: false, approved_at: null, approved_by_user_id: null,
    criteria: ['explanation', 'circuit'].map((key, index) => ({ id: `criterion-version-${index}`, version: 3,
      stable_key: key, learner_description: `Describe ${key}`, evidence_description: `Evidence ${key}`,
      mandatory: true, evidence_source_types: ['learner_response', 'simulation'], met_rule: `Met ${key}`,
      not_met_rule: `Missing ${key}`, not_evaluable_rule: `Unavailable ${key}`, evaluator_type: index ? 'mixed' : 'human',
      approved_anchors: { version: 2, examples: [{ response: 'private anchor', metadata: { stage: index } }] },
      critical_error_rules: [{ code: 'critical', details: { retained: true } }],
    })),
    pass_rule_expression: { operator: 'ALL_OF', clauses: [
      { criterion_version_id: 'criterion-version-0' },
      { operator: 'ANY_OF', clauses: [{ criterion_version_id: 'criterion-version-1' }] },
    ] },
    task_forms: [{ id: 'form-version', version: 3, learning_task_id: 'task', task_revision_id: 'revision',
      source_version: 'task-revision:revision', source_digest: 'digest', task_family: 'quantum',
      context: [{ scenario: 'keep' }], constraints: { elicited_bloom_processes: ['ANALYSE'], review_policy: { exact: true } } }],
  }
}
async function open(record = fixture()) {
  vi.spyOn(definitionEditingApi, 'history').mockResolvedValue([record])
  render(<AssessorDefinitionEditor assignments={assignments} initialDefinitionId="definition" />)
  fireEvent.click(screen.getByRole('button', { name: 'Load definition' }))
  await screen.findByText('Latest definition loaded.')
  return record
}
beforeEach(() => vi.restoreAllMocks())

test('loads and edits a multi-criterion draft without losing opaque metadata or stable identities', async () => {
  const original = await open()
  const expected = definitionToDraft(original)
  const save = vi.spyOn(definitionEditingApi, 'save').mockResolvedValue({ ...original, id: 'version-4', version: 4 })
  const publish = vi.spyOn(definitionEditingApi, 'publish')
  fireEvent.change(screen.getByLabelText('Learner description — circuit'), { target: { value: 'Revised circuit description' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save new draft version' }))
  await screen.findByText('Draft version 4 saved. It has not been approved.')
  expect(save).toHaveBeenCalledWith(original, { ...expected, criteria: [expected.criteria[0], { ...expected.criteria[1], learner_description: 'Revised circuit description' }] })
  expect(publish).not.toHaveBeenCalled()
  expect(original.criteria[1].learner_description).toBe('Describe circuit')
})

test('criterion deletion requires removing its pass-rule references and new mandatory criteria need references', async () => {
  await open()
  const save = vi.spyOn(definitionEditingApi, 'save')
  expect(screen.getByRole('button', { name: 'Remove criterion circuit' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Remove pass rule condition 2' }))
  fireEvent.click(screen.getByRole('button', { name: 'Remove criterion circuit' }))
  expect(screen.queryByLabelText('Learner description — circuit')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Add criterion' }))
  for (const label of ['Learner description', 'Evidence description', 'Met rule', 'Not met rule', 'Not evaluable rule']) {
    fireEvent.change(screen.getByLabelText(`${label} — criterion_2`), { target: { value: label } })
  }
  fireEvent.click(screen.getByLabelText('Mandatory — criterion_2'))
  fireEvent.click(screen.getByRole('button', { name: 'Save new draft version' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Include every mandatory criterion')
  expect(save).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Add condition to pass rule' }))
  fireEvent.change(screen.getByLabelText('Pass rule 2 criterion'), { target: { value: 'criterion_2' } })
  save.mockResolvedValue({ ...fixture(), id: 'version-4', version: 4 })
  fireEvent.click(screen.getByRole('button', { name: 'Save new draft version' }))
  await waitFor(() => expect(save).toHaveBeenCalled())
  expect(save.mock.calls[0][1].pass_rule_expression).toEqual({ operator: 'ALL_OF', clauses: [{ criterion: 'explanation' }, { criterion: 'criterion_2' }] })
})

test('invalid policy input and missing criterion descriptions block save and approval', async () => {
  await open()
  const save = vi.spyOn(definitionEditingApi, 'save')
  fireEvent.change(screen.getByLabelText('Approved anchors — circuit'), { target: { value: '{broken' } })
  expect(screen.getByLabelText('Approved anchors — circuit')).toHaveAttribute('aria-invalid', 'true')
  expect(screen.getByRole('button', { name: 'Save new draft version' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Approve saved version' })).toBeDisabled()
  fireEvent.change(screen.getByLabelText('Approved anchors — circuit'), { target: { value: '[{"preserved":true}]' } })
  fireEvent.change(screen.getByLabelText('Met rule — circuit'), { target: { value: ' ' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save new draft version' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Complete the descriptions and evidence rules for circuit')
  expect(save).not.toHaveBeenCalled()
})

test('stale save preserves edits across history reload until explicit server-version selection', async () => {
  const original = await open()
  const save = vi.spyOn(definitionEditingApi, 'save').mockRejectedValue(new ApiError('private error', 409))
  fireEvent.change(screen.getByLabelText('Claim'), { target: { value: 'Local claim' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save new draft version' }))
  await screen.findByText(/This definition changed elsewhere/)
  expect(screen.getByRole('button', { name: 'Save new draft version' })).toBeDisabled()
  vi.mocked(definitionEditingApi.history).mockResolvedValue([{ ...original, id: 'version-4', version: 4, claim: 'Server claim' }, original])
  fireEvent.click(screen.getByRole('button', { name: 'Reload definition history' }))
  await screen.findByText(/History reloaded/)
  expect(screen.getByLabelText('Claim')).toHaveValue('Local claim')
  fireEvent.click(screen.getByText('Version 4 — DRAFT'))
  fireEvent.click(screen.getByRole('button', { name: 'Use version 4 and discard local edits' }))
  expect(screen.getByLabelText('Claim')).toHaveValue('Server claim')
  save.mockResolvedValue({ ...original, version: 5, id: 'version-5' })
  fireEvent.click(screen.getByRole('button', { name: 'Save new draft version' }))
  await waitFor(() => expect(save).toHaveBeenCalledTimes(2))
  expect(save.mock.calls[1][0].version).toBe(4)
})

test('published versions are frozen and revisions remain unapproved until explicit saved-version approval', async () => {
  const original = await open({ ...fixture(), approval_state: 'APPROVED' })
  const user = userEvent.setup()
  expect(screen.getByLabelText('Claim')).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Approve saved version' })).toBeDisabled()
  const saved = { ...fixture(), id: 'version-4', version: 4 }
  const save = vi.spyOn(definitionEditingApi, 'save').mockResolvedValue(saved)
  const publish = vi.spyOn(definitionEditingApi, 'publish').mockResolvedValue({ ...saved, approval_state: 'APPROVED' })
  await user.click(screen.getByRole('button', { name: 'Create draft from this version' }))
  fireEvent.change(screen.getByLabelText('Claim'), { target: { value: 'Revision claim' } })
  await user.click(screen.getByRole('button', { name: 'Save new draft version' }))
  await screen.findByText('Draft version 4 saved. It has not been approved.')
  expect(save.mock.calls[0][0]).toEqual(original)
  expect(publish).not.toHaveBeenCalled()
  fireEvent.change(screen.getByLabelText('Version approval reason'), { target: { value: 'Reviewed complete definition' } })
  await user.click(screen.getByLabelText(/I reviewed every criterion/))
  await user.click(screen.getByRole('button', { name: 'Approve saved version' }))
  await screen.findByText('Version 4 approved and published.')
  expect(publish).toHaveBeenCalledWith(saved, 'Reviewed complete definition')
  expect(screen.getByLabelText('Claim')).toBeDisabled()
})

test.each([403, 404, 422, 500])('save error %s preserves complete local draft and reports a safe error', async (status) => {
  await open()
  vi.spyOn(definitionEditingApi, 'save').mockRejectedValue(new ApiError('private error', status))
  fireEvent.change(screen.getByLabelText('Claim'), { target: { value: 'Retained local claim' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save new draft version' }))
  expect(await screen.findByRole('alert')).not.toHaveTextContent('private error')
  expect(screen.getByLabelText('Claim')).toHaveValue('Retained local claim')
  expect(screen.getByLabelText('Learner description — circuit')).toHaveValue('Describe circuit')
})

test('roundtrip remaps nested version references and rejects incomplete authoring responses', () => {
  const original = fixture()
  const draft = definitionToDraft(original)
  expect(draft.pass_rule_expression).toEqual({ operator: 'ALL_OF', clauses: [
    { criterion: 'explanation' }, { operator: 'ANY_OF', clauses: [{ criterion: 'circuit' }] },
  ] })
  expect(validateDefinitionDraft(draft)).toEqual([])
  expect(() => editableRule({ criterion_version_id: 'missing' })).toThrow('missing from this version')
  expect(() => definitionToDraft({ ...original, outcome_id: '' })).toThrow('lacks authoring metadata')
  expect(validateDefinitionDraft({ ...draft, pass_rule_expression: { criterion: 'deleted' } })).toContain('The pass rule references a removed criterion.')
  expect(newCriterion(draft.criteria, ['criterion_3', 'criterion_4']).stable_key).toBe('criterion_5')
})

test('saving a generated draft opens its course definition with all five criteria and anchors', async () => {
  const original = fixture()
  original.criteria = ['prediction', 'reasoning', 'explanation', 'reflection', 'transfer'].map((key, index) => ({
    ...original.criteria[0], id: `generated-${index}`, stable_key: key, learner_description: `Review ${key}`,
  }))
  original.pass_rule_expression = { operator: 'ALL_OF', clauses: original.criteria.map((criterion) => ({ criterion_version_id: criterion.id })) }
  const tasks = [{ task_id: 'task', title: 'Generated episode', task_type: 'short_answer', outcome_id: 'outcome',
    outcome_statement: 'Explain interference', revision_id: 'revision', content_digest: 'digest', reviewed: true,
    issues: [], source_materials: [{ material_id: 'material', label: 'Reviewed notes' }], generated_assessment_candidate: true }]
  vi.spyOn(api.assessment, 'authoringTasks').mockResolvedValue(tasks)
  vi.spyOn(api.assessment, 'generatedDraft').mockResolvedValue(definitionToDraft(original))
  const generatedSave = vi.spyOn(api.assessment, 'saveGeneratedDraft').mockResolvedValue(original)
  const history = vi.spyOn(definitionEditingApi, 'history').mockResolvedValue([original])
  const save = vi.spyOn(definitionEditingApi, 'save').mockResolvedValue({ ...original, version: 4 })
  const publish = vi.spyOn(definitionEditingApi, 'publish')
  render(<AssessorSetup assignments={assignments} onCheckAccess={async () => true} onAccessRevoked={() => undefined} />)
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Browse saved course tasks' }))
  await user.click(await screen.findByLabelText('Saved course task'))
  await user.click(await screen.findByRole('option', { name: 'Generated episode' }))
  await user.click(screen.getByRole('button', { name: 'Preview generated assessment design' }))
  await user.click(await screen.findByRole('button', { name: 'Save generated assessment draft' }))
  await screen.findByText('Latest definition loaded.')
  expect(generatedSave).toHaveBeenCalledWith('course', 'task', 'revision')
  expect(history).toHaveBeenCalledWith('course', 'definition')
  const editor = within(screen.getByRole('group', { name: 'Definition content' }))
  for (const criterion of original.criteria) {
    expect(editor.getByLabelText(`Learner description — ${criterion.stable_key}`)).toHaveValue(criterion.learner_description)
    expect(JSON.parse((editor.getByLabelText(`Approved anchors — ${criterion.stable_key}`) as HTMLTextAreaElement).value)).toEqual(criterion.approved_anchors)
  }
  await user.click(editor.getByRole('button', { name: 'Save new draft version' }))
  await screen.findByText('Draft version 4 saved. It has not been approved.')
  expect(save).toHaveBeenCalledWith(original, definitionToDraft(original))
  expect(publish).not.toHaveBeenCalled()
})
