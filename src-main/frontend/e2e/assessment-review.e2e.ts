import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

const actionsByProject = {
  'chrome-stable': 'Withhold result',
  'edge-stable': 'Return for review',
  firefox: 'Confirm result',
  webkit: 'Override result',
} as const

async function measurePageOverflow(page: import('@playwright/test').Page) {
  return await page.evaluate(() => ({
    body: {
      bounds: document.body.getBoundingClientRect().toJSON(),
      clientWidth: document.body.clientWidth,
      scrollWidth: document.body.scrollWidth,
      styles: {
        margin: getComputedStyle(document.body).margin,
        minWidth: getComputedStyle(document.body).minWidth,
        padding: getComputedStyle(document.body).padding,
        width: getComputedStyle(document.body).width,
      },
    },
    clientWidth: document.documentElement.clientWidth,
    innerWidth: window.innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    // Widest right-edge offenders first: a closed off-canvas drawer sits at a
    // negative left by design, so reporting those first hides the real cause.
    overflowingElements: [...document.querySelectorAll<HTMLElement>('body *')]
      .map((element) => ({
        className: String(element.className),
        tagName: element.tagName,
        right: Math.round(element.getBoundingClientRect().right),
        left: Math.round(element.getBoundingClientRect().left),
        text: element.textContent?.trim().slice(0, 60),
      }))
      .filter((entry) => entry.right > document.documentElement.clientWidth)
      .sort((first, second) => second.right - first.right)
      .slice(0, 8),
  }))
}

/**
 * WCAG 2.2 reflow: no horizontal page scroll at the tested width. Polled
 * because a viewport resize is not synchronous with relayout in every engine;
 * the assertion itself is unchanged, it just measures a settled layout.
 */
async function expectNoHorizontalPageOverflow(page: import('@playwright/test').Page) {
  await expect
    .poll(async () => {
      const dimensions = await measurePageOverflow(page)
      return dimensions.scrollWidth - dimensions.clientWidth
    }, {
      message: `horizontal overflow at ${JSON.stringify(await measurePageOverflow(page))}`,
      timeout: 5_000,
    })
    .toBeLessThanOrEqual(0)
}

test('assessor reviews frozen evidence and records an action by keyboard', async ({ page }, testInfo) => {
  const actionLabel = actionsByProject[testInfo.project.name as keyof typeof actionsByProject]
  expect(actionLabel).toBeDefined()

  const reviewRequests: Array<{ method: string; path: string; status: number }> = []
  page.on('response', (response) => {
    const url = new URL(response.url())
    if (!url.pathname.includes('/api/v1/assessment/')) return
    reviewRequests.push({
      method: response.request().method(),
      path: url.pathname,
      status: response.status(),
    })
  })

  await page.goto('/login')
  await page.getByRole('radio', { name: 'Educator', exact: true }).check()
  await page.getByLabel('Email address').fill('educator@quantumlearn.demo')
  await page.getByLabel('Password').fill('quantumlearn-demo')
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()

  const reviewNavigation = page.getByRole('link', { name: 'Assessment review' })
  await expect(reviewNavigation).toBeVisible()
  await reviewNavigation.focus()
  await page.keyboard.press('Enter')

  await expect(page).toHaveURL(/\/assessor\/review$/)
  await expect(page.getByRole('heading', { name: 'Assessment review queue' })).toBeVisible()
  const responseHeading = page.getByRole('heading', { name: 'Response and evidence' })
  await expect(responseHeading).toBeVisible()
  await expect(page.getByText('The response links the observation to the claim.')).toBeVisible()
  await expect(page.getByText('TARGET_EVIDENCE_MET')).toBeVisible()
  await expect(page.getByText('The exact response contains the required explanation.')).toBeVisible()
  await expect(page.getByText(/Evaluator: rules\.v1\. Model: model\.v1\. Prompt: prompt\.v1\. Retrieval: retrieval\.v1\./)).toBeVisible()
  // Quality Judge stays a separate namespace from the learner result (AT20).
  await expect(page.getByText('Quality review: rejected')).toBeVisible()
  // The formal result renders through ResultSeal: a capitalised PASS/INCOMPLETE
  // label plus a written lifecycle line, never lowercase body text (AC19, AT24).
  // Each project records a different action against the same shared record, so
  // the lifecycle value depends on run order and is matched as a set.
  await expect(page.getByText(/^(Pass|Incomplete)$/).first()).toBeVisible()
  await expect(
    page
      .getByText(
        /^(Provisional \u2014 awaiting assessor review|Confirmed by assessor|Changed by assessor decision|Set aside by assessor decision|Not yet assessed)$/,
      )
      .first(),
  ).toBeVisible()
  const headingTexts = await page.getByRole('heading').allTextContents()
  expect(headingTexts.indexOf('Response and evidence')).toBeLessThan(
    headingTexts.indexOf('Assessor action'),
  )

  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])

  const action = page.getByRole('button', { name: actionLabel })
  await action.focus()
  await page.keyboard.press('Enter')
  const dialog = page.getByRole('alertdialog')
  await expect(dialog).toBeVisible()

  // Initial focus lands on the least destructive control: Cancel.
  const cancel = dialog.getByRole('button', { name: 'Cancel' })
  await expect(cancel).toBeFocused()
  if (actionLabel === 'Override result') {
    await expect(dialog.getByLabel('Replacement result')).toBeVisible()
  }
  await page.keyboard.press('Shift+Tab')
  const reason = dialog.getByLabel('Reason (required)')
  await expect(reason).toBeFocused()
  await page.keyboard.type(`Browser evidence for ${testInfo.project.name}.`)
  await page.keyboard.press('Tab')
  await expect(cancel).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(dialog.getByRole('button', { name: actionLabel })).toBeFocused()
  expect((await new AxeBuilder({ page }).include('[role="alertdialog"]').analyze()).violations).toEqual([])
  const actionResponsePromise = page.waitForResponse((response) =>
    response.request().method() === 'POST'
      && new URL(response.url()).pathname.endsWith('/review'),
  )
  await page.keyboard.press('Enter')
  const actionResponse = await actionResponsePromise
  expect(
    actionResponse.status(),
    `Request ${actionResponse.request().postData()} returned ${await actionResponse.text()}`,
  ).toBe(200)

  await expect(page.getByRole('status')).toContainText(`${actionLabel} recorded`)
  await expect(action).toBeFocused()
  expect(reviewRequests.some((request) => request.method === 'GET'
    && request.path.endsWith('/review-queue') && request.status === 200)).toBe(true)
  expect(reviewRequests.some((request) => request.method === 'POST'
    && request.path.endsWith('/review') && request.status === 200)).toBe(true)

  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur())
  await page.setViewportSize({ width: 640, height: 900 })
  await expectNoHorizontalPageOverflow(page)
  await page.setViewportSize({ width: 320, height: 900 })
  await expectNoHorizontalPageOverflow(page)
})
