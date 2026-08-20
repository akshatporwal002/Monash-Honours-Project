import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import type { Page, TestInfo } from '@playwright/test'

/**
 * Axe scan per authenticated route (plan 006 Step 10). Every route in the
 * design route table that the demo data supports is loaded, awaited on its
 * page heading, and scanned. Serious and critical violations fail the test;
 * lower-impact findings are attached to the report for the record.
 */

async function openDemoWorkspace(
  page: Page,
  role: 'Student' | 'Educator' | 'Admin',
) {
  await page.goto('/login')
  await page.getByRole('radio', { name: role, exact: true }).check()
  await page.getByRole('button', { name: 'Load demo workspace' }).click()
}

async function expectNoSeriousViolations(
  page: Page,
  testInfo: TestInfo,
  routeName: string,
) {
  const results = await new AxeBuilder({ page }).analyze()
  if (results.violations.length > 0) {
    await testInfo.attach(`axe${routeName.replaceAll('/', '-') || '-root'}`, {
      body: JSON.stringify(results.violations, null, 2),
      contentType: 'application/json',
    })
  }
  const blocking = results.violations
    .filter((violation) => violation.impact === 'serious' || violation.impact === 'critical')
    .map((violation) => ({
      id: violation.id,
      impact: violation.impact,
      help: violation.help,
      targets: violation.nodes.map((node) => node.target),
    }))
  expect(blocking, `serious/critical axe violations on ${routeName}`).toEqual([])
}

test('login page has no serious accessibility violations', async ({ page }, testInfo) => {
  await page.goto('/login')
  await expect(
    page.getByRole('heading', { name: 'Sign in to LearnLens', level: 1 }),
  ).toBeVisible()
  await expectNoSeriousViolations(page, testInfo, '/login')
})

test('student routes have no serious accessibility violations', async ({ page }, testInfo) => {
  await openDemoWorkspace(page, 'Student')

  await expect(page).toHaveURL(/\/student$/)
  await expect(page.getByRole('heading', { name: 'Welcome back, Alex' })).toBeVisible()
  await expectNoSeriousViolations(page, testInfo, '/student')

  await page.getByRole('button', { name: 'Continue learning' }).click()
  await expect(page).toHaveURL(/\/student\/tasks\/[^/]+$/)
  await expect(
    page.getByRole('heading', { name: 'Choose the superposition statement', level: 1 }),
  ).toBeVisible()
  await expectNoSeriousViolations(page, testInfo, '/student/tasks/:taskId')
})

test('educator and assessor routes have no serious accessibility violations', async ({ page }, testInfo) => {
  await openDemoWorkspace(page, 'Educator')

  await expect(page).toHaveURL(/\/educator$/)
  await expect(page.getByRole('heading', { name: 'Learning pulse' })).toBeVisible()
  await expectNoSeriousViolations(page, testInfo, '/educator')

  await page.goto('/educator/courses')
  await expect(
    page.getByRole('heading', { name: 'Configure a grounded course' }),
  ).toBeVisible()
  await expectNoSeriousViolations(page, testInfo, '/educator/courses')

  await page.goto('/educator/students')
  await expect(page.getByRole('heading', { name: 'Students', exact: true })).toBeVisible()
  await expectNoSeriousViolations(page, testInfo, '/educator/students')

  await page.goto('/educator/analytics')
  await expect(page.getByRole('heading', { name: 'Cohort analytics' })).toBeVisible()
  await expectNoSeriousViolations(page, testInfo, '/educator/analytics')

  // The demo educator carries an assessor assignment when the backend seeds
  // one; skip the assessor routes gracefully when it does not.
  const hasAssessorAccess =
    (await page.getByRole('link', { name: 'Assessment setup' }).count()) > 0
  if (!hasAssessorAccess) {
    testInfo.annotations.push({
      type: 'skipped-routes',
      description: 'Demo educator has no assessor assignment; /assessor/* not scanned.',
    })
    return
  }

  await page.goto('/assessor/setup')
  await expect(page.getByRole('heading', { name: 'Assessment setup' })).toBeVisible()
  await expectNoSeriousViolations(page, testInfo, '/assessor/setup')

  await page.goto('/assessor/review')
  await expect(page.getByRole('heading', { name: 'Assessment review queue' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Response and evidence' })).toBeVisible()
  await expectNoSeriousViolations(page, testInfo, '/assessor/review')
})

test('admin routes and the not-found page have no serious accessibility violations', async ({ page }, testInfo) => {
  await openDemoWorkspace(page, 'Admin')

  await expect(page).toHaveURL(/\/admin$/)
  await expect(page.getByRole('heading', { name: 'System overview' })).toBeVisible()
  await expectNoSeriousViolations(page, testInfo, '/admin')

  await page.goto('/admin/users')
  await expect(page.getByRole('heading', { name: 'Users' })).toBeVisible()
  await expectNoSeriousViolations(page, testInfo, '/admin/users')

  await page.goto('/admin/courses')
  await expect(page.getByRole('heading', { name: 'Courses' })).toBeVisible()
  await expectNoSeriousViolations(page, testInfo, '/admin/courses')

  await page.goto('/admin/settings')
  await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible()
  await expectNoSeriousViolations(page, testInfo, '/admin/settings')

  // Unknown and unauthorised paths render the same not-found page.
  await page.goto('/this-route-does-not-exist')
  await expect(
    page.getByRole('heading', {
      name: 'This page does not exist or is not available to your account',
      level: 1,
    }),
  ).toBeVisible()
  await expect(page.getByRole('link', { name: 'Go to your workspace' })).toBeVisible()
  await expectNoSeriousViolations(page, testInfo, '/this-route-does-not-exist (not found)')
})
