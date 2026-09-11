import { apiUrl } from './urls'
import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

for (const method of ['rules', 'human'] as const) {
  test(`assessor authors and publishes ${method} criteria through the real API`, async ({ page, request }) => {
    const fixture = await request.post(`${apiUrl}/e2e/assessment-authoring-fixture`)
    expect(fixture.ok()).toBeTruthy()
    const ids = await fixture.json() as {
      course_id: string; outcome_id: string; task_id: string
      educator_email: string; educator_password: string
    }
    await page.goto('/login')
    await page.getByRole('radio', { name: 'Educator', exact: true }).check()
    await page.getByLabel('Email address').fill(ids.educator_email)
    await page.getByLabel('Password').fill(ids.educator_password)
    await page.getByRole('button', { name: 'Sign in', exact: true }).click()
    await page.getByRole('link', { name: 'Assessment setup' }).click()
    await expect(page.getByRole('heading', { name: 'Assessment setup', exact: true })).toBeVisible()
    const choose = async (label: string, name: string) => {
      await page.getByLabel(label, { exact: true }).scrollIntoViewIfNeeded()
      await expect(page.getByLabel(label, { exact: true })).toBeInViewport()
      await page.getByLabel(label, { exact: true }).focus()
      await page.getByLabel(label, { exact: true }).press('ArrowDown')
      await page.getByRole('option', { name, exact: true }).click()
    }
    await choose('Assigned course', ids.course_id)
    await expect(page.getByLabel('Assessment method')).toContainText('Human assessment')
    const fields = {
      'Outcome ID': ids.outcome_id, 'Outcome wording': 'Recall the Hadamard gate name.',
      Source: 'Approved gate glossary', 'Source version': 'v1', 'Source digest': 'sha256:glossary',
      Claim: 'Recall a gate name.', 'Required evidence': 'The gate name is present.',
      'Mandatory criterion': 'Name the Hadamard gate.', 'Task form ID': ids.task_id,
      'Task family': 'recall', 'Permitted tools': 'None', 'Instructional support': 'None',
      'Access conditions': 'Text', 'Transfer rule': 'No transfer required for this recall criterion.',
    }
    for (const [label, value] of Object.entries(fields)) await page.getByLabel(label, { exact: true }).fill(value)
    await page.getByLabel('I verified that this task elicits the selected Bloom process.').check()
    await page.getByLabel('I verified that each access mode preserves the assessed construct.').check()
    await choose('Bloom process', 'Remember')
    await choose('Assessment method', 'Phrase rules for recall')
    await page.getByRole('button', { name: 'Save assessment draft' }).click()
    await expect(page.getByRole('alert')).toContainText('required or alternative phrases')
    await page.getByLabel('All required phrases').fill('Hadamard')
    await page.getByLabel('Excluded phrases').fill('Hadamard')
    await page.getByRole('button', { name: 'Save assessment draft' }).click()
    await expect(page.getByRole('alert')).toContainText('consistent required and excluded phrases')
    await page.getByLabel('Excluded phrases').fill('Pauli')
    if (method === 'human') {
      await choose('Bloom process', 'Understand')
      await page.getByRole('button', { name: 'Save assessment draft' }).click()
      await expect(page.getByRole('alert')).toContainText('human assessment for this Bloom target')
      await choose('Assessment method', 'Human assessment')
      await expect(page.getByLabel('All required phrases')).toHaveCount(0)
    }
    await page.getByLabel('I verified that this task elicits the selected Bloom process.').check()
    await page.getByLabel('I verified that each access mode preserves the assessed construct.').check()
    const created = page.waitForResponse((response) => response.url().endsWith('/definitions') && response.request().method() === 'POST')
    await page.getByRole('button', { name: 'Save assessment draft' }).click()
    const saved = await created
    expect(saved.status(), await saved.text()).toBe(201)
    expect(saved.request().postDataJSON().criteria[0]).toMatchObject({ evaluator_type: method, approved_anchors: method === 'rules' ? {
      all_of: ['Hadamard'], any_of: [], none_of: ['Pauli'],
    } : {} })
    await page.getByLabel('Approval reason').fill('The fixed recall evidence and exclusions are checked.')
    const incompletePublication = page.waitForResponse((response) => response.url().endsWith('/publish'))
    await page.getByRole('button', { name: 'Approve and publish' }).click()
    const rejected = await incompletePublication
    expect(rejected.status()).toBe(422)
    expect(await rejected.text()).toContain('next_action_contract alignment')
    await page.getByRole('button', { name: 'Complete feedback and adaptation in definition editor' }).click()
    await page.getByText('Next action and review policy', { exact: true }).click()
    await page.getByText('Required alignment structure for these criteria', { exact: true }).click()
    const alignment = JSON.parse(await page.getByLabel('Required alignment JSON').innerText())
    expect(alignment.criterion_feedback).toEqual([{
      criterion_key: 'required_evidence', evidence_source_types: ['learner_response'],
      met: '', not_met: '', not_evaluable: '',
    }])
    alignment.criterion_feedback[0] = {
      ...alignment.criterion_feedback[0],
      met: 'Explain how the submitted gate name satisfies the criterion.',
      not_met: 'Identify the missing or contradictory gate name in the response.',
      not_evaluable: 'Explain why the submitted response cannot establish the required evidence.',
    }
    alignment.result_adaptation = {
      PASS: { feedback: 'Confirm that all mandatory evidence was met.', adaptation: 'No reassessment is needed for this completed outcome.' },
      INCOMPLETE: { feedback: 'Explain which mandatory evidence remains incomplete.', adaptation: 'Direct the learner to the authorised reassessment path for the missing evidence.' },
    }
    const policy = page.getByLabel('Next action and review policy policy', { exact: true })
    await policy.fill(JSON.stringify({ ...JSON.parse(await policy.inputValue()), alignment }, null, 2))
    const revised = page.waitForResponse((response) => response.url().includes('/definitions/') && response.request().method() === 'PUT')
    await page.getByRole('button', { name: 'Save new draft version' }).click()
    const revision = await revised
    expect(revision.status(), await revision.text()).toBe(200)
    expect(revision.request().postDataJSON().criteria[0]).toMatchObject(saved.request().postDataJSON().criteria[0])
    await page.getByLabel('Version approval reason').fill('The criterion, feedback plan, result explanation and reassessment path are reviewed.')
    await page.getByLabel('I reviewed every criterion, the pass rule, Bloom elicitation and access preservation for this saved version.').check()
    const published = page.waitForResponse((response) => response.url().endsWith('/publish'))
    await page.getByRole('button', { name: 'Approve saved version', exact: true }).click()
    const approval = await published
    expect(approval.status(), await approval.text()).toBe(200)
    await expect(page.getByText('Version 2 approved and published.', { exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Approve saved version', exact: true })).toBeDisabled()
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
  })
}
