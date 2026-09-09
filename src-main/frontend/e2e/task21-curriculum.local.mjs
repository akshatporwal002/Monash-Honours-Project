import { chromium, firefox, webkit, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { spawn, execFileSync } from 'node:child_process'
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { resolve } from 'node:path'

const backendRoot = resolve('../backend')
const run = `browser-${Date.now()}`
const scratch = resolve(backendRoot, '.tmp-task21', run)
mkdirSync(scratch, { recursive: true })
const processes = []
function start(command, args, cwd) {
  const child = spawn(command, args, { cwd, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'], env: { ...process.env, PYTHONPATH: backendRoot, TASK21_BROWSER_RUN: run } })
  let output = ''
  child.stdout.on('data', chunk => { output += chunk })
  child.stderr.on('data', chunk => { output += chunk })
  child.on('exit', () => writeFileSync(resolve(scratch, `${processes.indexOf(child)}.log`), output))
  processes.push(child)
  return child
}
let browser
try {
  start(process.env.QUANTUMLEARN_BACKEND_PYTHON, ['tests/task21_browser_server.py'], backendRoot)
  start(process.execPath, ['node_modules/vite/bin/vite.js', '--config', 'e2e/task21-vite.config.ts'], process.cwd())
  let ready = false
  for (let index = 0; index < 60; index++) {
    if (processes.some(child => child.exitCode !== null)) throw new Error('A fixture server exited. Inspect task-owned logs.')
    try { ready = (await fetch('http://127.0.0.1:8171/api/v1/health')).ok && (await fetch('http://localhost:5271')).ok } catch { /* Wait for owned servers. */ }
    if (ready) break
    await new Promise(resolveWait => setTimeout(resolveWait, 1000))
  }
  if (!ready) throw new Error('Fixture servers did not become ready')
  const fixture = JSON.parse(readFileSync(resolve(scratch, 'context.json'), 'utf8'))
  const browserName = process.env.TASK21_BROWSER ?? 'chrome'
  browser = await (browserName === 'firefox' ? firefox.launch({ headless: true }) : browserName === 'webkit' ? webkit.launch({ headless: true }) : chromium.launch({ channel: browserName === 'edge' ? 'msedge' : 'chrome', headless: true }))
  const context = await browser.newContext({ viewport: { width: 1365, height: 900 } })
  const page = await context.newPage()
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  async function login(email, route) {
    await context.clearCookies()
    await page.goto('http://localhost:5271/login')
    await page.getByRole('radio', { name: route === 'educator' ? 'Educator' : 'Student', exact: true }).check()
    await page.getByLabel('Email address').fill(email)
    await page.getByLabel('Password', { exact: true }).fill('quantumlearn-demo')
    await page.getByRole('button', { name: 'Sign in', exact: true }).click()
    await page.waitForURL(`**/${route}`)
  }
  let expectedVersion = 1
  async function openPaths() {
    await page.getByRole('button', { name: 'Learning pathways and diagnostics' }).click()
    await page.getByRole('combobox', { name: /^Course/ }).selectOption(fixture.course_id)
    await expect(page.getByRole('heading', { name: `Three approved activities (version ${expectedVersion})` })).toBeVisible()
  }
  if (process.env.TASK21_PUBLISH === '1') {
    await login(fixture.teacher_email, 'educator')
    await page.goto('http://localhost:5271/educator/courses')
    await page.getByRole('combobox', { name: 'Choose a course to edit' }).click()
    await page.getByRole('option').filter({ hasText: fixture.course_title }).click()
    await page.getByRole('button', { name: 'Manage learning pathways' }).click()
    await page.getByRole('combobox', { name: /^Outcome/ }).selectOption(fixture.outcome_id)
    await page.getByLabel('Publication reason').fill('Checked diagnostic, sources, conditions, and exit guidance.')
    await page.getByRole('button', { name: 'Approve and publish pathway' }).click()
    await expect(page.getByText('Pathway version 2 published.', { exact: true })).toBeVisible()
    expectedVersion = 2
  }
  await login(fixture.student_email, 'student')
  await openPaths()
  await page.getByLabel('Prior-mastery target').selectOption(fixture.target_id)
  await page.getByRole('button', { name: 'Request prior-mastery check' }).click()
  await page.getByLabel('Prior knowledge', { exact: true }).fill('H applied twice restores the input.')
  await page.getByLabel('Reasoning', { exact: true }).fill('The second H reverses the first transformation.')
  await page.getByLabel('I met the stated independent conditions').check()
  await page.getByRole('button', { name: 'Save diagnostic evidence' }).click()
  await expect(page.getByText('needs review', { exact: true })).toBeVisible()
  await page.reload(); await openPaths()
  await expect(page.getByText('The second H reverses the first transformation.', { exact: true })).toBeVisible()
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
  await page.setViewportSize({ width: 390, height: 844 })
  await expect.poll(() => page.locator('#app-sidebar').evaluate(element => element.getBoundingClientRect().right)).toBeLessThanOrEqual(1)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path: resolve(scratch, 'diagnostic-mobile.png'), fullPage: true })
  await page.setViewportSize({ width: 1365, height: 900 })
  await login(fixture.teacher_email, 'educator')
  await page.goto('http://localhost:5271/assessor/review')
  await page.getByRole('button', { name: 'Review learning diagnostics' }).click()
  await expect(page.getByRole('heading', { name: 'Prior-mastery check', exact: true })).toBeVisible()
  await page.getByLabel('Pathway decision').selectOption('advance')
  await page.getByLabel('Independent conditions verified').check()
  await page.getByLabel('Assessor reason').fill('Independent reasoning checked against approved criteria.')
  await page.getByRole('button', { name: 'Confirm pathway decision' }).click()
  await expect(page.getByText('advance', { exact: true })).toBeVisible()
  await login(fixture.student_email, 'student')
  await openPaths()
  await page.getByRole('link', { name: /^Open approved practice:/ }).click()
  await page.waitForURL(`**/student/tasks/${fixture.target_id}`)
  await expect(page.getByText('Optional guidance (independent)', { exact: true })).toBeVisible()
  expect(errors).toEqual([])
  writeFileSync(resolve(scratch, 'result.json'), JSON.stringify({ browser: browserName, status: 'passed', axeViolations: 0, pageErrors: errors,
    checks: [process.env.TASK21_PUBLISH === '1' ? 'educator UI publication' : 'fixture publication', 'approved practice link', 'real login', 'approved pathway', 'diagnostic response', 'reload and evidence history', '390px reflow', 'course assessor confirmation', 'new learner session', 'practice target unlock', 'optional guidance fading'] }, null, 2))
  console.log(`Task 21 authenticated journey passed: ${scratch}`)
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
      if (process.platform === 'win32') { try { execFileSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' }) } catch { /* Already stopped. */ } }
      else child.kill('SIGTERM')
    }
  }
}
