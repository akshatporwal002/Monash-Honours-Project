import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

for (const method of ['rules', 'human'] as const) {
  test(`assessor authors and publishes ${method} criteria through the real API`, async ({ page, request }) => {
    const fixture = await request.post('http://127.0.0.1:4180/e2e/assessment-authoring-fixture')
    expect(fixture.ok()).toBeTruthy()
    const ids = await fixture.json() as { course_id: string; outcome_id: string; task_id: string }
    await page.goto('/login')
    await page.getByRole('radio', { name: 'Educator', exact: true }).check()
    await page.getByLabel('Email address').fill('educator@quantumlearn.demo')
    await page.getByLabel('Password').fill('quantumlearn-demo')
    await page.getByRole('button', { name: 'Sign in', exact: true }).click()
    await page.getByRole('link', { name: 'Assessment setup' }).click()
    await expect(page.getByRole('heading', { name: 'Assessment setup', exact: true })).toBeVisible()
    const choose = async (label: string, name: string) => {
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
    expect(saved.status()).toBe(201)
    expect(saved.request().postDataJSON().criteria[0]).toMatchObject({ evaluator_type: method, approved_anchors: method === 'rules' ? {
      all_of: ['Hadamard'], any_of: [], none_of: ['Pauli'],
    } : {} })
    await page.getByLabel('Approval reason').fill('The fixed recall evidence and exclusions are checked.')
    const published = page.waitForResponse((response) => response.url().endsWith('/publish'))
    await page.getByRole('button', { name: 'Approve and publish' }).click()
    expect((await published).status()).toBe(200)
    await expect(page.getByRole('button', { name: 'Approve and publish' })).toBeDisabled()
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
  })
}
