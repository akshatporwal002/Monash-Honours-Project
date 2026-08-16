import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

const actionsByProject = {
  'chrome-stable': 'Withhold result',
  'edge-stable': 'Return for review',
  firefox: 'Confirm result',
  webkit: 'Override result',
} as const

async function expectNoHorizontalPageOverflow(page: import('@playwright/test').Page) {
  const dimensions = await page.evaluate(() => ({
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
    overflowingElements: [...document.querySelectorAll<HTMLElement>('body *')]
      .filter((element) => {
        const bounds = element.getBoundingClientRect()
        return bounds.left < 0 || bounds.right > document.documentElement.clientWidth
      })
      .map((element) => ({
        className: element.className,
        tagName: element.tagName,
        text: element.textContent?.trim().slice(0, 80),
      }))
      .slice(0, 10),
  }))
  expect(dimensions.scrollWidth, JSON.stringify(dimensions)).toBeLessThanOrEqual(
    dimensions.clientWidth,
  )
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

  await page.goto('/')
  await page.getByRole('button', { name: 'Educator', exact: true }).click()
  await page.getByLabel('Email address').fill('educator@quantumlearn.demo')
  await page.getByLabel('Password').fill('quantumlearn-demo')
  await page.getByRole('button', { name: 'Enter educator workspace' }).click()

  const reviewNavigation = page.getByRole('button', { name: 'Assessment review' })
  await expect(reviewNavigation).toBeVisible()
  await reviewNavigation.focus()
  await page.keyboard.press('Enter')

  await expect(page.getByRole('heading', { name: 'Assessment review queue' })).toBeVisible()
  const responseHeading = page.getByRole('heading', { name: 'Response and evidence' })
  await expect(responseHeading).toBeVisible()
  await expect(page.getByText('The response links the observation to the claim.')).toBeVisible()
  await expect(page.getByText('Every mandatory criterion is met.')).toBeVisible()
  await expect(page.getByText('The exact response contains the required explanation.')).toBeVisible()
  await expect(page.getByText(/Evaluator: rules\.v1\. Model: model\.v1\. Prompt: prompt\.v1\. Retrieval: retrieval\.v1\./)).toBeVisible()
  await expect(page.getByText('Quality Review:', { exact: true }).locator('..')).toContainText('rejected')
  const headingTexts = await page.getByRole('heading').allTextContents()
  expect(headingTexts.indexOf('Response and evidence')).toBeLessThan(
    headingTexts.indexOf('Assessor action'),
  )

  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])

  const action = page.getByRole('button', { name: actionLabel })
  await action.focus()
  await page.keyboard.press('Enter')
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()

  if (actionLabel === 'Override result') {
    await expect(dialog.getByLabel('Replacement result')).toBeFocused()
    await page.keyboard.press('Tab')
  }
  const reason = dialog.getByLabel('Reason')
  await expect(reason).toBeFocused()
  await page.keyboard.type(`Browser evidence for ${testInfo.project.name}.`)
  await page.keyboard.press('Tab')
  await expect(dialog.getByRole('button', { name: 'Cancel' })).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(dialog.getByRole('button', { name: actionLabel })).toBeFocused()
  expect((await new AxeBuilder({ page }).include('.assessment-review-dialog').analyze()).violations).toEqual([])
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
