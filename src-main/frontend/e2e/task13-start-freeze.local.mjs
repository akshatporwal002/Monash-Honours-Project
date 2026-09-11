import { chromium, expect } from '@playwright/test'
import { readFileSync, writeFileSync } from 'node:fs'
import { execFileSync } from 'node:child_process'
import { resolve } from 'node:path'

const backend = resolve('../backend')
const scratch = resolve(backend, '.tmp-task13', process.env.TASK13_BROWSER_RUN ?? 'browser')
const fixture = JSON.parse(readFileSync(resolve(scratch, 'context.json'), 'utf8'))
const python = process.env.TASK13_PYTHON
if (!python) throw new Error('Set TASK13_PYTHON to the backend Python interpreter')
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const page = await browser.newPage({ viewport: { width: 1365, height: 900 } })
const requests = []
page.on('request', request => {
  if (/\/(start|draft|submissions)$/.test(request.url()) && request.method() !== 'GET') {
    requests.push({ path: new URL(request.url()).pathname, method: request.method(), body: request.postDataJSON() })
  }
})
try {
  await page.goto('http://localhost:5233')
  await page.getByLabel('Email address').fill(fixture.student_email)
  await page.getByLabel('Password', { exact: true }).fill('quantumlearn-demo')
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await page.waitForURL('**/student')
  await page.goto(`http://localhost:5233/student/tasks/${fixture.task_id}`)
  await expect(page.getByRole('heading', { name: 'Assessment conditions' })).toBeVisible()
  await expect(page.getByText('unlimited approved conceptual hints')).toBeVisible()
  await page.getByRole('button', { name: 'Start assessed task', exact: true }).click()
  await page.getByRole('radio').first().check()
  await page.getByRole('button', { name: 'Save draft', exact: true }).click()
  await expect(page.getByText('Draft saved.', { exact: true })).toBeVisible()
  const saved = requests.find(request => request.method === 'PUT')
  if (!saved.body.assessment_work_start_id) throw new Error('Draft did not carry work reference')
  await page.reload()
  await expect(page.getByRole('radio').first()).toBeChecked()
  await page.screenshot({ path: resolve(scratch, 'original-draft.png'), fullPage: true })
  const replacement = execFileSync(python, ['tests/task13_browser_server.py', 'republish'], {
    cwd: backend, env: { ...process.env, PYTHONPATH: backend }, encoding: 'utf8', windowsHide: true,
  })
  await page.getByRole('button', { name: 'Submit activity', exact: true }).click()
  await expect(page.getByText(/Assessment conditions changed after work began/)).toBeVisible()
  await expect(page.getByRole('button', { name: 'Submit activity', exact: true })).toBeDisabled()
  await expect(page.getByRole('radio').first()).toBeChecked()
  await page.screenshot({ path: resolve(scratch, 'rule-change-conflict.png'), fullPage: true })
  const submission = requests.find(request => request.path.endsWith('/submissions'))
  if (submission.body.assessment_work_start_id !== saved.body.assessment_work_start_id) throw new Error('Submission replaced original reference')
  await page.reload()
  await expect(page.getByText(/Assessment conditions changed after work began/)).toBeVisible()
  await expect(page.getByRole('radio').first()).toBeChecked()
  await expect(page.getByRole('button', { name: 'Save draft', exact: true })).toBeDisabled()
  await page.screenshot({ path: resolve(scratch, 'reload-preserves-work.png'), fullPage: true })
  writeFileSync(resolve(scratch, 'result.json'), JSON.stringify({ passed: true, requests, replacement: JSON.parse(replacement) }, null, 2))
  console.log('PASS: normal login, explicit start, save, reload, published rule change, conflict, retained work reference and private draft')
} finally {
  await browser.close()
}
