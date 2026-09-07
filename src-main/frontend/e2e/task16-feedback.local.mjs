import { chromium, expect } from '@playwright/test'
import { readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import AxeBuilder from '@axe-core/playwright'

const scratch = resolve('../backend/.tmp-task16', process.env.TASK16_BROWSER_RUN ?? 'browser')
const fixture = JSON.parse(readFileSync(resolve(scratch, 'context.json'), 'utf8'))
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const context = await browser.newContext({ viewport: { width: 1365, height: 900 } })
const page = await context.newPage()
const errors = []
const terminalResponses = []
const requests = []
page.on('pageerror', error => errors.push(error.message))
page.on('request', request => {
  if (/\/(submissions|feedback)$/.test(request.url()) && request.method() === 'POST') {
    requests.push({ path: new URL(request.url()).pathname, method: request.method() })
  }
})
page.on('response', async response => {
  if (/\/submissions\/[^/]+\/feedback$/.test(response.url()) && response.ok()) {
    const body = await response.json()
    if (body.status === 'validated') terminalResponses.push(body)
  }
})
try {
  await page.goto('http://localhost:5266')
  await page.getByLabel('Email address').fill(fixture.student_email)
  await page.getByLabel('Password', { exact: true }).fill('quantumlearn-demo')
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await page.waitForURL('**/student')
  await page.goto(`http://localhost:5266/student/tasks/${fixture.task_id}`)
  await expect(page.getByRole('heading', { name: 'Learning episode' })).toBeVisible()
  await expect(page.getByLabel('Your reflection', { exact: true })).toHaveValue(fixture.reflection)
  await page.getByRole('button', { name: 'Submit activity', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Your feedback', exact: true })).toBeVisible({ timeout: 60000 })
  await expect.poll(() => terminalResponses.length).toBeGreaterThan(0)
  const first = terminalResponses[0]
  expect(first.feedback.assessed.response_version_id).toBe(first.submission_id)
  expect(first.feedback.assessed.criteria).toHaveLength(3)
  expect(first.feedback.assessed.source_claims.length).toBeGreaterThan(0)
  expect(first.feedback.assessed.content_digest).toMatch(/^sha256:/)
  for (const source of first.feedback.assessed.source_claims) {
    expect(fixture.source_ids).toContain(source.source_id)
    expect(source.claim).toBe(source.support_quote)
    await expect(page.getByText(source.support_quote, { exact: true })).toBeVisible()
  }
  await expect(page.getByText(first.feedback.assessed.reflection_prompt, { exact: true })).toBeVisible()
  for (const criterion of first.feedback.assessed.criteria) {
    await expect(page.getByRole('heading', { name: criterion.learner_description, exact: true })).toBeVisible()
  }
  await expect(page.getByText(/^(PASS|INCOMPLETE)$/)).toHaveCount(0)
  await expect(page.getByText('NEVER REVEAL solution', { exact: true })).toHaveCount(0)
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Your feedback', exact: true })).toBeVisible({ timeout: 60000 })
  await expect.poll(() => terminalResponses.length).toBeGreaterThan(1)
  const second = terminalResponses.at(-1)
  expect(second.workflow_run_id).toBe(first.workflow_run_id)
  expect(second.submission_id).toBe(first.submission_id)
  expect(second.feedback.feedback_id).toBe(first.feedback.feedback_id)
  expect(second.feedback.assessed).toEqual(first.feedback.assessed)
  await expect(page.getByText(/^(PASS|INCOMPLETE)$/)).toHaveCount(0)
  const disclosure = page.getByText('Inspect recorded evidence', { exact: true }).first()
  await disclosure.focus()
  await page.keyboard.press('Enter')
  await expect(disclosure.locator('..')).toHaveAttribute('open', '')
  const evidence = first.feedback.assessed.criteria[0].evidence[0]
  if (evidence) await expect(page.getByText(evidence.statement, { exact: true }).first()).toBeVisible()
  const accessibility = await new AxeBuilder({ page }).analyze()
  expect(accessibility.violations).toEqual([])
  expect(errors).toEqual([])
  await page.screenshot({ path: resolve(scratch, 'grounded-feedback.png'), fullPage: true })
  writeFileSync(resolve(scratch, 'result.json'), JSON.stringify({ passed: true, requests, response: first, reload: second, accessibility: accessibility.violations, pageErrors: errors }, null, 2))
  console.log('PASS: authenticated UI submission, grounded criterion feedback, source support, reflection, stable reload, hidden pending results, zero Axe violations and page errors')
} catch (error) {
  await page.screenshot({ path: resolve(scratch, 'failure.png'), fullPage: true })
  writeFileSync(resolve(scratch, 'failure.json'), JSON.stringify({ error: String(error), requests, terminalResponses, pageErrors: errors }, null, 2))
  throw error
} finally {
  await browser.close()
}
