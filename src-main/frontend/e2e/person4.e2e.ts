import { readFile } from 'node:fs/promises'

import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

test('production entry keeps protected route-ready modules unmounted', async ({
  page,
}) => {
  await page.goto('/')

  await expect(page.getByRole('heading', { name: 'QuantumLearn' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Your feedback' })).toHaveCount(0)
  await expect(
    page.getByRole('heading', { name: 'Learning and research analytics' }),
  ).toHaveCount(0)
})

test('E2E entry exercises feedback, analytics, keyboard, accessibility, and exports', async ({
  page,
}) => {
  const apiRequests: string[] = []
  const reports: unknown[] = []

  page.on('request', (request) => {
    const url = new URL(request.url())
    if (!url.pathname.startsWith('/api/v1/')) return
    apiRequests.push(`${request.method()} ${url.pathname}${url.search}`)
    if (url.pathname.includes('/feedback/') && url.pathname.endsWith('/report')) {
      reports.push(request.postDataJSON())
    }
  })

  await page.goto('/e2e.html')

  await expect(page.getByText('The revised feedback is ready.')).toBeVisible()
  await expect(
    page.getByRole('heading', { name: 'Learning activity' }),
  ).toBeVisible()
  await expect(
    page.getByRole('heading', { name: /Paired agentic/ }),
  ).toBeVisible()
  await expect(page.locator('.analytics-dashboard')).toHaveAttribute(
    'data-motion',
    'reduce',
  )

  await page.keyboard.press('Tab')
  const reportButton = page.getByRole('button', { name: 'Report a concern' })
  await expect(reportButton).toBeFocused()
  await page.keyboard.press('Enter')
  await page.keyboard.press('Tab')
  const concern = page.getByLabel('Concern', { exact: true })
  await expect(concern).toBeFocused()
  await concern.selectOption('citation_issue')
  await page.keyboard.press('Tab')
  await page.keyboard.type('Please review the source label.')
  await page.keyboard.press('Tab')
  await expect(page.getByRole('button', { name: 'Send report' })).toBeFocused()
  await page.keyboard.press('Enter')

  await expect(
    page.getByText('Thank you. Your concern has been received.'),
  ).toBeVisible()
  expect(reports).toEqual([
    {
      category: 'citation_issue',
      note: 'Please review the source label.',
    },
  ])

  await page.getByLabel('Task type').selectOption('short_answer')
  const applyFilters = page.getByRole('button', { name: 'Apply filters' })
  await applyFilters.focus()
  await page.keyboard.press('Enter')
  await expect
    .poll(() =>
      apiRequests.some(
        (request) =>
          request.startsWith('GET /api/v1/analytics/research?') &&
          request.includes('task_type=short_answer'),
      ),
    )
    .toBe(true)

  const csvDownloadPromise = page.waitForEvent('download')
  await page.getByRole('link', { name: 'Download CSV' }).click()
  const csvDownload = await csvDownloadPromise
  expect(csvDownload.suggestedFilename()).toMatch(
    /^quantumlearn-research-\d{8}T\d{6}Z\.csv$/,
  )
  const csvPath = await csvDownload.path()
  expect(csvPath).not.toBeNull()
  expect(await readFile(csvPath!, 'utf8')).toContain('"agentic_rag"')

  const jsonDownloadPromise = page.waitForEvent('download')
  await page.getByRole('link', { name: 'Download JSON' }).click()
  const jsonDownload = await jsonDownloadPromise
  expect(jsonDownload.suggestedFilename()).toMatch(
    /^quantumlearn-research-\d{8}T\d{6}Z\.json$/,
  )
  const jsonPath = await jsonDownload.path()
  expect(jsonPath).not.toBeNull()
  expect(JSON.parse(await readFile(jsonPath!, 'utf8'))).toMatchObject({
    schema_version: 'quantumlearn.research-export.v1',
    record_count: 2,
  })

  const accessibility = await new AxeBuilder({ page }).analyze()
  expect(accessibility.violations).toEqual([])
  expect(apiRequests).toContain(
    'POST /api/v1/submissions/submission-e2e/feedback',
  )
})
