import { chromium, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const scratch = resolve('../backend/.tmp-task14', process.env.TASK14_AUTHORING_RUN ?? 'authoring')
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
try {
  await page.goto('http://localhost:5240/login')
  await page.getByRole('radio', { name: 'Educator', exact: true }).check()
  await page.getByLabel('Email address').fill('definition-assessor@example.edu')
  await page.getByLabel('Password', { exact: true }).fill('definition-test-password')
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await page.waitForURL('**/educator')
  await page.goto('http://localhost:5240/educator/courses')
  await choose('Choose a course to edit', /QNT601/)
  await page.getByRole('button', { name: 'Review saved tasks', exact: true }).click()
  await choose('Task to review', 'Interference analysis')
  await page.getByLabel('Include a separate unaided transfer stage').uncheck()
  await page.getByLabel('Include a separate unaided transfer stage').check()
  await page.getByLabel('Approved conceptual hints', { exact: true }).fill('Consider the amplitudes.\nReview the input state.')
  await page.getByLabel('Accessibility support for both stages', { exact: true }).fill('Keyboard and circuit text')
  await page.getByLabel('Fresh transfer prompt (required)', { exact: true }).fill('Apply H to a fresh input.')
  await page.getByLabel('Fresh transfer starter code', { exact: true }).fill('  circuit.h(0)\n')
  await page.getByLabel('Private transfer solution', { exact: true }).fill('PRIVATE approved educator guidance')
  const savedResponse = page.waitForResponse(response => response.request().method() === 'PATCH' && response.url().includes(ids.task_id))
  await page.getByRole('button', { name: 'Save task revision', exact: true }).click()
  expect((await savedResponse).ok()).toBeTruthy()
  await expect(page.getByText('Task saved. Review the saved revision before approving it.')).toBeVisible()
  await page.getByLabel('Review reason (required)', { exact: true }).fill('Synthetic source, supported hints, fresh prompt and private guidance checked.')
  await page.getByRole('button', { name: 'Submit for review', exact: true }).click()
  await expect(page.getByText('Review action recorded.')).toBeVisible()
  await page.getByLabel('Review reason (required)', { exact: true }).fill('Synthetic reviewed source and exact episode plan approved.')
  await expect(page.getByRole('button', { name: 'Approve task', exact: true })).toBeEnabled()
  const reviewedResponse = page.waitForResponse(response => response.url().includes('/review') && response.request().method() === 'POST')
  await page.getByRole('button', { name: 'Approve task', exact: true }).click()
  expect((await reviewedResponse).ok()).toBeTruthy()
  await expect(page.getByText('Review action recorded.')).toBeVisible()
  await page.getByRole('button', { name: 'Reload saved review' }).click()
  await expect(page.getByLabel('Fresh transfer starter code', { exact: true })).toHaveValue('  circuit.h(0)\n')
  await expect(page.getByLabel('Private transfer solution', { exact: true })).toHaveValue('PRIVATE approved educator guidance')
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
  await page.screenshot({ path: resolve(scratch, 'reviewed-plan.png'), fullPage: true })
  await page.getByRole('link', { name: 'Assessment setup', exact: true }).click()
  await choose('Assigned course', ids.course_id)
  const fields = {
    'Outcome ID': ids.outcome_id, 'Outcome wording': 'Apply a Hadamard circuit.',
    Source: 'Synthetic approved course source', 'Source version': 'learning-task.v1',
    'Source digest': 'sha256:definition-service-task', Claim: 'Apply the gate in supported and fresh work.',
    'Required evidence': 'Prediction, explanation, and a fresh circuit.',
    'Mandatory criterion': 'Explain and apply the Hadamard gate.', 'Task form ID': ids.task_id,
    'Task family': 'Hadamard episode', 'Permitted tools': 'Circuit simulator',
    'Instructional support': 'Unlimited approved conceptual hints during supported work',
    'Access conditions': 'Keyboard and circuit text', 'Transfer rule': 'Separate unaided fresh application',
  }
  for (const [label, value] of Object.entries(fields)) await page.getByLabel(label, { exact: true }).fill(value)
  await page.getByLabel('I verified that this task elicits the selected Bloom process.').check()
  await page.getByLabel('I verified that each access mode preserves the assessed construct.').check()
  const createdResponse = page.waitForResponse(response => response.url().endsWith('/definitions') && response.request().method() === 'POST')
  await page.getByRole('button', { name: 'Save assessment draft' }).click()
  const created = await createdResponse
  expect(created.status()).toBe(201)
  const definition = await created.json()
  expect(definition.task_forms[0].constraints.episode_plan.transfer).toMatchObject({
    prompt: 'Apply H to a fresh input.', starter_code: '  circuit.h(0)\n',
    solution: { answer: 'PRIVATE approved educator guidance' },
  })
  await page.getByLabel('Approval reason', { exact: true }).fill('Synthetic APPLY evidence, stage boundaries and access conditions reviewed.')
  const publishedResponse = page.waitForResponse(response => response.url().endsWith('/publish'))
  await page.getByRole('button', { name: 'Approve and publish' }).click()
  expect((await publishedResponse).status()).toBe(200)
  const accessibility = (await new AxeBuilder({ page }).analyze()).violations
  expect(accessibility).toEqual([])
  await page.screenshot({ path: resolve(scratch, 'published-plan.png'), fullPage: true })
  writeFileSync(resolve(scratch, 'result.json'), JSON.stringify({ passed: true, definition_id: definition.id, accessibility }, null, 2))
  console.log('PASS: educator plan authoring, exact saved review, whitespace reload, frozen private plan, human APPLY publication, axe')
} catch (error) {
  await page.screenshot({ path: resolve(scratch, 'failure.png'), fullPage: true })
  writeFileSync(resolve(scratch, 'failure.txt'), await page.locator('body').innerText())
  throw error
} finally { await browser.close() }
