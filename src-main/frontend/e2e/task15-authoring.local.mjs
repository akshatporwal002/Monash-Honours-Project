import { chromium, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const scratch = resolve('../backend/.tmp-task15', process.env.TASK15_AUTHORING_RUN ?? 'authoring')
const ids = JSON.parse(readFileSync(resolve(scratch, 'context.json'), 'utf8'))
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const context = await browser.newContext({ viewport: { width: 1365, height: 900 } })
const page = await context.newPage()
const choose = async (label, name) => {
  const control = page.getByLabel(label, { exact: true })
  await control.scrollIntoViewIfNeeded()
  await expect(control).toBeInViewport()
  await control.focus()
  await control.press('ArrowDown')
  await page.getByRole('option', { name, exact: true }).click()
}
const outcomes = []
try {
  await page.goto('http://localhost:5241/login')
  await page.getByRole('radio', { name: 'Educator', exact: true }).check()
  await page.getByLabel('Email address').fill('definition-assessor@example.edu')
  await page.getByLabel('Password', { exact: true }).fill('definition-test-password')
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await page.waitForURL('**/educator')
  for (const method of ['rules', 'mixed']) {
    if (method === 'rules') {
      await page.goto('http://localhost:5241/assessor/setup')
      await choose('Assigned course', ids.course_id)
    }
    const fields = {
      'Outcome ID': ids.outcome_id, 'Outcome wording': 'Apply a Hadamard circuit.',
      Source: 'Synthetic approved course source', 'Source version': 'learning-task.v1',
      'Source digest': 'sha256:definition-service-task', Claim: 'Construct the approved circuit structure.',
      'Required evidence': 'A one-qubit circuit with H at qubit zero.',
      'Mandatory criterion': 'Match the ordered circuit structure.', 'Task form ID': ids.task_id,
      'Task family': 'Hadamard structure', 'Permitted tools': 'Circuit simulator',
      'Instructional support': 'Approved conceptual hints', 'Access conditions': 'Keyboard and circuit text',
      'Transfer rule': 'This criterion checks supported circuit structure only.',
    }
    if (method === 'rules') {
      for (const [label, value] of Object.entries(fields)) await page.getByLabel(label, { exact: true }).fill(value)
    }
    await choose('Assessment method', method === 'rules' ? 'Circuit structure rules' : 'Circuit checks with human review')
    await page.getByLabel('Required circuit qubits', { exact: true }).fill('1')
    await page.getByLabel('Required gates, in order', { exact: true }).fill('H 0')
    await page.getByLabel('I verified that this task elicits the selected Bloom process.').check()
    await page.getByLabel('I verified that each access mode preserves the assessed construct.').check()
    const createdResponse = page.waitForResponse(response => response.url().includes('/definitions') && response.request().method() === (method === 'rules' ? 'POST' : 'PUT'))
    await page.getByRole('button', { name: 'Save assessment draft' }).click()
    const created = await createdResponse
    expect(created.status()).toBe(method === 'rules' ? 201 : 200)
    expect(created.request().postDataJSON().criteria[0]).toMatchObject({
      evaluator_type: method,
      approved_anchors: { kind: 'circuit_v1', stage: 'supported', qubits: 1, operations: [{ gate: 'h', targets: [0] }] },
    })
    await page.getByLabel('Approval reason', { exact: true }).fill('Synthetic structural claim and exact source reviewed. Human review remains required for formal results.')
    const publishedResponse = page.waitForResponse(response => response.url().endsWith('/publish'))
    await page.getByRole('button', { name: 'Approve and publish' }).click()
    const published = await publishedResponse
    expect(published.status()).toBe(200)
    const definition = await published.json()
    expect(definition.criteria[0].evaluator_type).toBe(method)
    const accessibility = (await new AxeBuilder({ page }).analyze()).violations
    expect(accessibility).toEqual([])
    await page.screenshot({ path: resolve(scratch, `published-${method}.png`), fullPage: true })
    outcomes.push({ method, definition_id: definition.id, accessibility })
  }
  writeFileSync(resolve(scratch, 'result.json'), JSON.stringify({ passed: true, outcomes }, null, 2))
  console.log('PASS: real scoped circuit rules and mixed human publication, exact structural anchors, axe')
} catch (error) {
  await page.screenshot({ path: resolve(scratch, 'failure.png'), fullPage: true })
  writeFileSync(resolve(scratch, 'failure.txt'), await page.locator('body').innerText())
  throw error
} finally { await browser.close() }
