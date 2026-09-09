import { chromium, firefox, webkit, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { spawn, execFileSync } from 'node:child_process'
import { readFileSync, writeFileSync, mkdirSync, appendFileSync } from 'node:fs'
import { resolve } from 'node:path'

const backendRoot = resolve('../backend')
const run = `browser-${Date.now()}`
const scratch = resolve(backendRoot, '.tmp-task22', run)
mkdirSync(scratch, { recursive: true })
const processes = []
function start(command, args, cwd) {
  const child = spawn(command, args, { cwd, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'], env: { ...process.env, PYTHONPATH: backendRoot, TASK22_BROWSER_RUN: run } })
  let output = ''
  child.stdout.on('data', chunk => { output += chunk; appendFileSync(resolve(scratch, `${processes.indexOf(child)}.log`), chunk) })
  child.stderr.on('data', chunk => { output += chunk; appendFileSync(resolve(scratch, `${processes.indexOf(child)}.log`), chunk) })
  child.on('exit', () => writeFileSync(resolve(scratch, `${processes.indexOf(child)}.log`), output))
  processes.push(child)
  writeFileSync(resolve(scratch, 'owned-pids.json'), JSON.stringify(processes.map(item => item.pid)))
  return child
}
let browser
try {
  start(process.env.QUANTUMLEARN_BACKEND_PYTHON, ['tests/task22_browser_server.py'], backendRoot)
  start(process.execPath, ['node_modules/vite/bin/vite.js', '--config', 'e2e/task22-vite.config.ts'], process.cwd())
  let ready = false
  for (let index = 0; index < 60; index++) {
    if (processes.some(child => child.exitCode !== null)) throw new Error('A fixture server exited. Inspect task-owned logs.')
    try { ready = (await fetch('http://127.0.0.1:8172/api/v1/health')).ok && (await fetch('http://localhost:5272')).ok } catch { /* Wait for owned servers. */ }
    if (ready) break
    await new Promise(resolveWait => setTimeout(resolveWait, 1000))
  }
  if (!ready) throw new Error('Fixture servers did not become ready')
  const fixture = JSON.parse(readFileSync(resolve(scratch, 'context.json'), 'utf8'))
  const browserName = process.env.TASK22_BROWSER ?? 'chrome'
  browser = await (browserName === 'firefox' ? firefox.launch({ headless: true }) : browserName === 'webkit' ? webkit.launch({ headless: true }) : chromium.launch({ channel: browserName === 'edge' ? 'msedge' : 'chrome', headless: true }))
  const context = await browser.newContext({ viewport: { width: 1365, height: 900 } })
  const page = await context.newPage()
  page.setDefaultTimeout(15000)
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  async function login(email, route) {
    await context.clearCookies()
    await page.goto('http://localhost:5272/login')
    await page.getByRole('radio', { name: route === 'educator' ? 'Educator' : 'Student', exact: true }).check()
    await page.getByLabel('Email address').fill(email)
    await page.getByLabel('Password', { exact: true }).fill('quantumlearn-demo')
    await page.getByRole('button', { name: 'Sign in', exact: true }).click()
    await page.waitForURL(`**/${route}`)
  }

  await login(fixture.student_email, 'student')
  await page.goto(`http://localhost:5272/student/tasks/${fixture.first_id}`)
  await page.locator('input[type="radio"]').first().check()
  await page.getByRole('button', { name: 'Submit activity', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Next approved activity', exact: true })).toBeVisible({ timeout: 45000 })
  await expect(page.getByRole('button', { name: 'Accept suggestion', exact: true })).toBeEnabled({ timeout: 45000 })
  await page.getByRole('button', { name: 'Accept suggestion', exact: true }).click()
  await expect(page.getByRole('link', { name: 'Open chosen activity' })).toHaveAttribute('href', `/student/tasks/${fixture.next_id}`)
  await page.reload()
  await expect(page.getByRole('link', { name: 'Open chosen activity' })).toBeVisible()
  await page.getByRole('button', { name: 'Defer suggestion' }).click()
  await expect(page.getByText('State: defer', { exact: true })).toBeVisible()
  await page.getByLabel('Approved alternatives').selectOption(fixture.next_id)
  await page.getByRole('button', { name: 'Replace suggestion' }).click()
  await expect(page.getByText('State: replace', { exact: true })).toBeVisible()
  expect((await new AxeBuilder({ page }).include('section:has(> h3)').analyze()).violations).toEqual([])
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path: resolve(scratch, 'activity-mobile.png'), fullPage: true, animations: 'disabled' })
  await page.setViewportSize({ width: 1365, height: 900 })
  await login(fixture.teacher_email, 'educator')
  await page.goto('http://localhost:5272/educator/courses')
  await page.getByRole('combobox', { name: 'Choose a course to edit' }).click()
  await page.getByRole('option').filter({ hasText: fixture.course_title }).click()
  await page.getByRole('button', { name: 'Manage learning pathways' }).click()
  await page.getByLabel('Approved alternatives').selectOption(fixture.next_id)
  await page.getByLabel('Reason for educator override').fill('Continue with the approved practice sequence.')
  await page.getByRole('button', { name: 'Save educator override' }).click()
  await expect(page.getByText('State: educator override', { exact: true })).toBeVisible()
  await login(fixture.student_email, 'student')
  await page.goto(`http://localhost:5272/student/tasks/${fixture.first_id}`)
  await expect(page.getByText('State: educator override', { exact: true })).toBeVisible()
  await page.getByText('Why this suggestion and choice history').click()
  await expect(page.getByText(/Continue with the approved practice sequence./)).toBeVisible()
  await page.getByRole('link', { name: 'Open chosen activity' }).click()
  await page.waitForURL(`**/student/tasks/${fixture.next_id}`)
  expect(errors).toEqual([])
  writeFileSync(resolve(scratch, 'result.json'), JSON.stringify({ browser: browserName, status: 'passed', axeViolations: 0, pageErrors: errors,
    checks: ['ordinary authentication', 'UI submission', 'real feedback pipeline', 'shipped worker', 'model and suggestion', 'accept', 'reload', 'defer', 'replace', 'educator override reason', 'learner reload history', 'open approved activity', '390px reflow'] }, null, 2))

} catch (error) {
  if (browser) {
    const page = browser.contexts()[0]?.pages()[0]
    if (page) {
      writeFileSync(resolve(scratch, 'failure.txt'), await page.locator('body').innerText())
      await page.screenshot({ path: resolve(scratch, 'failure.png'), fullPage: true })
    }
  }
  throw error
} finally {
  if (browser) await browser.close()
  for (const child of processes.reverse()) {
    if (child.exitCode === null) {
      if (process.platform === 'win32') { try { execFileSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore', timeout: 5000 }) } catch { /* Already stopped. */ } }
      else child.kill('SIGTERM')
    }
  }
}
