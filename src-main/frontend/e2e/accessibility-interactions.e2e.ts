import AxeBuilder from '@axe-core/playwright'
import { expect, test } from './fixtures/assessment'
import type { Page } from '@playwright/test'

async function expectReflow(page: Page) {
  expect(page.viewportSize()?.width).toBe(320)
  await expect.poll(() => page.evaluate(() =>
    document.documentElement.scrollWidth - document.documentElement.clientWidth,
  )).toBeLessThanOrEqual(0)
}

async function expectAccessible(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']).analyze()
  expect(results.violations.map(({ id, nodes }) => ({ id, targets: nodes.map(node => node.target) }))).toEqual([])
}

test('login validates by keyboard and reflows with enlarged text', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 720 })
  await page.goto('/login')
  await page.getByLabel('Email address').focus()
  await page.keyboard.press('Tab')
  await expect(page.getByLabel('Password')).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(page.getByLabel('Email address')).toBeFocused()
  await page.getByLabel('Email address').fill('invalid@example.test')
  await page.keyboard.press('Tab')
  await page.keyboard.type('incorrect-password')
  await page.keyboard.press('Enter')
  await expect(page.getByRole('alert')).toBeVisible()
  await expectAccessible(page)
  await expectReflow(page)
  // CSS text enlargement complements the 320px reflow check; it is not native browser zoom.
  await page.addStyleTag({ content: 'html { font-size: 200%; }' })
  await expectReflow(page)
  await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeVisible()
})

test('preference load failure is announced and keyboard retry restores usable controls', async ({ page, assessmentReview }) => {
  await page.goto('/login')
  await page.getByLabel('Email address').fill(assessmentReview.student_email)
  await page.getByLabel('Password').fill(assessmentReview.student_password)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page).toHaveURL(/\/student$/)
  await page.route('**/api/v1/students/me/preferences', route => route.fulfill({
    status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Unavailable' }),
  }))
  await page.goto('/student/preferences')
  await expect(page.getByRole('alert')).toHaveText('Preferences could not be loaded.')
  await expectAccessible(page)
  const retry = page.getByRole('button', { name: 'Reload learning preferences' })
  await retry.focus()
  await page.unroute('**/api/v1/students/me/preferences')
  await page.keyboard.press('Enter')
  await expect(page.getByLabel('Presentation pace')).toBeVisible()
  await expect(page.getByLabel('Presentation pace')).toBeFocused()
  await page.keyboard.press('ArrowDown')
  await page.keyboard.press('Tab')
  await expect(page.getByLabel('Preferred format')).toBeFocused()
  await page.getByRole('button', { name: 'Save preferences', exact: true }).focus()
  const saved = page.waitForResponse(response => response.url().endsWith('/students/me/preferences') && response.request().method() === 'PUT')
  await page.keyboard.press('Enter')
  expect((await saved).status()).toBe(201)
  await expect(page.getByRole('status').filter({ hasText: 'Learning preferences saved.' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Save preferences', exact: true })).toBeFocused()
  await page.setViewportSize({ width: 320, height: 720 })
  await expectReflow(page)
  await expectAccessible(page)
})
