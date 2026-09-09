import { chromium, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { spawn, execFileSync } from 'node:child_process'
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

const backendRoot = resolve('../backend')
const run = `browser-${Date.now()}`
const scratch = resolve(backendRoot, '.tmp-task20', run)
mkdirSync(scratch, { recursive: true })
const processes = []
function start(command, args, cwd) {
  const child = spawn(command, args, { cwd, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'], env: { ...process.env, PYTHONPATH: backendRoot, TASK20_BROWSER_RUN: run } })
  let output = ''
  child.stdout.on('data', chunk => { output += chunk })
  child.stderr.on('data', chunk => { output += chunk })
  child.on('exit', () => writeFileSync(resolve(scratch, `${processes.indexOf(child)}.log`), output))
  processes.push(child)
  return child
}
let browser
try {
  start(process.env.QUANTUMLEARN_BACKEND_PYTHON, ['tests/task20_browser_server.py'], backendRoot)
  start(process.execPath, ['node_modules/vite/bin/vite.js', '--config', 'e2e/task20-vite.config.ts'], process.cwd())
  let ready = false
  for (let index = 0; index < 60; index++) {
    if (processes.some(child => child.exitCode !== null)) throw new Error('A fixture server exited. Inspect task-owned logs.')
    try { ready = (await fetch('http://127.0.0.1:8170/api/v1/health')).ok && (await fetch('http://localhost:5270')).ok } catch { /* Wait for owned servers. */ }
    if (ready) break
    await new Promise(resolveWait => setTimeout(resolveWait, 1000))
  }
  if (!ready) throw new Error('Fixture servers did not become ready')
  const fixture = JSON.parse(readFileSync(resolve(scratch, 'context.json'), 'utf8'))
  browser = await chromium.launch({ channel: 'chrome', headless: true })
  const context = await browser.newContext({ viewport: { width: 1365, height: 900 } })
  const page = await context.newPage()
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  async function login() {
    await page.goto('http://localhost:5270/login')
    await page.getByLabel('Email address').fill(fixture.student_email)
    await page.getByLabel('Password', { exact: true }).fill('quantumlearn-demo')
    await page.getByRole('button', { name: 'Sign in', exact: true }).click()
    await page.waitForURL('**/student')
  }
  async function openTask() {
    await page.goto(`http://localhost:5270/student/tasks/${fixture.task_id}`)
    await expect(page.getByRole('heading', { name: 'Learning episode', exact: true })).toBeVisible()
    await page.getByText('Change learning preferences', { exact: true }).click()
    await expect(page.getByRole('combobox', { name: 'Pace', exact: true })).toBeVisible()
  }
  await login(); await openTask()
  await page.getByRole('combobox', { name: 'Pace', exact: true }).selectOption('stepwise')
  await page.getByRole('combobox', { name: 'Support format', exact: true }).selectOption('stepwise')
  await page.getByRole('combobox', { name: 'Explanation detail', exact: true }).selectOption('detailed')
  await page.getByRole('combobox', { name: 'Support amount', exact: true }).selectOption('on_request')
  await page.getByRole('combobox', { name: 'Feedback form', exact: true }).selectOption('expandable')
  await page.getByLabel('Show save and break control').check()
  await page.getByLabel('Offer repeat practice where permitted').check()
  await page.getByRole('button', { name: 'Save preferences', exact: true }).click()
  await expect(page.getByText('Preferences saved. Version 1.', { exact: true })).toBeVisible()
  await expect(page.getByRole('navigation', { name: 'Stepwise workspace guide' })).toBeVisible()
  await expect(page.getByText('Open approved hint controls')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Start another practice draft' })).toHaveCount(0)
  await expect(page.getByLabel('Your reflection', { exact: true })).toBeVisible()
  await page.reload()
  await page.getByText('Change learning preferences', { exact: true }).click()
  await expect(page.getByRole('combobox', { name: 'Pace', exact: true })).toHaveValue('stepwise')
  await expect(page.getByRole('combobox', { name: 'Support amount', exact: true })).toHaveValue('on_request')
  await page.getByLabel('Your reflection', { exact: true }).fill('My reflection remains required and available.')
  await page.getByRole('button', { name: 'Save draft and take a break' }).click()
  await expect(page.getByText(/Draft saved. You can take a break/)).toBeVisible()
  await context.clearCookies()
  await login(); await openTask()
  await expect(page.getByRole('combobox', { name: 'Pace', exact: true })).toHaveValue('stepwise')
  await expect(page.getByLabel('Your reflection', { exact: true })).toHaveValue('My reflection remains required and available.')
  await page.getByLabel('Enable non-essential personalisation').uncheck()
  await page.getByRole('button', { name: 'Save preferences', exact: true }).click()
  await expect(page.getByText('Preferences saved. Version 2.', { exact: true })).toBeVisible()
  await expect(page.getByRole('navigation', { name: 'Stepwise workspace guide' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Save draft and take a break' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Request conceptual hint 1' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'I used access support 1' })).toBeVisible()
  await expect(page.getByLabel('Your reflection', { exact: true })).toHaveValue('My reflection remains required and available.')
  await page.getByRole('combobox', { name: 'Pace', exact: true }).selectOption('self_paced')
  await page.getByRole('button', { name: 'Save preferences', exact: true }).click()
  await expect(page.getByText('Preferences saved. Version 3.', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Reset and save defaults' }).click()
  await expect(page.getByText(/Preferences reset and saved/)).toBeVisible()
  await page.getByText('Preference change history', { exact: true }).click()
  await page.getByRole('button', { name: 'Load preference history' }).click()
  await expect(page.getByRole('heading', { name: /Version 1, save/ })).toBeVisible()
  await expect(page.getByRole('heading', { name: /Version 4, reset/ })).toBeVisible()
  const second = await context.newPage()
  await second.goto(`http://localhost:5270/student/tasks/${fixture.task_id}`)
  await second.getByText('Change learning preferences', { exact: true }).click()
  await expect(second.getByRole('combobox', { name: 'Pace', exact: true })).toHaveValue('self_paced')
  await page.getByRole('combobox', { name: 'Pace', exact: true }).selectOption('stepwise')
  await page.getByRole('button', { name: 'Save preferences', exact: true }).click()
  await expect(page.getByText('Preferences saved. Version 5.', { exact: true })).toBeVisible()
  await second.getByLabel('Show save and break control').check()
  await second.getByRole('button', { name: 'Save preferences', exact: true }).click()
  await expect(second.getByRole('button', { name: 'Save preferences', exact: true })).toBeDisabled()
  await expect(second.getByLabel('Show save and break control')).toBeChecked()
  await second.getByRole('button', { name: 'Refresh saved version, keep my draft' }).click()
  await second.getByRole('button', { name: 'Save preferences', exact: true }).click()
  await expect(second.getByText('Preferences saved. Version 6.', { exact: true })).toBeVisible()
  // Drop one response after the real API commits. Retry must recover the same receipt.
  await second.route('**/api/v1/learner-preferences/me', async route => {
    if (route.request().method() !== 'PUT') return route.continue()
    await route.fetch()
    await route.abort('failed')
  }, { times: 1 })
  await second.getByRole('combobox', { name: 'Support format', exact: true }).selectOption('stepwise')
  await second.getByRole('button', { name: 'Save preferences', exact: true }).click()
  await expect(second.getByText(/Preferences could not be saved. Your draft is kept/)).toBeVisible()
  await expect(second.getByRole('combobox', { name: 'Support format', exact: true })).toHaveValue('stepwise')
  await second.getByRole('button', { name: 'Save preferences', exact: true }).click()
  await expect(second.getByText('Preferences saved. Version 7.', { exact: true })).toBeVisible()
  await second.close()
  if (fixture.practice_id) {
    const practice = await context.newPage()
    await practice.goto(`http://localhost:5270/student/tasks/${fixture.practice_id}`)
    await practice.getByText('Change learning preferences', { exact: true }).click()
    await practice.getByLabel('Offer repeat practice where permitted').check()
    await practice.getByRole('button', { name: 'Save preferences', exact: true }).click()
    await expect(practice.getByRole('button', { name: 'Start another practice draft' })).toBeVisible()
    await practice.getByRole('button', { name: 'Start another practice draft' }).click()
    await expect(practice.getByText(/New practice draft started/)).toBeVisible()
    await practice.close()
  }
  const accessibility = await new AxeBuilder({ page }).analyze()
  expect(accessibility.violations).toEqual([])
  await page.getByLabel('Enable non-essential personalisation').focus()
  await page.keyboard.press('Tab')
  await expect(page.getByRole('combobox', { name: 'Pace', exact: true })).toBeFocused()
  await page.setViewportSize({ width: 390, height: 844 })
  await expect.poll(() => page.locator('#app-sidebar').evaluate(element => element.getBoundingClientRect().right)).toBeLessThanOrEqual(1)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path: resolve(scratch, 'preferences-mobile.png'), fullPage: true })
  expect(errors).toEqual([])
  writeFileSync(resolve(scratch, 'result.json'), JSON.stringify({ status: 'passed', axeViolations: 0, pageErrors: errors, checks: ['save all choices', 'reload', 'new authenticated session', 'saved reflection', 'break saves draft', 'opt-out effects', 'access support', 'correction', 'reset history', 'concurrent save conflict', 'committed response loss and replay', 'permitted repeat practice', 'keyboard', '390px reflow'] }, null, 2))
  console.log(`Task 20 authenticated journey passed: ${scratch}`)
} finally {
  if (browser) await browser.close()
  for (const child of processes.reverse()) {
    if (child.exitCode === null) {
      if (process.platform === 'win32') { try { execFileSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' }) } catch { /* Already stopped. */ } }
      else child.kill('SIGTERM')
    }
  }
}
